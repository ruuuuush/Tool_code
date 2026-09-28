"""tests.test_ue_importer

Tests for the UE-side importer's pure-Python logic.

The actual FBX import / AnimSequence slicing requires the `unreal`
module (only available inside UE), so we test only the pure helpers
here: path math, frame-to-seconds conversion, overwrite policy,
ImportOutcome state, and asset-path listing.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# NOTE: `unreal` (our package) shadows UE's module name when imported from
# outside UE. We force-load our package by file path so the test does not
# depend on UE being installed.
import importlib.util
_pkg_init = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "unreal", "__init__.py",
)
_spec = importlib.util.spec_from_file_location("mtu_unreal", _pkg_init)
ue = importlib.util.module_from_spec(_spec)
sys.modules["mtu_unreal"] = ue
_spec.loader.exec_module(ue)  # type: ignore[union-attr]

from bridge.schema import Clip, Manifest, UEDestination, Convention, Source
from bridge.manifest import write_manifest


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

class TestUnrealPathJoin(unittest.TestCase):
    def test_simple_join(self):
        self.assertEqual(ue.unreal_path_join("/Game", "Animations", "Hero"),
                         "/Game/Animations/Hero")

    def test_handles_existing_slashes(self):
        self.assertEqual(ue.unreal_path_join("/Game/", "/Animations/", "Hero"),
                         "/Game/Animations/Hero")

    def test_collapses_double_slash(self):
        self.assertEqual(ue.unreal_path_join("/Game//Animations"), "/Game/Animations")

    def test_skips_empty(self):
        self.assertEqual(ue.unreal_path_join("/Game", "", "Hero"), "/Game/Hero")


class TestClipAssetPath(unittest.TestCase):
    def test_basic(self):
        dest = UEDestination(content_root="/Game/Animations/Hero")
        c = Clip(name="walk", start=1, end=30)
        self.assertEqual(ue.clip_asset_path(dest, c), "/Game/Animations/Hero/walk")

    def test_trailing_slash_normalised(self):
        dest = UEDestination(content_root="/Game/Animations/Hero/")
        c = Clip(name="idle", start=1, end=10)
        self.assertEqual(ue.clip_asset_path(dest, c), "/Game/Animations/Hero/idle")


class TestSkeletonAssetPath(unittest.TestCase):
    def test_explicit_path_wins(self):
        dest = UEDestination(content_root="/Game/X", skeleton_path="/Game/Shared/Sk")
        self.assertEqual(ue.skeleton_asset_path(dest, "hero"), "/Game/Shared/Sk")

    def test_fallback_synthesises_name(self):
        dest = UEDestination(content_root="/Game/Animations/Hero", skeleton_path="")
        self.assertEqual(
            ue.skeleton_asset_path(dest, "hero"),
            "/Game/Animations/Hero/hero_Skeleton",
        )


# ---------------------------------------------------------------------------
# Frame range -> seconds
# ---------------------------------------------------------------------------

class TestFrameRangeToSeconds(unittest.TestCase):
    def test_first_frame_starts_at_zero(self):
        start, end = ue.frame_range_to_seconds(1, 30, 30)
        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(end, 1.0)

    def test_later_clip_offset(self):
        # Clip [31..90] at 30 fps: start = 30/30 = 1.0s, 60 frames = 2.0s long
        start, end = ue.frame_range_to_seconds(31, 90, 30)
        self.assertAlmostEqual(start, 1.0)
        self.assertAlmostEqual(end, 3.0)

    def test_single_frame(self):
        start, end = ue.frame_range_to_seconds(5, 5, 30)
        self.assertAlmostEqual(start, 4 / 30)
        self.assertAlmostEqual(end, 5 / 30)

    def test_invalid_frame_rate(self):
        with self.assertRaises(ValueError):
            ue.frame_range_to_seconds(1, 10, 0)


# ---------------------------------------------------------------------------
# Overwrite policy
# ---------------------------------------------------------------------------

class TestResolveOverwriteName(unittest.TestCase):
    def test_create_when_absent(self):
        path, action = ue.resolve_overwrite_name("/Game/x/walk", "rename", lambda p: False)
        self.assertEqual(path, "/Game/x/walk")
        self.assertEqual(action, "create")

    def test_overwrite_policy(self):
        path, action = ue.resolve_overwrite_name("/Game/x/walk", "overwrite", lambda p: True)
        self.assertEqual(path, "/Game/x/walk")
        self.assertEqual(action, "overwrite")

    def test_skip_policy(self):
        path, action = ue.resolve_overwrite_name("/Game/x/walk", "skip", lambda p: True)
        self.assertEqual(path, "/Game/x/walk")
        self.assertEqual(action, "skip")

    def test_rename_finds_first_free(self):
        existing = {"/Game/x/walk", "/Game/x/walk_01", "/Game/x/walk_02"}
        path, action = ue.resolve_overwrite_name(
            "/Game/x/walk", "rename", lambda p: p in existing
        )
        self.assertEqual(path, "/Game/x/walk_03")
        self.assertEqual(action, "rename")

    def test_rename_first_free_when_only_original_exists(self):
        path, action = ue.resolve_overwrite_name(
            "/Game/x/walk", "rename", lambda p: p == "/Game/x/walk"
        )
        self.assertEqual(path, "/Game/x/walk_01")
        self.assertEqual(action, "rename")


# ---------------------------------------------------------------------------
# ImportOutcome aggregation
# ---------------------------------------------------------------------------

class TestImportOutcome(unittest.TestCase):
    def test_to_result_dict_success(self):
        outcome = ue.ImportOutcome(
            manifest_path="x.json",
            skeleton_asset_path="/Game/S",
            long_anim_path="/Game/L",
        )
        outcome.add(ue.ClipImportOutcome("idle", "/Game/idle", "create", True))
        outcome.add(ue.ClipImportOutcome("walk", "/Game/walk", "create", True))
        d = outcome.to_result_dict()
        self.assertEqual(d["status"], "success")
        self.assertEqual(sorted(d["imported_clips"]), ["idle", "walk"])
        self.assertEqual(d["errors"], [])

    def test_to_result_dict_partial(self):
        outcome = ue.ImportOutcome("x.json", "/Game/S", "/Game/L")
        outcome.add(ue.ClipImportOutcome("idle", "/Game/idle", "create", True))
        outcome.add(ue.ClipImportOutcome("walk", "/Game/walk", "skip", True, "policy"))
        d = outcome.to_result_dict()
        self.assertEqual(d["status"], "success")  # at least one succeeded
        self.assertIn("idle", d["imported_clips"])

    def test_to_result_dict_failed(self):
        outcome = ue.ImportOutcome("x.json", "/Game/S", "/Game/L")
        outcome.add(ue.ClipImportOutcome("idle", "/Game/idle", "failed", False, "boom"))
        d = outcome.to_result_dict()
        self.assertEqual(d["status"], "failed")
        self.assertIn("idle: boom", d["errors"])

    def test_to_result_dict_all_skipped_is_partial(self):
        outcome = ue.ImportOutcome("x.json", "/Game/S", "/Game/L")
        outcome.add(ue.ClipImportOutcome("idle", "/Game/idle", "skip", True))
        d = outcome.to_result_dict()
        # no successes and no failures -> status falls through to failed
        self.assertIn(d["status"], ("partial", "failed"))

    def test_to_result_dict_rig_fields_when_skeleton_created(self):
        outcome = ue.ImportOutcome("x.json", "/Game/Hero/Hero_Skeleton", "/Game/L",
                                   skeletal_mesh_path="/Game/Hero/Hero_SkeletalMesh",
                                   skeleton_created=True)
        outcome.add(ue.ClipImportOutcome("walk", "/Game/walk", "create", True))
        d = outcome.to_result_dict()
        self.assertEqual(d["skeleton_path"], "/Game/Hero/Hero_Skeleton")
        self.assertEqual(d["skeletal_mesh_path"], "/Game/Hero/Hero_SkeletalMesh")

    def test_to_result_dict_rig_fields_empty_when_skeleton_reused(self):
        outcome = ue.ImportOutcome("x.json", "/Game/Existing_Skeleton", "/Game/L")
        outcome.add(ue.ClipImportOutcome("walk", "/Game/walk", "create", True))
        d = outcome.to_result_dict()
        self.assertEqual(d["skeleton_path"], "")
        self.assertEqual(d["skeletal_mesh_path"], "")


class TestRevealAssets(unittest.TestCase):
    def test_no_unreal_module_does_not_raise(self):
        # Outside UE there is no `unreal` module; locating assets must skip silently.
        outcome = ue.ImportOutcome("x.json", "/Game/S", "/Game/L")
        outcome.add(ue.ClipImportOutcome("walk", "/Game/walk", "create", True))
        ue.reveal_assets(outcome)  # must not raise

    def test_empty_outcome_does_not_raise(self):
        ue.reveal_assets(ue.ImportOutcome("x.json", "", ""))


class TestEnvironmentRequirements(unittest.TestCase):
    def test_first_delivery_types_are_required(self):
        class FakeImportTypes:
            FBXIT_ANIMATION = object()
            FBXIT_SKELETAL_MESH = object()

        class FakeUnreal:
            AssetImportTask = object
            FbxImportUI = object
            FbxAnimSequenceImportData = object
            FbxSkeletalMeshImportData = object
            SkeletalMesh = object
            FBXImportType = FakeImportTypes
            FBXAnimationLengthImportType = type(
                "AnimationLength", (),
                {"FBXALIT_SET_RANGE": object(), "FBXALIT_EXPORTED_TIME": object()},
            )
            Int32Interval = object
            EditorAssetLibrary = object
            AssetToolsHelpers = object

        original_unreal = ue.importer._unreal
        original_interchange = ue.importer.interchange_fbx_enabled
        original_disable = ue.importer.disable_interchange_fbx
        try:
            ue.importer._unreal = lambda: FakeUnreal
            ue.importer.interchange_fbx_enabled = lambda: False
            ue.importer.disable_interchange_fbx = lambda: True
            self.assertEqual(ue.importer.check_environment(), [])
            del FakeUnreal.FbxSkeletalMeshImportData
            problems = ue.importer.check_environment()
            self.assertIn("unreal.FbxSkeletalMeshImportData is missing in this UE build", problems)
        finally:
            ue.importer._unreal = original_unreal
            ue.importer.interchange_fbx_enabled = original_interchange
            ue.importer.disable_interchange_fbx = original_disable


# ---------------------------------------------------------------------------
# list_expected_asset_paths (end-to-end-ish, with a manifest on disk)
# ---------------------------------------------------------------------------

class TestDefaultMeshAssetName(unittest.TestCase):
    """First-delivery naming: the mesh should read as a pair with its skeleton."""

    def test_derives_from_skeleton_path(self):
        self.assertEqual(
            ue.default_mesh_asset_name("D:/x/walk.fbx", "/Game/Chars/Hero_Skeleton"),
            "Hero",
        )

    def test_handles_lowercase_suffix(self):
        self.assertEqual(
            ue.default_mesh_asset_name("D:/x/walk.fbx", "/Game/Chars/Hero_skeleton"),
            "Hero",
        )

    def test_keeps_name_without_suffix(self):
        self.assertEqual(
            ue.default_mesh_asset_name("D:/x/walk.fbx", "/Game/Chars/HeroRig"),
            "HeroRig",
        )

    def test_falls_back_to_fbx_name(self):
        self.assertEqual(
            ue.default_mesh_asset_name("D:/exports/hero_walk.fbx", ""),
            "hero_walk",
        )

    def test_never_returns_empty(self):
        self.assertTrue(ue.default_mesh_asset_name("", ""))


class TestExpectedAssetPaths(unittest.TestCase):
    def _write_manifest(self, tmp: str) -> str:
        m = Manifest.new(
            source=Source(maya_scene="hero", preset="ue_mannequin", skeleton_root="root"),
            convention=Convention(),
            clips=[Clip("idle", 1, 10, False), Clip("walk", 11, 30, True)],
            fbx_path=os.path.join(tmp, "hero.fbx"),
            ue_destination=UEDestination(
                content_root="/Game/Animations/Hero",
                skeleton_path="/Game/Animations/Hero/Hero_Skeleton",
            ),
        )
        path = os.path.join(tmp, "manifest.json")
        write_manifest(m, path)
        return path

    def test_includes_skeleton_and_all_clips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_manifest(tmp)
            paths = ue.list_expected_asset_paths(path)
        self.assertIn("/Game/Animations/Hero/Hero_Skeleton", paths)
        self.assertIn("/Game/Animations/Hero/idle", paths)
        self.assertIn("/Game/Animations/Hero/walk", paths)
        self.assertEqual(len(paths), 3)


if __name__ == "__main__":
    unittest.main()
