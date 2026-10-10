from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bridge.manifest import atomic_write_json, read_manifest, write_manifest
from bridge.publication import PublicationRequest, data_hash, file_hash, read_json, ready_path, receipt_path, verify_package
from bridge.schema import CheckResultEntry, Clip, Convention, Manifest, Source, UEDestination, ValidationSummary

spec = importlib.util.spec_from_file_location("publication_unreal", os.path.join(ROOT, "unreal", "__init__.py"))
ue = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ue
spec.loader.exec_module(ue)
from publication_unreal import importer
from publication_unreal.verification import verify_animation


def package(directory):
    fbx = os.path.join(directory, "hero.fbx")
    with open(fbx, "wb") as stream:
        stream.write(b"test FBX content")
    settings = {"sample_rate": 30}
    manifest = Manifest.new(
        version="1.1",
        source=Source(skeleton_root="root"), convention=Convention(),
        clips=[Clip("walk", 1, 30, True)], fbx_path=fbx,
        ue_destination=UEDestination(content_root="/Game/Animations", skeleton_path="/Game/Shared/Hero"),
        validation=ValidationSummary.from_entries([CheckResultEntry("scene.fps", "error", True)]),
        publication={
            "version": 1, "publish_id": "a" * 32, "project": "Demo", "asset": "Hero", "revision": 3,
            "fbx_sha256": file_hash(fbx), "fbx_size": os.path.getsize(fbx),
            "rules_sha256": "b" * 64, "settings": settings, "settings_sha256": data_hash(settings),
            "required_bones": ["root"], "required_checks": ["scene.fps"],
        },
    )
    path = os.path.join(directory, "hero_manifest.json")
    write_manifest(manifest, path)
    report = os.path.join(directory, "report.txt")
    with open(report, "w") as stream:
        stream.write("validation report")
    atomic_write_json({"publish_id": "a" * 32, "manifest_sha256": file_hash(path),
                       "report": "report.txt", "report_sha256": file_hash(report)}, ready_path(path))
    return manifest, path, fbx


class FakeSkeleton:
    pass


class FakeAnimation:
    def __init__(self, skeleton):
        self.values = {"skeleton": skeleton, "enable_root_motion": True}

    def get_editor_property(self, name):
        return self.values[name]

    def get_data_model(self):
        return SimpleNamespace(get_frame_rate=lambda: SimpleNamespace(numerator=30, denominator=1))


def fake_engine():
    skeleton = FakeSkeleton()
    animation = FakeAnimation(skeleton)
    assets = {"/Game/Shared/Hero": skeleton}
    engine = SimpleNamespace(
        Skeleton=FakeSkeleton, AnimSequence=FakeAnimation,
        load_asset=lambda path: assets.get(path),
        SystemLibrary=SimpleNamespace(get_project_name=lambda: "Demo", get_engine_version=lambda: "5.3"),
        EditorAssetLibrary=SimpleNamespace(
            get_path_name_for_loaded_asset=lambda asset: "/Game/Shared/Hero.Hero",
            does_asset_exist=lambda path: path in assets,
        ),
        AnimationLibrary=SimpleNamespace(
            get_num_frames=lambda asset: 29, get_num_keys=lambda asset: 30,
            get_sequence_length=lambda asset: 29 / 30.0,
            get_animation_track_names=lambda asset: ["root"],
        ),
    )
    return engine, assets, animation


