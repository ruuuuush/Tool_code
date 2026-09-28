"""Tests for bone-role classification and the CLI argument split.

Neither needs Maya. Classification is pure string work, and the launcher
keeps its ``mp_core`` / ``mp_maya`` imports lazy precisely so it can be
imported — and its argument handling tested — outside Maya.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mp_core import (  # noqa: E402
    ROLE_BALL,
    ROLE_FOOT,
    ROLE_TOE_TIP,
    ROLE_UNKNOWN,
    FootInfo,
)
from mp_maya import classify_foot_bone, classify_role, classify_side  # noqa: E402
from launch_baseline_scan import _parse_argv, expand_paths  # noqa: E402


class TestRoleClassification(unittest.TestCase):
    def test_mixamo_names(self):
        self.assertEqual(classify_role("LeftFoot"), ROLE_FOOT)
        self.assertEqual(classify_role("LeftToeBase"), ROLE_BALL)
        self.assertEqual(classify_role("LeftToe_End"), ROLE_TOE_TIP)

    def test_ue_mannequin_names(self):
        self.assertEqual(classify_role("foot_l"), ROLE_FOOT)
        self.assertEqual(classify_role("ball_l"), ROLE_BALL)

    def test_toe_tip_is_not_swallowed_by_ball(self):
        # Regression: "toe_end" and "toebase" both contain "toe", so the
        # order of the pattern checks decides. A toe tip classified as a
        # ball would let its stance roll into the gate's distribution.
        for name in ("LeftToe_End", "mixamorig:RightToe_End", "toe_tip"):
            self.assertEqual(classify_role(name), ROLE_TOE_TIP)

    def test_unknown(self):
        self.assertEqual(classify_role("spine_01"), ROLE_UNKNOWN)


class TestSideClassification(unittest.TestCase):
    def test_mixamo_prefix_style(self):
        self.assertEqual(classify_side("LeftFoot"), "left")
        self.assertEqual(classify_side("RightToeBase"), "right")

    def test_ue_suffix_style(self):
        self.assertEqual(classify_side("foot_l"), "left")
        self.assertEqual(classify_side("ball_r"), "right")

    def test_ball_is_not_mistaken_for_a_left_suffix(self):
        self.assertEqual(classify_side("ball"), "")

    def test_no_side(self):
        self.assertEqual(classify_side("spine_01"), "")


class TestFootInfo(unittest.TestCase):
    def test_classify_foot_bone_combines_role_and_side(self):
        info = classify_foot_bone("|mixamorig:Hips|mixamorig:LeftLeg|mixamorig:LeftFoot")
        self.assertEqual(info.role, ROLE_FOOT)
        self.assertEqual(info.side, "left")
        self.assertEqual(info.label(), "left foot")

    def test_unknown_label(self):
        self.assertEqual(FootInfo().label(), ROLE_UNKNOWN)


class TestArgvParsing(unittest.TestCase):
    def test_paths_only(self):
        options = _parse_argv(["a.fbx", "b.fbx"])
        self.assertEqual(options.paths, ["a.fbx", "b.fbx"])
        self.assertIsNone(options.fps)
        self.assertFalse(options.calibrate)
        self.assertFalse(options.augment)
        self.assertIsNone(options.out_dir)

    def test_fps_flag_before_paths(self):
        options = _parse_argv(["--fps", "30", "a.fbx"])
        self.assertEqual(options.paths, ["a.fbx"])
        self.assertEqual(options.fps, 30.0)

    def test_fps_flag_between_paths(self):
        options = _parse_argv(["a.fbx", "--fps", "24", "b.fbx"])
        self.assertEqual(options.paths, ["a.fbx", "b.fbx"])
        self.assertEqual(options.fps, 24.0)

    def test_calibrate_flag(self):
        options = _parse_argv(["--calibrate", "a.fbx"])
        self.assertEqual(options.paths, ["a.fbx"])
        self.assertTrue(options.calibrate)

    def test_augment_flag_with_out_dir(self):
        options = _parse_argv(["--augment", "--out", "D:/out", "a.fbx"])
        self.assertTrue(options.augment)
        self.assertFalse(options.calibrate)
        self.assertEqual(options.out_dir, "D:/out")
        self.assertEqual(options.paths, ["a.fbx"])

    def test_report_flag(self):
        options = _parse_argv(["--report", "D:/out/report.html", "a.fbx"])
        self.assertEqual(options.report, "D:/out/report.html")
        self.assertEqual(options.paths, ["a.fbx"])

    def test_missing_flag_value_raises(self):
        with self.assertRaises(SystemExit):
            _parse_argv(["a.fbx", "--fps"])
        with self.assertRaises(SystemExit):
            _parse_argv(["a.fbx", "--out"])
        with self.assertRaises(SystemExit):
            _parse_argv(["a.fbx", "--report"])


class TestExpandPaths(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.dir = tempfile.mkdtemp()
        for name in ("b_walk.fbx", "a_run.FBX", "notes.txt"):
            with open(os.path.join(self.dir, name), "w") as handle:
                handle.write("x")
        # Exported variants in a subfolder must NOT be picked up: feeding
        # augmented output back in as source is the mistake to prevent.
        sub = os.path.join(self.dir, "aug")
        os.mkdir(sub)
        with open(os.path.join(sub, "c_variant.fbx"), "w") as handle:
            handle.write("x")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.dir, ignore_errors=True)

    def test_directory_expands_to_sorted_fbx_only(self):
        result = expand_paths([self.dir])
        self.assertEqual(
            [os.path.basename(p) for p in result], ["a_run.FBX", "b_walk.fbx"]
        )

    def test_subfolders_are_not_recursed(self):
        self.assertTrue(
            all("c_variant" not in path for path in expand_paths([self.dir]))
        )

    def test_plain_files_pass_through_in_order(self):
        result = expand_paths(["z.fbx", self.dir, "a.fbx"])
        self.assertEqual(result[0], "z.fbx")
        self.assertEqual(result[-1], "a.fbx")
        self.assertEqual(len(result), 4)


if __name__ == "__main__":
    unittest.main()
