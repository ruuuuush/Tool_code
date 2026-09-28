"""tests.test_bridge_schema

Round-trip and validation tests for the bridge layer.

These run with plain Python 3 — no Maya, no UE — so they can be executed
in any environment, which is exactly the point of decoupling the manifest
into its own layer.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import asdict

# Allow running from the repo root without installation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge import (
    SCHEMA_VERSION,
    Manifest,
    Clip,
    Source,
    Convention,
    UEDestination,
    CheckResultEntry,
    ValidationSummary,
    ImportResult,
    read_manifest,
    write_manifest,
    load_or_create,
)


def _sample_manifest() -> Manifest:
    return Manifest.new(
        version=SCHEMA_VERSION,
        tool_version="0.1.0",
        source=Source(
            maya_scene="hero_anim.ma",
            maya_version="2024",
            preset="ue_mannequin",
            skeleton_root="root",
        ),
        convention=Convention(up_axis="z", unit="cm", frame_rate=30, axis_conversion=False),
        clips=[
            Clip(name="idle", start=1, end=30, root_motion=False),
            Clip(name="walk", start=31, end=90, root_motion=True),
        ],
        fbx_path="./exports/hero_anim.fbx",
        ue_destination=UEDestination(
            content_root="/Game/Animations/Hero",
            skeleton_path="/Game/Animations/Hero/Hero_Skeleton",
            overwrite_policy="rename",
        ),
        validation=ValidationSummary(
            status="passed_with_warnings",
            errors=0,
            warnings=1,
            infos=0,
            results=[
                CheckResultEntry(
                    check="scene.unit",
                    level="error",
                    passed=True,
                    message="unit = cm",
                ),
                CheckResultEntry(
                    check="skeleton.scale",
                    level="warning",
                    passed=False,
                    message="joint 'spine_03' scale = 1.02",
                    auto_fixable=True,
                ),
            ],
        ),
        result=ImportResult(status="pending"),
    )


class TestClip(unittest.TestCase):
    def test_valid_clip(self):
        Clip(name="idle", start=1, end=30).validate()

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            Clip(name="", start=1, end=30).validate()

    def test_end_before_start_rejected(self):
        with self.assertRaises(ValueError):
            Clip(name="x", start=30, end=1).validate()

    def test_negative_start_rejected(self):
        with self.assertRaises(ValueError):
            Clip(name="x", start=-1, end=10).validate()


class TestManifestValidation(unittest.TestCase):
    def test_valid_manifest(self):
        _sample_manifest().validate()  # should not raise

    def test_wrong_version_rejected(self):
        m = _sample_manifest()
        m.version = "0.9"
        with self.assertRaises(ValueError):
            m.validate()

    def test_y_up_is_allowed(self):
        m = _sample_manifest()
        m.convention.up_axis = "y"
        m.validate()

    def test_invalid_up_axis_rejected(self):
        m = _sample_manifest()
        m.convention.up_axis = "x"
        with self.assertRaises(ValueError):
            m.validate()

    def test_unit_lock(self):
        m = _sample_manifest()
        m.convention.unit = "m"
        with self.assertRaises(ValueError):
            m.validate()

    def test_axis_conversion_lock(self):
        m = _sample_manifest()
        m.convention.axis_conversion = True
        with self.assertRaises(ValueError):
            m.validate()

    def test_empty_fbx_path_rejected(self):
        m = _sample_manifest()
        m.fbx_path = ""
        with self.assertRaises(ValueError):
            m.validate()

    def test_duplicate_clip_names_rejected(self):
        m = _sample_manifest()
        m.clips = [
            Clip(name="idle", start=1, end=10),
            Clip(name="idle", start=11, end=20),
        ]
        with self.assertRaises(ValueError):
            m.validate()

    def test_can_export_flag(self):
        m = _sample_manifest()
        self.assertTrue(m.can_export())
        m.validation.status = "failed"
        self.assertFalse(m.can_export())


class TestSkeletonDelivery(unittest.TestCase):
    def test_defaults_are_off(self):
        m = _sample_manifest()
        d = m.ue_destination.skeleton_delivery
        self.assertFalse(d.include_rig)
        self.assertFalse(d.create_if_missing)
        self.assertEqual(d.import_uniform_scale, 1.0)

    def test_create_without_rig_rejected(self):
        # UE cannot build a Skeleton from an animation-only FBX, so this
        # combination must never reach the importer.
        m = _sample_manifest()
        m.ue_destination.skeleton_delivery.create_if_missing = True
        m.ue_destination.skeleton_delivery.include_rig = False
        with self.assertRaises(ValueError):
            m.validate()

    def test_empty_skeleton_path_allowed_when_creating(self):
        m = _sample_manifest()
        m.ue_destination.skeleton_path = ""
        m.ue_destination.skeleton_delivery.include_rig = True
        m.ue_destination.skeleton_delivery.create_if_missing = True
        m.validate()

    def test_empty_skeleton_path_rejected_otherwise(self):
        m = _sample_manifest()
        m.ue_destination.skeleton_path = ""
        with self.assertRaises(ValueError):
            m.validate()

    def test_non_positive_scale_rejected(self):
        from bridge.schema import SkeletonDelivery
        with self.assertRaises(ValueError):
            SkeletonDelivery.from_dict({"import_uniform_scale": 0})
        with self.assertRaises(ValueError):
            SkeletonDelivery.from_dict({"import_uniform_scale": -5})

    def test_round_trip_preserves_delivery(self):
        m = _sample_manifest()
        m.ue_destination.skeleton_delivery.include_rig = True
        m.ue_destination.skeleton_delivery.create_if_missing = True
        m.ue_destination.skeleton_delivery.import_uniform_scale = 50.0
        restored = Manifest.from_dict(m.to_dict())
        d = restored.ue_destination.skeleton_delivery
        self.assertTrue(d.include_rig)
        self.assertTrue(d.create_if_missing)
        self.assertEqual(d.import_uniform_scale, 50.0)


class TestValidationSummary(unittest.TestCase):
    def test_from_entries_counts(self):
        entries = [
            CheckResultEntry(check="a", level="error", passed=False),
            CheckResultEntry(check="b", level="error", passed=True),
            CheckResultEntry(check="c", level="warning", passed=False),
            CheckResultEntry(check="d", level="info", passed=False),
        ]
        s = ValidationSummary.from_entries(entries)
        self.assertEqual(s.errors, 1)
        self.assertEqual(s.warnings, 1)
        self.assertEqual(s.infos, 1)
        self.assertEqual(s.status, "failed")

    def test_passed_with_warnings_status(self):
        entries = [
            CheckResultEntry(check="a", level="warning", passed=False),
            CheckResultEntry(check="b", level="info", passed=False),
        ]
        s = ValidationSummary.from_entries(entries)
        self.assertEqual(s.status, "passed_with_warnings")

    def test_all_passed_status(self):
        entries = [CheckResultEntry(check="a", level="error", passed=True)]
        s = ValidationSummary.from_entries(entries)
        self.assertEqual(s.status, "passed")


class TestSkippedChecksInManifest(unittest.TestCase):
    """跳过必须留痕：下游得分得清"通过"和"根本没跑"。"""

    def test_skipped_error_does_not_count_as_failure(self):
        entries = [
            CheckResultEntry(check="a", level="error", passed=False, skipped=True),
            CheckResultEntry(check="b", level="info", passed=True),
        ]
        s = ValidationSummary.from_entries(entries)
        self.assertEqual(s.errors, 0)
        self.assertEqual(s.status, "passed")

    def test_skipped_list_carries_id_and_level(self):
        entries = [CheckResultEntry(check="skeleton.naming", level="error",
                                    passed=False, skipped=True)]
        s = ValidationSummary.from_entries(entries)
        self.assertEqual([(k.check, k.level) for k in s.skipped],
                         [("skeleton.naming", "error")])

    def test_round_trip_keeps_the_record(self):
        s = ValidationSummary.from_entries([
            CheckResultEntry(check="a", level="error", passed=False, skipped=True),
        ])
        restored = ValidationSummary.from_dict(json.loads(json.dumps(asdict(s))))
        self.assertEqual([k.check for k in restored.skipped], ["a"])
        self.assertTrue(restored.results[0].skipped)

    def test_manifest_without_the_field_still_reads(self):
        # 旧 manifest 没有这个键，解析不能炸。
        legacy = {
            "status": "passed",
            "errors": 0, "warnings": 0, "infos": 0,
            "results": [{"check": "a", "level": "info", "passed": True}],
        }
        s = ValidationSummary.from_dict(legacy)
        self.assertEqual(s.skipped, [])
        self.assertFalse(s.results[0].skipped)

    def test_skipped_must_not_be_a_mapping(self):
        with self.assertRaises(ValueError):
            ValidationSummary.from_dict({"skipped": {"check": "a"}})


class TestImportResultRigFields(unittest.TestCase):
    """首次交付建出的骨架要写进 result，卡片才报得出；旧 manifest 没这两键。"""

    def test_legacy_manifest_without_rig_keys_reads_empty(self):
        r = ImportResult.from_dict({"status": "success", "imported_clips": ["walk"]})
        self.assertEqual(r.skeleton_path, "")
        self.assertEqual(r.skeletal_mesh_path, "")
        self.assertEqual(r.skipped_clips, [])

    def test_round_trip_keeps_rig_paths(self):
        r = ImportResult(status="partial", imported_clips=["idle"],
                         skipped_clips=["walk"],
                         skeleton_path="/Game/Hero/Hero_Skeleton",
                         skeletal_mesh_path="/Game/Hero/Hero_SkeletalMesh")
        restored = ImportResult.from_dict(json.loads(json.dumps(asdict(r))))
        self.assertEqual(restored.skeleton_path, "/Game/Hero/Hero_Skeleton")
        self.assertEqual(restored.skeletal_mesh_path, "/Game/Hero/Hero_SkeletalMesh")
        self.assertEqual(restored.skipped_clips, ["walk"])

    def test_skipped_clips_must_be_a_list(self):
        with self.assertRaises(ValueError):
            ImportResult.from_dict({"status": "partial", "skipped_clips": "walk"})


class TestRoundTrip(unittest.TestCase):
    def test_write_then_read_roundtrip(self):
        original = _sample_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "manifest.json")  # sub dir must be auto-created
            written = write_manifest(original, path)
            self.assertTrue(os.path.isfile(written))

            loaded = read_manifest(written)

        self.assertEqual(loaded.version, original.version)
        self.assertEqual(loaded.source.maya_scene, "hero_anim.ma")
        self.assertEqual(loaded.source.preset, "ue_mannequin")
        self.assertEqual(loaded.convention.frame_rate, 30)
        self.assertEqual(len(loaded.clips), 2)
        self.assertEqual(loaded.clips[0].name, "idle")
        self.assertFalse(loaded.clips[0].root_motion)
        self.assertTrue(loaded.clips[1].root_motion)
        self.assertEqual(loaded.ue_destination.overwrite_policy, "rename")
        self.assertEqual(loaded.validation.status, "passed_with_warnings")
        self.assertEqual(loaded.validation.warnings, 1)
        self.assertEqual(loaded.validation.results[1].check, "skeleton.scale")
        self.assertTrue(loaded.validation.results[1].auto_fixable)
        self.assertEqual(loaded.result.status, "pending")

    def test_json_is_utf8_and_indented(self):
        m = _sample_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            write_manifest(m, path)
            with open(path, "r", encoding="utf-8") as fp:
                raw = fp.read()
        # Should be valid JSON with indentation.
        self.assertIn("\n  ", raw)
        json.loads(raw)  # parses without error

    def test_load_or_create_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nope.json")
            m = load_or_create(path)
            self.assertEqual(m.version, SCHEMA_VERSION)
            self.assertEqual(m.clips, [])

    def test_load_or_create_existing(self):
        m = _sample_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            write_manifest(m, path)
            loaded = load_or_create(path)
        self.assertEqual(loaded.source.maya_scene, m.source.maya_scene)

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fp:
                fp.write("{not valid json")
            with self.assertRaises(ValueError):
                read_manifest(path)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_manifest("/does/not/exist/manifest.json")


if __name__ == "__main__":
    unittest.main()
