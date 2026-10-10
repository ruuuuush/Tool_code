from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import PurePosixPath

DIRECTORIES = ("bridge", "config", "mtu_maya", "unreal")
ROOT_FILES = ("launch_maya_tool.py", "launch_ue_importer.py", "install_shelf_button.py",
              "install_ue_menu.py", "tool_version.py", "tool_deployment.py")
COMPATIBILITY = {"python_min": [3, 7], "maya_min": 2022, "unreal_min": [5, 3], "status": "declared_not_host_certified"}


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _read_json(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("Tool version must be major.minor.patch")
    return value


def _safe_path(name):
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Invalid release path")
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name or any(part in (".", "..") for part in path.parts):
        raise ValueError("Unsafe release path: " + name)
    for part in path.parts:
        if (re.search(r'[<>:"|?*\x00-\x1f]', part) or part.endswith((".", " "))
                or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", part.split(".")[0])):
            raise ValueError("Unsafe Windows release path: " + name)
    return name


def _runtime_path(name):
    _safe_path(name)
    parts = PurePosixPath(name).parts
    return (name in ROOT_FILES or (len(parts) > 1 and parts[0] in DIRECTORIES
            and "__pycache__" not in parts and name.endswith((".py", ".json"))))


def _source_version(data):
    tree = ast.parse(data.decode("utf-8"))
    values = [node.value for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)]
    if len(values) != 1:
        raise ValueError("Missing unique VERSION assignment")
    return _version(ast.literal_eval(values[0]))


def _release(data):
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unsupported release schema")
    _version(data.get("version"))
    if data.get("compatibility") != COMPATIBILITY:
        raise ValueError("Unsupported compatibility declaration")
    files = data.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Empty release")
    if not set(ROOT_FILES).issubset(files):
        raise ValueError("Required launch/runtime files missing")
    lowered = set()
    for name, entry in files.items():
        if not _runtime_path(name) or name.lower() in lowered:
            raise ValueError("Unexpected or duplicate release path: " + name)
        lowered.add(name.lower())
        if not isinstance(entry, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
            raise ValueError("Invalid release hash")
        size = entry.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("Invalid release size")
    return data


def build(source, output):
    source = os.path.abspath(source)
    files = {}
    for directory in DIRECTORIES:
        for root, directories, names in os.walk(os.path.join(source, directory)):
            directories[:] = [name for name in directories if name != "__pycache__"]
            for name in names:
                path = os.path.join(root, name)
                relative = os.path.relpath(path, source).replace("\\", "/")
                if _runtime_path(relative):
                    if os.path.islink(path):
                        raise ValueError("Release source cannot contain symlinks")
                    with open(path, "rb") as stream:
                        files[relative] = stream.read()
    for name in ROOT_FILES:
        path = os.path.join(source, name)
        if os.path.islink(path):
            raise ValueError("Release source cannot contain symlinks")
        with open(path, "rb") as stream:
            files[name] = stream.read()
    release = _release({"schema": 1, "version": _source_version(files["tool_version.py"]),
                        "compatibility": COMPATIBILITY,
                        "files": {name: {"sha256": _hash(data), "size": len(data)} for name, data in sorted(files.items())}})
    if not os.path.isdir(os.path.dirname(os.path.abspath(output))):
        raise ValueError("Release output parent directory must exist")
    with open(output, "xb") as target:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("release.json", json.dumps(release, sort_keys=True, indent=2))
            for name, data in sorted(files.items()):
                archive.writestr(name, data)
    return os.path.abspath(output)


def verify(root, expected_hash=None):
    root = os.path.abspath(root)
    release_path = os.path.join(root, "release.json")
    if os.path.islink(root) or os.path.islink(release_path):
        raise ValueError("Cache cannot contain symbolic links")
    with open(release_path, "rb") as stream:
        raw = stream.read()
    if expected_hash is not None and _hash(raw) != expected_hash:
        raise ValueError("Release does not match project lock")
    release = _release(json.loads(raw.decode("utf-8")))
    actual = set()
    for directory, directories, names in os.walk(root):
        if any(os.path.islink(os.path.join(directory, name)) for name in directories + names):
            raise ValueError("Cache contains symbolic links")
        for name in names:
            relative = os.path.relpath(os.path.join(directory, name), root).replace("\\", "/")
            if relative != "release.json" and not ("__pycache__" in relative.split("/") and name.endswith(".pyc")):
                actual.add(relative)
    if actual != set(release["files"]):
        raise ValueError("Cache files differ from release manifest")
    for name, entry in release["files"].items():
        with open(os.path.join(root, *name.split("/")), "rb") as stream:
            content = stream.read()
        if len(content) != entry["size"] or _hash(content) != entry["sha256"]:
            raise ValueError("Cache file changed: " + name)
    with open(os.path.join(root, "tool_version.py"), "rb") as stream:
        if _source_version(stream.read()) != release["version"]:
            raise ValueError("Runtime and release version differ")
    return release, _hash(raw)


def install(package, cache):
    cache = os.path.abspath(cache)
    os.makedirs(cache, exist_ok=True)
    temporary = tempfile.mkdtemp(prefix=".install-", dir=cache)
    try:
        with zipfile.ZipFile(package) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len({name.lower() for name in names}) != len(names):
                raise ValueError("Duplicate archive members")
            for member in members:
                _safe_path(member.filename)
                if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("Archive contains directory or symlink entry")
            release = _release(json.loads(archive.read("release.json").decode("utf-8")))
            if set(names) != set(release["files"]) | {"release.json"}:
                raise ValueError("Archive does not match release manifest")
            destination = os.path.join(cache, release["version"])
            if os.path.lexists(destination):
                raise FileExistsError("Cache version already exists: " + destination)
            for member in members:
                if member.filename != "release.json" and member.file_size != release["files"][member.filename]["size"]:
                    raise ValueError("Archive file size mismatch")
                path = os.path.join(temporary, *member.filename.split("/"))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with archive.open(member) as source, open(path, "xb") as target:
                    shutil.copyfileobj(source, target)
        verify(temporary)
        if os.path.lexists(destination):
            raise FileExistsError("Cache version already exists")
        os.rename(temporary, destination)
        temporary = None
        return destination
    finally:
        if temporary is not None:
            shutil.rmtree(temporary)


def _atomic_json(data, path):
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        raise ValueError("Project lock parent directory must exist")
    descriptor, temporary = tempfile.mkstemp(prefix=".lock-", suffix=".json", dir=parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def pin(cache, version, lock):
    version = _version(version)
    release, digest = verify(os.path.join(cache, version))
    _atomic_json({"schema": 1, "version": release["version"], "release_sha256": digest}, lock)
    return os.path.abspath(lock)


def resolve(cache, lock):
    data = _read_json(lock)
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Invalid project tool lock")
    version = _version(data.get("version"))
    digest = data.get("release_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid project release hash")
    root = os.path.abspath(os.path.join(cache, version))
    release, _ = verify(root, digest)
    if release["version"] != version:
        raise ValueError("Cache directory version mismatch")
    return root


def _launcher(cache, lock, module_name):
    root = resolve(cache, lock)
    if sys.version_info[:2] < (3, 7):
        raise RuntimeError("Tool requires Python 3.7 or later")
    normalized = os.path.normcase(os.path.realpath(root))
    prefixes = ("bridge", "mtu_maya", "mtu_unreal", "tool_version", "launch_maya_tool", "launch_ue_importer")
    for name, module in list(sys.modules.items()):
        if any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes):
            path = getattr(module, "__file__", None)
            if path and not os.path.normcase(os.path.realpath(path)).startswith(normalized + os.sep):
                raise RuntimeError("Other tool version already loaded; restart Maya/UE before switching")
    if root not in sys.path:
        sys.path.insert(0, root)
    spec = importlib.util.spec_from_file_location(module_name, os.path.join(root, module_name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def launch_maya(cache, lock):
    import maya.cmds as cmds
    if int(str(cmds.about(version=True)).split()[0]) < 2022:
        raise RuntimeError("Deployment requires Maya 2022 or later")
    return _launcher(cache, lock, "launch_maya_tool").show()


def launch_unreal(cache, lock, manifest_path):
    import unreal
    match = re.match(r"(\d+)\.(\d+)", unreal.SystemLibrary.get_engine_version())
    if not match or tuple(map(int, match.groups())) < (5, 3):
        raise RuntimeError("Deployment requires UE 5.3 or later")
    launcher = _launcher(cache, lock, "launch_ue_importer")
    outcome = launcher.run(manifest_path)
    launcher.report(outcome)
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(description="Versioned Maya-to-UE deployment; pin older version to roll back (restart host).")
    commands = parser.add_subparsers(dest="command", required=True)
    build_command = commands.add_parser("build")
    build_command.add_argument("source")
    build_command.add_argument("output")
    install_command = commands.add_parser("install")
    install_command.add_argument("package")
    install_command.add_argument("cache")
    pin_command = commands.add_parser("pin")
    pin_command.add_argument("cache")
    pin_command.add_argument("version")
    pin_command.add_argument("lock")
    verify_command = commands.add_parser("verify")
    verify_command.add_argument("cache")
    verify_command.add_argument("lock")
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build(args.source, args.output)
    elif args.command == "install":
        result = install(args.package, args.cache)
    elif args.command == "pin":
        result = pin(args.cache, args.version, args.lock)
    else:
        result = resolve(args.cache, args.lock)
    print(result)
    return result


if __name__ == "__main__":
    main()