class TestPublicationPackage(unittest.TestCase):
    def test_identity_validation(self):
        for project in ("../Demo", "Demo/Bad", "", "Demo Project"):
            with self.assertRaises(ValueError):
                PublicationRequest(project, "Hero", 1).validate()
        self.assertEqual(PublicationRequest("Demo", "Hero", 3).relative_path(), "Demo/Hero/v003")
        for revision in (True, 0, -1, "3"):
            with self.assertRaises(ValueError):
                PublicationRequest("Demo", "Hero", revision).validate()

    def test_ready_and_hashes_bind_files(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, path, fbx = package(directory)
            self.assertEqual(verify_package(manifest, path, fbx), file_hash(path))
            with open(fbx, "ab") as stream:
                stream.write(b"changed")
            with self.assertRaises(ValueError):
                verify_package(manifest, path, fbx)

    def test_missing_report_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, path, fbx = package(directory)
            os.remove(os.path.join(directory, "report.txt"))
            with self.assertRaises(FileNotFoundError):
                verify_package(manifest, path, fbx)

    def test_changed_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, path, fbx = package(directory)
            with open(path, "a") as stream:
                stream.write(" ")
            with self.assertRaises(ValueError):
                verify_package(manifest, path, fbx)

    def test_missing_ready_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, path, fbx = package(directory)
            os.remove(ready_path(path))
            with self.assertRaises(FileNotFoundError):
                verify_package(manifest, path, fbx)

    def test_atomic_write_failure_keeps_previous_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "record.json")
            atomic_write_json({"version": 1}, path)
            with patch("bridge.manifest.os.replace", side_effect=OSError("locked")):
                with self.assertRaises(OSError):
                    atomic_write_json({"version": 2}, path)
            self.assertEqual(read_json(path), {"version": 1})
            self.assertEqual(os.listdir(directory), ["record.json"])

    def test_publication_requires_new_manifest_version(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _, _ = package(directory)
            manifest.version = "1.0"
            with self.assertRaises(ValueError):
                manifest.validate()

    def test_contract_fingerprint_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _, _ = package(directory)
            manifest.publication["settings"]["sample_rate"] = 24
            with self.assertRaises(ValueError):
                manifest.validate()

    def test_incomplete_check_records_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, path, fbx = package(directory)
            manifest.publication["required_checks"].append("missing.check")
            with self.assertRaises(ValueError):
                verify_package(manifest, path, fbx)


class TestPublicationExport(unittest.TestCase):
    def request(self, directory):
        from mtu_maya.core.preset_loader import SkeletonPreset
        from mtu_maya.export.fbx_exporter import ExportRequest
        return ExportRequest(
            fbx_path=os.path.join(directory, "hero.fbx"), clips=[Clip("walk", 1, 30, True)],
            preset=SkeletonPreset(id="custom", display_name="Custom", skeleton_type="custom"),
            skeleton_root="|root", ue_skeleton_path="/Game/Shared/Hero",
            publication=PublicationRequest("Demo", "Hero", 3),
        )

    def export(self, request):
        from mtu_maya.checks import CheckContext, CheckResult, RunReport
        from mtu_maya.export import fbx_exporter as exporter
        context = CheckContext(joints=["|root"], scene_units="cm")
        report = RunReport(results=[CheckResult("scene.fps", "scene", "error", True)])
        def write(path, *args, **kwargs):
            with open(path, "wb") as stream:
                stream.write(b"exported FBX")
        with patch.object(exporter, "build_context", return_value=context), \
                patch.object(exporter, "run_all_checks", return_value=report), \
                patch.object(exporter.maya_utils, "ensure_fbx_plugin", return_value=True), \
                patch.object(exporter, "_apply_fbx_preset"), \
                patch.object(exporter, "_export_fbx", side_effect=write), \
                patch.object(exporter, "_maya_version_str", return_value="2022"):
            return exporter.export_animation(request)

    def test_complete_package_and_existing_version_protection(self):
        from mtu_maya.export.manifest_writer import write_all_artifacts
        with tempfile.TemporaryDirectory() as directory:
            request = self.request(directory)
            result = self.export(request)
            self.assertIn("v003", result.fbx_path)
            self.assertFalse(result.is_complete())
            write_all_artifacts(result, write_report=False)
            self.assertTrue(result.is_complete())
            verify_package(read_manifest(result.manifest_path), result.manifest_path, result.fbx_path)
            before = file_hash(result.manifest_path)
            with self.assertRaises(FileExistsError):
                self.export(request)
            self.assertEqual(before, file_hash(result.manifest_path))

    def test_skips_rejected_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            request = self.request(directory)
            request.skipped_checks.add("scene.fps")
            with self.assertRaises(ValueError):
                self.export(request)
            self.assertEqual(os.listdir(directory), [])

    def test_rig_and_single_frame_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            request = self.request(directory)
            request.include_rig = True
            with self.assertRaises(ValueError):
                self.export(request)
            request.include_rig = False
            request.clips[0].end = request.clips[0].start
            with self.assertRaises(ValueError):
                self.export(request)

    def test_report_failure_does_not_make_ready(self):
        from mtu_maya.export import manifest_writer
        with tempfile.TemporaryDirectory() as directory:
            result = self.export(self.request(directory))
            with patch.object(manifest_writer, "write_markdown_report", side_effect=OSError("report failed")):
                manifest_writer.write_all_artifacts(result)
            self.assertFalse(result.is_complete())
            self.assertFalse(os.path.isfile(ready_path(result.manifest_path)))
            self.assertTrue(result.errors)


class TestVerification(unittest.TestCase):
    def setUp(self):
        self.engine, self.assets, self.animation = fake_engine()
        self.assets["/Game/Test"] = self.animation

    def verify(self):
        return verify_animation(self.engine, "/Game/Test", "/Game/Shared/Hero", Clip("walk", 1, 30, True), 30, ["root"])

    def test_expected_frame_intervals_and_samples(self):
        result = self.verify()
        self.assertTrue(result["passed"])
        self.assertEqual(result["expected"]["frames"], 29)
        self.assertEqual(result["expected"]["keys"], 30)

    def test_wrong_type(self):
        self.assets["/Game/Test"] = object()
        self.assertFalse(self.verify()["passed"])

    def test_wrong_skeleton(self):
        self.animation.values["skeleton"] = None
        self.assertFalse(self.verify()["passed"])

    def test_wrong_frames_duration_and_tracks(self):
        self.engine.AnimationLibrary.get_num_frames = lambda asset: 120
        self.engine.AnimationLibrary.get_sequence_length = lambda asset: 4.0
        self.engine.AnimationLibrary.get_animation_track_names = lambda asset: []
        result = self.verify()
        self.assertFalse(result["passed"])
        self.assertGreaterEqual(len(result["errors"]), 3)

    def test_wrong_root_motion(self):
        self.animation.values["enable_root_motion"] = False
        self.assertFalse(self.verify()["passed"])

    def test_missing_api_fails_closed(self):
        del self.engine.AnimationLibrary.get_num_keys
        self.assertFalse(self.verify()["passed"])


class TestPublicationImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manifest, self.path, self.fbx = package(self.tmp.name)
        self.engine, self.assets, self.animation = fake_engine()
        self.target = "/Game/Animations/Demo/Hero/v003/walk"
        self.calls = []
        def import_clip(fbx, skeleton, destination, name, clip, rate, overwrite):
            self.calls.append((destination, name, overwrite))
            self.assets[destination + "/" + name] = self.animation
            return destination + "/" + name
        for name, value in (
            ("_unreal", lambda: self.engine), ("check_environment", lambda: []),
            ("_import_clip_fbx", import_clip), ("_set_root_motion", lambda path, enabled: None),
        ):
            replacement = patch.object(importer, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def run_import(self):
        return importer.import_manifest(self.path)

    def test_success_receipt_without_mutating_manifest(self):
        before = file_hash(self.path)
        result = self.run_import()
        self.assertEqual(result.succeeded, ["walk"])
        receipt = read_json(receipt_path(self.path))
        self.assertEqual(receipt["result"]["status"], "success")
        self.assertTrue(receipt["verification"][0]["passed"])
        self.assertEqual(before, file_hash(self.path))
        self.assertFalse(self.calls[0][2])

    def test_repeated_success_reverifies_without_import(self):
        self.run_import()
        result = self.run_import()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result.succeeded, ["walk"])
        self.animation.values["enable_root_motion"] = False
        self.assertEqual(self.run_import().failed, ["walk"])
        self.assertEqual(len(self.calls), 1)

    def test_conflict_never_imports(self):
        self.assets[self.target] = object()
        result = self.run_import()
        self.assertTrue(result.errors)
        self.assertEqual(self.calls, [])

    def test_wrong_project_never_imports(self):
        self.engine.SystemLibrary.get_project_name = lambda: "Wrong"
        self.assertTrue(self.run_import().errors)
        self.assertEqual(self.calls, [])

    def test_hash_mismatch_never_imports(self):
        with open(self.fbx, "ab") as stream:
            stream.write(b"wrong")
        self.assertTrue(self.run_import().errors)
        self.assertEqual(self.calls, [])

    def test_receipt_failure_visible(self):
        with patch("bridge.manifest.atomic_write_json", side_effect=OSError("read only")):
            result = self.run_import()
        self.assertTrue(any("回执" in error for error in result.errors))
        self.assertEqual(read_manifest(self.path).result.status, "pending")

    def test_wrong_target_skeleton_type_never_imports(self):
        self.assets["/Game/Shared/Hero"] = object()
        self.assertTrue(self.run_import().errors)
        self.assertEqual(self.calls, [])

    def test_partial_failure_keeps_failed_batch_receipt(self):
        self.manifest.clips.append(Clip("run", 31, 60, True))
        write_manifest(self.manifest, self.path)
        ready = read_json(ready_path(self.path))
        ready["manifest_sha256"] = file_hash(self.path)
        atomic_write_json(ready, ready_path(self.path))
        original = importer._import_clip_fbx
        def second_fails(*args, **kwargs):
            if args[3] == "run":
                raise RuntimeError("second clip failed")
            return original(*args, **kwargs)
        with patch.object(importer, "_import_clip_fbx", side_effect=second_fails):
            result = self.run_import()
        self.assertEqual(result.succeeded, ["walk"])
        self.assertEqual(result.failed, ["run"])
        self.assertEqual(read_json(receipt_path(self.path))["result"]["status"], "failed")
        self.assertIs(self.assets[self.target], self.animation)

    def test_import_failure_receipt(self):
        with patch.object(importer, "_import_clip_fbx", side_effect=RuntimeError("FBX failed")):
            result = self.run_import()
        self.assertEqual(result.failed, ["walk"])
        self.assertEqual(read_json(receipt_path(self.path))["result"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
