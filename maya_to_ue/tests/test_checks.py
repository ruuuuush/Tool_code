"""tests.test_checks

Tests for the validator framework and the shipped checks.

The key design property under test: every check receives a CheckContext
and never calls maya.cmds directly during check(). This means all check
LOGIC can be tested in plain Python with a hand-built context — no Maya
session required. Fixes DO call maya.cmds (lazily, inside fix()), so
those are tested separately / skipped here.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge.schema import Clip
from mtu_maya.checks import (
    CheckContext,
    CheckResult,
    RunReport,
    ValidatorRegistry,
    default_registry,
    register_validator,
    run_all_checks,
)
from mtu_maya.core.preset_loader import SkeletonPreset, NamingConvention


def _ctx(**overrides) -> CheckContext:
    """Build a minimal valid context; tests override what they need.

    The default fbx_path points into a temp dir so export.path_valid
    passes; tests that need to check path logic override fbx_path.
    """
    _tmp = _ctx._tmp  # type: ignore[attr-defined]
    base = dict(
        scene_units="cm",
        scene_up_axis="z",
        scene_fps=30.0,
        timeline_start=1,
        timeline_end=120,
        joints=["|root", "|root|spine_01"],
        root_joint="|root",
        joint_scales={"|root": (1.0, 1.0, 1.0), "|root|spine_01": (1.0, 1.0, 1.0)},
        fbx_plugin_loaded=True,
        fbx_path=os.path.join(_tmp, "hero.fbx"),
        skeleton_root_selected="|root",
        ue_content_root="/Game/Animations/Hero",
        ue_skeleton_path="/Game/Animations/Hero/Hero_Skeleton",
        skeleton_roots=["|root"],
        skeleton_height=175.0,
        unanimated_joints=[],
        clips=[Clip(name="idle", start=1, end=30, root_motion=False)],
    )
    base.update(overrides)
    return CheckContext(**base)


# Shared temp dir for the whole test module so _ctx defaults to a real path.
_ctx._tmp = tempfile.mkdtemp(prefix="maya_to_ue_tests_")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Registry mechanics
# ---------------------------------------------------------------------------

class TestRegistry(unittest.TestCase):
    def test_default_registry_has_all_categories(self):
        reg = default_registry()
        cats = reg.categories()
        self.assertEqual(cats, ["scene", "skeleton", "mesh", "anim", "export"])

    def test_expected_validator_ids_present(self):
        reg = default_registry()
        expected = {
            "scene.unit", "scene.up_axis", "scene.fps", "scene.timeline_range",
            "skeleton.root_exists", "skeleton.naming", "skeleton.scale",
            "skeleton.single_root", "skeleton.duplicate_names", "skeleton.segment_scale",
            "skeleton.real_world_scale", "skeleton.bind_pose",
            "mesh.history", "mesh.transforms", "mesh.uv", "mesh.skin_weight",
            "anim.curves_on_expected", "anim.stray_layers", "anim.clip_ranges_valid",
            "anim.clip_overlap", "anim.keys_in_clip_range", "anim.skeleton_animated",
            "anim.root_motion_match", "anim.keys_dense",
            "export.fbx_plugin", "export.path_valid", "export.naming_legal",
            "export.ue_path_valid", "export.skeleton_root_set",
        }
        present = {v.id for v in reg.all()}
        missing = expected - present
        self.assertFalse(missing, f"missing validator ids: {missing}")

    def test_validator_ids_unique(self):
        reg = default_registry()
        ids = [v.id for v in reg.all()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_by_category_groups_correctly(self):
        reg = default_registry()
        groups = reg.by_category()
        self.assertEqual(len(groups["scene"]), 4)
        self.assertEqual(len(groups["skeleton"]), 8)
        self.assertEqual(len(groups["mesh"]), 4)
        self.assertEqual(len(groups["anim"]), 8)
        self.assertEqual(len(groups["export"]), 5)

    def test_duplicate_registration_replaces(self):
        reg = ValidatorRegistry()
        from mtu_maya.checks.registry import BaseValidator

        class V1(BaseValidator):
            id = "dup"
            category = "x"
            level = "info"
            def check(self, ctx): return CheckResult("dup", "x", "info", True)
        reg.register(V1())

        # Re-registering the same id must REPLACE, not raise. This is what makes
        # importlib.reload() safe inside Maya (reloading a check module re-runs
        # @register_validator; raising here previously left the registry broken
        # and the UI's check list empty).
        class V2(BaseValidator):
            id = "dup"
            category = "x"
            level = "info"
            def check(self, ctx): return CheckResult("dup", "x", "info", True)
        reg.register(V2())  # should NOT raise

        self.assertIsInstance(reg.require("dup"), V2)


# ---------------------------------------------------------------------------
# Scene checks
# ---------------------------------------------------------------------------

class TestSceneChecks(unittest.TestCase):
    def test_unit_pass(self):
        r = run_all_checks(_ctx(scene_units="cm"))
        unit = next(x for x in r.results if x.check_id == "scene.unit")
        self.assertTrue(unit.passed)

    def test_unit_fail(self):
        r = run_all_checks(_ctx(scene_units="m"))
        unit = next(x for x in r.results if x.check_id == "scene.unit")
        self.assertFalse(unit.passed)
        self.assertEqual(unit.level, "error")

    def test_up_axis_is_informational(self):
        r = run_all_checks(_ctx(scene_up_axis="y"))
        up = next(x for x in r.results if x.check_id == "scene.up_axis")
        self.assertTrue(up.passed)
        self.assertEqual(up.level, "info")

    def test_fps_fail(self):
        r = run_all_checks(_ctx(scene_fps=24.0))
        fps = next(x for x in r.results if x.check_id == "scene.fps")
        self.assertFalse(fps.passed)
        self.assertEqual(fps.level, "error")

    def test_timeline_single_frame_warns(self):
        r = run_all_checks(_ctx(timeline_start=10, timeline_end=10))
        tr = next(x for x in r.results if x.check_id == "scene.timeline_range")
        self.assertFalse(tr.passed)
        self.assertEqual(tr.level, "warning")

    def test_timeline_inverted_warns(self):
        r = run_all_checks(_ctx(timeline_start=50, timeline_end=10))
        tr = next(x for x in r.results if x.check_id == "scene.timeline_range")
        self.assertFalse(tr.passed)


# ---------------------------------------------------------------------------
# Skeleton checks
# ---------------------------------------------------------------------------

class TestSkeletonChecks(unittest.TestCase):
    def test_root_missing_fails(self):
        r = run_all_checks(_ctx(joints=[], root_joint=None, skeleton_root_selected=None))
        root = next(x for x in r.results if x.check_id == "skeleton.root_exists")
        self.assertFalse(root.passed)

    def test_naming_no_preset_passes(self):
        r = run_all_checks(_ctx(preset=None))
        n = next(x for x in r.results if x.check_id == "skeleton.naming")
        self.assertTrue(n.passed)

    def test_naming_with_valid_preset_passes(self):
        preset = SkeletonPreset(
            id="ue_mannequin", display_name="UE", skeleton_type="humanoid",
            root_bone="root", naming=NamingConvention(naming_regex=r"^[a-z]+(_[a-z0-9]+)*(_l|_r)?$"),
        )
        r = run_all_checks(_ctx(preset=preset, joints=["|root", "|root|spine_01", "|root|thigh_l"]))
        n = next(x for x in r.results if x.check_id == "skeleton.naming")
        self.assertTrue(n.passed)

    def test_naming_with_bad_name_warns(self):
        preset = SkeletonPreset(
            id="ue_mannequin", display_name="UE", skeleton_type="humanoid",
            root_bone="root", naming=NamingConvention(naming_regex=r"^[a-z]+(_[a-z0-9]+)*(_l|_r)?$"),
        )
        r = run_all_checks(_ctx(preset=preset, joints=["|root", "|Hips"]))
        n = next(x for x in r.results if x.check_id == "skeleton.naming")
        self.assertFalse(n.passed)
        self.assertEqual(n.level, "warning")
        self.assertIn("Hips", n.details)

    def test_scale_off_unit_warns(self):
        r = run_all_checks(_ctx(joint_scales={"|root": (1.0, 1.0, 1.0), "|spine": (1.02, 1.0, 1.0)}))
        s = next(x for x in r.results if x.check_id == "skeleton.scale")
        self.assertFalse(s.passed)
        self.assertFalse(s.auto_fixable)
        self.assertTrue(any("spine" in d for d in s.details))

    def test_scale_within_tolerance_passes(self):
        r = run_all_checks(_ctx(joint_scales={"|root": (1.0001, 1.0001, 1.0001)}))
        s = next(x for x in r.results if x.check_id == "skeleton.scale")
        self.assertTrue(s.passed)


# ---------------------------------------------------------------------------
# Mesh checks (skipped when no mesh)
# ---------------------------------------------------------------------------

class TestMeshChecks(unittest.TestCase):
    def test_no_mesh_all_pass(self):
        r = run_all_checks(_ctx(has_mesh=False))
        for cid in ("mesh.history", "mesh.transforms", "mesh.uv", "mesh.skin_weight"):
            res = next(x for x in r.results if x.check_id == cid)
            self.assertTrue(res.passed, f"{cid} should pass when no mesh")

    def test_unskinned_mesh_with_history_flagged(self):
        r = run_all_checks(_ctx(
            has_mesh=True,
            mesh_history={"|prop": False},
            mesh_frozen={"|prop": True},
            mesh_has_uvs={"|prop": True},
            mesh_skin_normalized={"|prop": True},
            mesh_skinned={"|prop": False},
        ))
        h = next(x for x in r.results if x.check_id == "mesh.history")
        self.assertFalse(h.passed)

    def test_skinned_mesh_history_never_flagged(self):
        # Deformer history IS the rig — flagging it would invite users to
        # destroy their own bind. Skinned meshes must always pass.
        r = run_all_checks(_ctx(
            has_mesh=True,
            mesh_history={"|body": False},
            mesh_frozen={"|body": False},
            mesh_has_uvs={"|body": True},
            mesh_skin_normalized={"|body": True},
            mesh_skinned={"|body": True},
        ))
        h = next(x for x in r.results if x.check_id == "mesh.history")
        t = next(x for x in r.results if x.check_id == "mesh.transforms")
        self.assertTrue(h.passed)
        self.assertTrue(t.passed)

    def test_mesh_checks_are_not_auto_fixable(self):
        # Auto-fixing history/freeze on a character is destructive; both
        # checks must stay advisory only.
        r = run_all_checks(_ctx(
            has_mesh=True,
            mesh_history={"|prop": False},
            mesh_frozen={"|prop": False},
            mesh_has_uvs={"|prop": True},
            mesh_skin_normalized={"|prop": True},
            mesh_skinned={"|prop": False},
        ))
        for cid in ("mesh.history", "mesh.transforms"):
            res = next(x for x in r.results if x.check_id == cid)
            self.assertFalse(res.auto_fixable, f"{cid} must not be auto-fixable")

    def test_transforms_not_frozen_warns(self):
        r = run_all_checks(_ctx(
            has_mesh=True,
            mesh_history={"|prop": True},
            mesh_frozen={"|prop": False},
            mesh_has_uvs={"|prop": True},
            mesh_skin_normalized={"|prop": True},
            mesh_skinned={"|prop": False},
        ))
        t = next(x for x in r.results if x.check_id == "mesh.transforms")
        self.assertFalse(t.passed)

    def test_no_uvs_warns_not_fixable(self):
        r = run_all_checks(_ctx(
            has_mesh=True,
            mesh_history={"|body": True},
            mesh_frozen={"|body": True},
            mesh_has_uvs={"|body": False},
            mesh_skin_normalized={"|body": True},
        ))
        u = next(x for x in r.results if x.check_id == "mesh.uv")
        self.assertFalse(u.passed)
        self.assertFalse(u.auto_fixable)

    def test_mesh_skin_weight_is_not_auto_fixable(self):
        r = run_all_checks(_ctx(
            has_mesh=True,
            mesh_history={"|body": True},
            mesh_frozen={"|body": True},
            mesh_has_uvs={"|body": True},
            mesh_skin_normalized={"|body": False},
            mesh_skinned={"|body": True},
        ))
        weights = next(x for x in r.results if x.check_id == "mesh.skin_weight")
        self.assertFalse(weights.passed)
        self.assertFalse(weights.auto_fixable)


# ---------------------------------------------------------------------------
# Anim checks
# ---------------------------------------------------------------------------

class TestAnimChecks(unittest.TestCase):
    def test_no_clips_fails(self):
        r = run_all_checks(_ctx(clips=[]))
        c = next(x for x in r.results if x.check_id == "anim.clip_ranges_valid")
        self.assertFalse(c.passed)
        self.assertEqual(c.level, "error")

    def test_clip_end_before_start_fails(self):
        r = run_all_checks(_ctx(clips=[Clip(name="x", start=30, end=10)]))
        c = next(x for x in r.results if x.check_id == "anim.clip_ranges_valid")
        self.assertFalse(c.passed)

    def test_clip_outside_timeline_fails(self):
        r = run_all_checks(_ctx(timeline_end=100, clips=[Clip(name="x", start=1, end=200)]))
        c = next(x for x in r.results if x.check_id == "anim.clip_ranges_valid")
        self.assertFalse(c.passed)

    def test_locomotion_without_root_motion_info(self):
        r = run_all_checks(_ctx(clips=[Clip(name="walk", start=1, end=30, root_motion=False)]))
        rm = next(x for x in r.results if x.check_id == "anim.root_motion_match")
        self.assertFalse(rm.passed)
        self.assertEqual(rm.level, "info")  # info, not error

    def test_locomotion_with_root_motion_passes(self):
        r = run_all_checks(_ctx(clips=[Clip(name="run", start=1, end=30, root_motion=True)]))
        rm = next(x for x in r.results if x.check_id == "anim.root_motion_match")
        self.assertTrue(rm.passed)

    def test_stray_layers_info(self):
        r = run_all_checks(_ctx(stray_anim_layers=["AnimLayer1"]))
        s = next(x for x in r.results if x.check_id == "anim.stray_layers")
        self.assertFalse(s.passed)
        self.assertEqual(s.level, "info")

    def test_overlapping_clips_flagged(self):
        r = run_all_checks(_ctx(clips=[
            Clip(name="idle", start=1, end=30),
            Clip(name="walk", start=30, end=60),
        ]))
        o = next(x for x in r.results if x.check_id == "anim.clip_overlap")
        self.assertFalse(o.passed)

    def test_adjacent_clips_do_not_overlap(self):
        r = run_all_checks(_ctx(clips=[
            Clip(name="idle", start=1, end=30),
            Clip(name="walk", start=31, end=60),
        ]))
        o = next(x for x in r.results if x.check_id == "anim.clip_overlap")
        self.assertTrue(o.passed)

    def test_keys_outside_clip_range_flagged(self):
        r = run_all_checks(_ctx(
            clips=[Clip(name="idle", start=1, end=30)],
            keys_outside_clip_range=["|root|spine_01"],
        ))
        k = next(x for x in r.results if x.check_id == "anim.keys_in_clip_range")
        self.assertFalse(k.passed)

    def test_skeleton_without_animation_is_error(self):
        r = run_all_checks(_ctx(
            joints=["|root", "|root|spine_01"],
            unanimated_joints=["|root", "|root|spine_01"],
        ))
        a = next(x for x in r.results if x.check_id == "anim.skeleton_animated")
        self.assertFalse(a.passed)
        self.assertEqual(a.level, "error")

    def test_partially_animated_skeleton_passes(self):
        r = run_all_checks(_ctx(
            joints=["|root", "|root|spine_01"],
            unanimated_joints=["|root|spine_01"],
        ))
        a = next(x for x in r.results if x.check_id == "anim.skeleton_animated")
        self.assertTrue(a.passed)


# ---------------------------------------------------------------------------
# Skeleton topology checks (the ones that actually break UE imports)
# ---------------------------------------------------------------------------

class TestSkeletonTopologyChecks(unittest.TestCase):
    def test_multiple_roots_is_error(self):
        r = run_all_checks(_ctx(skeleton_roots=["|rootA", "|rootB"]))
        s = next(x for x in r.results if x.check_id == "skeleton.single_root")
        self.assertFalse(s.passed)
        self.assertEqual(s.level, "error")

    def test_single_root_passes(self):
        r = run_all_checks(_ctx(skeleton_roots=["|root"]))
        s = next(x for x in r.results if x.check_id == "skeleton.single_root")
        self.assertTrue(s.passed)

    def test_duplicate_joint_names_is_error(self):
        r = run_all_checks(_ctx(duplicate_joint_names=["spine_01"]))
        d = next(x for x in r.results if x.check_id == "skeleton.duplicate_names")
        self.assertFalse(d.passed)
        self.assertEqual(d.level, "error")

    def test_segment_scale_compensate_flagged_without_auto_fix(self):
        r = run_all_checks(_ctx(segment_scale_compensate=["|root|spine_01"]))
        s = next(x for x in r.results if x.check_id == "skeleton.segment_scale")
        self.assertFalse(s.passed)
        self.assertFalse(s.auto_fixable)

    def test_metre_scale_character_flagged(self):
        # A 3.58 unit tall skeleton in a cm scene = authored in metres.
        r = run_all_checks(_ctx(skeleton_height=3.58))
        s = next(x for x in r.results if x.check_id == "skeleton.real_world_scale")
        self.assertFalse(s.passed)

    def test_human_scale_character_passes(self):
        r = run_all_checks(_ctx(skeleton_height=178.0))
        s = next(x for x in r.results if x.check_id == "skeleton.real_world_scale")
        self.assertTrue(s.passed)

    def test_oversized_character_flagged(self):
        r = run_all_checks(_ctx(skeleton_height=50000.0))
        s = next(x for x in r.results if x.check_id == "skeleton.real_world_scale")
        self.assertFalse(s.passed)

    def test_bind_pose_skipped_when_not_shipping_rig(self):
        # No rig in the FBX means no Skeleton gets created, so the reference
        # pose is irrelevant.
        r = run_all_checks(_ctx(include_rig=False, tpose_arm_deviation=80.0))
        b = next(x for x in r.results if x.check_id == "skeleton.bind_pose")
        self.assertTrue(b.passed)

    def test_bind_pose_flagged_when_shipping_non_tpose_rig(self):
        r = run_all_checks(_ctx(include_rig=True, tpose_arm_deviation=70.0))
        b = next(x for x in r.results if x.check_id == "skeleton.bind_pose")
        self.assertFalse(b.passed)

    def test_bind_pose_passes_for_tpose(self):
        r = run_all_checks(_ctx(include_rig=True, tpose_arm_deviation=4.0))
        b = next(x for x in r.results if x.check_id == "skeleton.bind_pose")
        self.assertTrue(b.passed)

    def test_bind_pose_skipped_when_unmeasurable(self):
        r = run_all_checks(_ctx(include_rig=True, tpose_arm_deviation=-1.0))
        b = next(x for x in r.results if x.check_id == "skeleton.bind_pose")
        self.assertTrue(b.passed)


# ---------------------------------------------------------------------------
# Export checks
# ---------------------------------------------------------------------------

class TestExportChecks(unittest.TestCase):
    def test_fbx_plugin_missing_fails(self):
        r = run_all_checks(_ctx(fbx_plugin_loaded=False))
        p = next(x for x in r.results if x.check_id == "export.fbx_plugin")
        self.assertFalse(p.passed)

    def test_path_empty_fails(self):
        r = run_all_checks(_ctx(fbx_path=""))
        p = next(x for x in r.results if x.check_id == "export.path_valid")
        self.assertFalse(p.passed)

    def test_path_wrong_extension_fails(self):
        r = run_all_checks(_ctx(fbx_path="./exports/hero.obj"))
        p = next(x for x in r.results if x.check_id == "export.path_valid")
        self.assertFalse(p.passed)

    def test_path_valid_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_all_checks(_ctx(fbx_path=os.path.join(tmp, "hero.fbx")))
            p = next(x for x in r.results if x.check_id == "export.path_valid")
            self.assertTrue(p.passed)

    def test_illegal_clip_name_fails(self):
        r = run_all_checks(_ctx(clips=[Clip(name="walk/forward", start=1, end=10)]))
        n = next(x for x in r.results if x.check_id == "export.naming_legal")
        self.assertFalse(n.passed)
        self.assertEqual(n.level, "error")

    def test_legal_clip_name_passes(self):
        r = run_all_checks(_ctx(clips=[Clip(name="walk_forward", start=1, end=10)]))
        n = next(x for x in r.results if x.check_id == "export.naming_legal")
        self.assertTrue(n.passed)

    def test_no_root_selected_fails(self):
        r = run_all_checks(_ctx(root_joint=None, skeleton_root_selected=None))
        s = next(x for x in r.results if x.check_id == "export.skeleton_root_set")
        self.assertFalse(s.passed)


class TestExportUEPathCheck(unittest.TestCase):
    """UE paths must be validated here, not by the manifest writer.

    An invalid path used to export the FBX fine and then fail silently when
    the manifest refused to serialise.
    """

    def _result(self, **overrides):
        r = run_all_checks(_ctx(**overrides))
        return next(x for x in r.results if x.check_id == "export.ue_path_valid")

    def test_content_root_without_game_prefix_fails(self):
        p = self._result(ue_content_root="Game/Animations")
        self.assertFalse(p.passed)
        self.assertEqual(p.level, "error")
        self.assertIn("/Game", p.message)

    def test_content_root_error_blocks_export(self):
        r = run_all_checks(_ctx(ue_content_root="/Content/Anim"))
        self.assertFalse(r.can_export())

    def test_empty_content_root_fails(self):
        self.assertFalse(self._result(ue_content_root="").passed)

    def test_empty_skeleton_without_rig_export_fails(self):
        p = self._result(ue_skeleton_path="", create_skeleton_if_missing=False)
        self.assertFalse(p.passed)
        self.assertIn("同时导出模型", p.message)

    def test_empty_skeleton_with_rig_export_passes(self):
        p = self._result(ue_skeleton_path="", create_skeleton_if_missing=True)
        self.assertTrue(p.passed)

    def test_skeleton_path_without_game_prefix_fails(self):
        p = self._result(ue_skeleton_path="Hero_Skeleton")
        self.assertFalse(p.passed)

    def test_valid_paths_pass(self):
        self.assertTrue(self._result().passed)

    def test_all_problems_listed_in_details(self):
        p = self._result(ue_content_root="Animations", ue_skeleton_path="Hero_Skeleton")
        self.assertEqual(len(p.details), 2)

    def test_passing_context_serialises_as_manifest(self):
        # The whole point of this check: what it accepts, the manifest accepts.
        from bridge.schema import Convention, Manifest, Source, UEDestination

        ctx = _ctx()
        manifest = Manifest.new(
            source=Source(maya_scene="hero", preset="custom", skeleton_root="|root"),
            convention=Convention(up_axis=ctx.scene_up_axis, unit=ctx.scene_units),
            clips=list(ctx.clips),
            fbx_path=ctx.fbx_path,
            ue_destination=UEDestination(
                content_root=ctx.ue_content_root,
                skeleton_path=ctx.ue_skeleton_path,
            ),
        )
        manifest.validate()  # must not raise


# ---------------------------------------------------------------------------
# Aggregation / RunReport
# ---------------------------------------------------------------------------

class TestRunReport(unittest.TestCase):
    def test_clean_scene_passes(self):
        r = run_all_checks(_ctx())
        self.assertEqual(r.status, "passed", r.errors)
        self.assertTrue(r.can_export())
        self.assertEqual(r.total, len(default_registry()))
        self.assertEqual(r.passed_count, len(default_registry()))

    def test_error_blocks_export(self):
        r = run_all_checks(_ctx(scene_units="m"))  # scene.unit fails
        self.assertEqual(r.status, "failed")
        self.assertFalse(r.can_export())
        self.assertGreaterEqual(len(r.errors), 1)

    def test_warning_does_not_block(self):
        r = run_all_checks(_ctx(joint_scales={"|root": (1.5, 1.0, 1.0)}))  # scale warns
        self.assertEqual(r.status, "passed_with_warnings")
        self.assertTrue(r.can_export())
        self.assertGreaterEqual(len(r.warnings), 1)

    def test_to_summary_matches_counts(self):
        r = run_all_checks(_ctx(scene_units="m", joint_scales={"|root": (2.0, 1.0, 1.0)}))
        s = r.to_summary()
        self.assertEqual(s.errors, len(r.errors))
        self.assertEqual(s.warnings, len(r.warnings))
        self.assertEqual(s.infos, len(r.infos))
        self.assertEqual(s.status, "failed")
        self.assertEqual(len(s.results), r.total)

    def test_buggy_check_does_not_abort_run(self):
        # Register a validator that raises; the runner should convert it to
        # a failed error-level result and continue.
        from mtu_maya.checks.registry import BaseValidator

        class BoomValidator(BaseValidator):
            id = "test.boom"
            category = "test"
            level = "info"
            def check(self, ctx):
                raise RuntimeError("boom")
            def fix(self, ctx):
                pass

        reg = ValidatorRegistry()
        reg.register(BoomValidator())
        report = run_all_checks(_ctx(), registry=reg)
        self.assertEqual(report.total, 1)
        self.assertFalse(report.results[0].passed)
        self.assertIn("RuntimeError", report.results[0].message)


class TestSkippedChecks(unittest.TestCase):
    """跳过是给门禁开的口子——它必须真的不跑，而且必须留痕。"""

    def _counting_registry(self):
        from mtu_maya.checks.registry import BaseValidator, CheckResult

        calls = []

        class Boom(BaseValidator):
            id = "test.boom"
            category = "test"
            level = "error"

            def check(self, ctx):
                calls.append(self.id)
                return CheckResult(self.id, self.category, self.level, passed=False,
                                   message="always fails")

            def fix(self, ctx):
                pass

        class Fine(BaseValidator):
            id = "test.fine"
            category = "test"
            level = "info"

            def check(self, ctx):
                calls.append(self.id)
                return CheckResult(self.id, self.category, self.level, passed=True)

            def fix(self, ctx):
                pass

        reg = ValidatorRegistry()
        reg.register(Boom())
        reg.register(Fine())
        return reg, calls

    def test_skipped_validator_never_runs(self):
        reg, calls = self._counting_registry()
        run_all_checks(_ctx(), registry=reg, skipped={"test.boom"})
        self.assertEqual(calls, ["test.fine"])

    def test_skipped_error_stops_blocking_export(self):
        reg, _ = self._counting_registry()
        blocked = run_all_checks(_ctx(), registry=reg)
        self.assertFalse(blocked.can_export())

        allowed = run_all_checks(_ctx(), registry=reg, skipped={"test.boom"})
        self.assertTrue(allowed.can_export())
        self.assertEqual(allowed.status, "passed")

    def test_skipped_is_neither_passed_nor_failed(self):
        reg, _ = self._counting_registry()
        r = run_all_checks(_ctx(), registry=reg, skipped={"test.boom", "test.fine"})
        self.assertEqual(r.total, 2)
        self.assertEqual(r.passed_count, 0)
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.skipped), 2)

    def test_skipped_entries_reach_the_summary(self):
        reg, _ = self._counting_registry()
        s = run_all_checks(_ctx(), registry=reg, skipped={"test.boom"}).to_summary()
        self.assertEqual([(k.check, k.level) for k in s.skipped], [("test.boom", "error")])
        # 明细行也标出来，别让它混在"未通过"里
        entry = next(r for r in s.results if r.check == "test.boom")
        self.assertTrue(entry.skipped)
        self.assertFalse(entry.passed)

    def test_nothing_skipped_leaves_no_record(self):
        reg, _ = self._counting_registry()
        self.assertEqual(run_all_checks(_ctx(), registry=reg).to_summary().skipped, [])

    def test_fix_all_warnings_leaves_skipped_alone(self):
        from mtu_maya.checks.registry import BaseValidator, CheckResult, fix_all_warnings

        fixed_by = []

        class Fixable(BaseValidator):
            id = "test.fixable"
            category = "test"
            level = "warning"
            auto_fixable = True

            def check(self, ctx):
                return CheckResult(self.id, self.category, self.level, passed=False)

            def fix(self, ctx):
                fixed_by.append(self.id)

        reg = ValidatorRegistry()
        reg.register(Fixable())
        self.assertEqual(fix_all_warnings(_ctx(), registry=reg, skipped={"test.fixable"}), [])
        self.assertEqual(fixed_by, [])
        self.assertEqual(fix_all_warnings(_ctx(), registry=reg), ["test.fixable"])


class TestDenseKeysCheck(unittest.TestCase):
    """逐帧烘焙曲线该被点名；开了抽稀就别再报。"""

    def _check(self, ctx):
        reg = default_registry()
        validator = next(v for v in reg.all() if v.id == "anim.keys_dense")
        return validator.check(ctx)

    def test_dense_curve_without_thinning_warns(self):
        r = self._check(_ctx(dense_curves=["|root_translateY", "|root|spine_01_translateY"]))
        self.assertFalse(r.passed)
        self.assertEqual(r.level, "warning")
        self.assertIn("|root_translateY", r.message)

    def test_dense_curve_with_thinning_passes(self):
        r = self._check(_ctx(dense_curves=["|root_translateY"], thinning_level="medium"))
        self.assertTrue(r.passed)

    def test_sparse_curves_pass(self):
        r = self._check(_ctx(dense_curves=[]))
        self.assertTrue(r.passed)


if __name__ == "__main__":
    unittest.main()
