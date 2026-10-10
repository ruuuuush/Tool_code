from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tool_deployment as deployment
from tool_version import VERSION


class TestDeployment(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.package = os.path.join(self.tmp.name, "release.zip")
        self.cache = os.path.join(self.tmp.name, "cache")
        self.lock = os.path.join(self.tmp.name, "project.lock.json")
        deployment.build(ROOT, self.package)

    def install_pin(self):
        root = deployment.install(self.package, self.cache)
        deployment.pin(self.cache, VERSION, self.lock)
        return root

    def altered_archive(self, changes=None, extra=None):
        output = os.path.join(self.tmp.name, "changed.zip")
        with zipfile.ZipFile(self.package) as source, zipfile.ZipFile(output, "w") as target:
            for name in source.namelist():
                target.writestr(name, (changes or {}).get(name, source.read(name)))
            if extra:
                for name, data in extra:
                    target.writestr(name, data)
        return output

    def test_runtime_package_excludes_development_files(self):
        with zipfile.ZipFile(self.package) as archive:
            names = archive.namelist()
            self.assertFalse(any("__pycache__" in name or name.startswith(("tests/", "docs/")) for name in names))
            release = json.loads(archive.read("release.json"))
            self.assertEqual(release["version"], VERSION)
            self.assertIn("bridge/publication.py", release["files"])
            self.assertIn("unreal/verification.py", release["files"])

    def test_build_does_not_overwrite(self):
        with open(self.package, "rb") as stream:
            before = stream.read()
        with self.assertRaises(FileExistsError):
            deployment.build(ROOT, self.package)
        with open(self.package, "rb") as stream:
            self.assertEqual(stream.read(), before)

    def test_install_pin_resolve(self):
        root = self.install_pin()
        self.assertEqual(deployment.resolve(self.cache, self.lock), root)
        release, _ = deployment.verify(root)
        self.assertEqual(release["version"], VERSION)

    def test_existing_cache_preserved(self):
        root = self.install_pin()
        with self.assertRaises(FileExistsError):
            deployment.install(self.package, self.cache)
        self.assertEqual(deployment.resolve(self.cache, self.lock), root)

    def test_modified_package_never_enabled(self):
        altered = self.altered_archive({"tool_version.py": b'VERSION = "9.9.9"\n'})
        with self.assertRaises(ValueError):
            deployment.install(altered, self.cache)
        self.assertEqual(os.listdir(self.cache), [])

    def test_path_traversal_never_written(self):
        for name in ("../escape.py", "/escape.py", "C:/escape.py", "config\\escape.py", "config/CON.json"):
            altered = self.altered_archive(extra=[(name, b"bad")])
            with self.assertRaises(ValueError):
                deployment.install(altered, self.cache)
            self.assertEqual(os.listdir(self.cache), [])

    def test_duplicate_member_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            altered = self.altered_archive(extra=[("tool_version.py", b"bad")])
        with self.assertRaises(ValueError):
            deployment.install(altered, self.cache)

    def test_modified_cache_and_extra_code_rejected(self):
        root = self.install_pin()
        with open(os.path.join(root, "extra.py"), "w") as stream:
            stream.write("pass")
        with self.assertRaises(ValueError):
            deployment.resolve(self.cache, self.lock)
        os.remove(os.path.join(root, "extra.py"))
        with open(os.path.join(root, "tool_version.py"), "a") as stream:
            stream.write("\n")
        with self.assertRaises(ValueError):
            deployment.resolve(self.cache, self.lock)

    def test_bytecode_cache_allowed(self):
        root = self.install_pin()
        directory = os.path.join(root, "__pycache__")
        os.makedirs(directory)
        with open(os.path.join(directory, "tool_version.cpython-37.pyc"), "wb") as stream:
            stream.write(b"cache")
        self.assertEqual(deployment.resolve(self.cache, self.lock), root)

    def test_lock_hash_tampering_rejected(self):
        self.install_pin()
        data = deployment._read_json(self.lock)
        data["release_sha256"] = "0" * 64
        deployment._atomic_json(data, self.lock)
        with self.assertRaises(ValueError):
            deployment.resolve(self.cache, self.lock)

    def test_atomic_lock_failure_preserves_old_lock(self):
        self.install_pin()
        before = deployment._read_json(self.lock)
        with patch.object(deployment.os, "replace", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                deployment.pin(self.cache, VERSION, self.lock)
        self.assertEqual(deployment._read_json(self.lock), before)

    def test_rollback_selects_old_cache_without_modification(self):
        current = self.install_pin()
        source = os.path.join(self.tmp.name, "source")
        shutil.copytree(current, source)
        with open(os.path.join(source, "tool_version.py"), "w") as stream:
            stream.write('VERSION = "0.2.0"\n')
        older = os.path.join(self.tmp.name, "old.zip")
        deployment.build(source, older)
        old_root = deployment.install(older, self.cache)
        deployment.pin(self.cache, "0.2.0", self.lock)
        self.assertEqual(deployment.resolve(self.cache, self.lock), old_root)
        deployment.pin(self.cache, VERSION, self.lock)
        self.assertEqual(deployment.resolve(self.cache, self.lock), current)

    def test_other_loaded_version_requires_restart(self):
        root = self.install_pin()
        fake = SimpleNamespace(__file__=os.path.join(self.tmp.name, "other", "bridge", "__init__.py"))
        with patch.dict(sys.modules, {"bridge": fake}):
            with self.assertRaisesRegex(RuntimeError, "restart"):
                deployment._launcher(self.cache, self.lock, "launch_maya_tool")
        self.assertTrue(os.path.isdir(root))

    def test_launcher_runs_in_clean_python_session(self):
        import subprocess
        root = self.install_pin()
        code = (
            "import sys; sys.path.insert(0, " + repr(ROOT) + "); "
            "import tool_deployment as d; "
            "m=d._launcher(" + repr(self.cache) + ", " + repr(self.lock) + ", 'launch_maya_tool'); "
            "assert m.__file__.startswith(" + repr(root) + "); "
            "import tool_version; assert tool_version.VERSION == " + repr(VERSION)
        )
        subprocess.check_call([sys.executable, "-c", code])

    def test_invalid_version_and_lock(self):
        for version in ("../bad", "1", "1.0", "1.0.0/other"):
            with self.assertRaises(ValueError):
                deployment.pin(self.cache, version, self.lock)


if __name__ == "__main__":
    unittest.main()
