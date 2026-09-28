"""Tests for the augmentation decision layer and the quality gate.

Both are pure: mirroring is name arithmetic plus one reflection matrix,
and the gate is threshold comparison. Neither needs Maya.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mp_core import (  # noqa: E402
    BaselineScan,
    ClipBaseline,
    FootReport,
    ThresholdSuggestion,
    Thresholds,
    evaluate,
    evaluate_against_source,
    format_gate_report,
    is_mirrorable,
    lateral_index,
    mirror_diagonal,
    mirror_map,
    opposite_name,
    retime_source_time,
    warped_frame_count,
    warped_range,
)


# ---------------------------------------------------------------------------
# Mirror planning
# ---------------------------------------------------------------------------


class TestOppositeName(unittest.TestCase):
    def test_mixamo_prefix_style(self):
        self.assertEqual(opposite_name("LeftFoot"), "RightFoot")
        self.assertEqual(opposite_name("RightUpLeg"), "LeftUpLeg")

    def test_ue_suffix_style(self):
        self.assertEqual(opposite_name("foot_l"), "foot_r")
        self.assertEqual(opposite_name("ball_r"), "ball_l")

    def test_centre_bone_has_no_side(self):
        self.assertIsNone(opposite_name("Hips"))
        self.assertIsNone(opposite_name("Spine1"))


class TestMirrorMap(unittest.TestCase):
    SKELETON = [
        "|Arm:Hips",
        "|Arm:Spine",
        "|Arm:LeftUpLeg",
        "|Arm:RightUpLeg",
        "|Arm:LeftFoot",
        "|Arm:RightFoot",
    ]

    def test_pairs_sides_and_self_maps_centre(self):
        mapping = mirror_map(self.SKELETON)
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["|Arm:LeftFoot"], "|Arm:RightFoot")
        self.assertEqual(mapping["|Arm:Hips"], "|Arm:Hips")

    def test_is_an_involution(self):
        mapping = mirror_map(self.SKELETON)
        for bone, partner in mapping.items():
            self.assertEqual(mapping[partner], bone)

    def test_missing_opposite_refuses_the_whole_skeleton(self):
        # Half a mirror looks fine in a still and is wrong in motion.
        partial = [b for b in self.SKELETON if b != "|Arm:RightFoot"]
        self.assertIsNone(mirror_map(partial))
        self.assertFalse(is_mirrorable(partial))

    def test_ambiguous_short_names_refuse(self):
        self.assertIsNone(mirror_map(["|A:Hips", "|B:Hips"]))


class TestMirrorGeometry(unittest.TestCase):
    def test_lateral_axis_follows_the_up_axis(self):
        self.assertEqual(lateral_index(1), 0)  # Y-up: X splits left from right
        self.assertEqual(lateral_index(2), 1)  # Z-up: Y does

    def test_diagonal_negates_only_the_lateral_axis(self):
        self.assertEqual(mirror_diagonal(1), (-1.0, 1.0, 1.0))
        self.assertEqual(mirror_diagonal(2), (1.0, -1.0, 1.0))


class TestWarpRange(unittest.TestCase):
    def test_slower_makes_a_longer_clip(self):
        self.assertEqual(warped_range(0, 28, 1.2), (0, 34))

    def test_faster_makes_a_shorter_clip(self):
        self.assertEqual(warped_range(0, 28, 0.8), (0, 22))

    def test_anchor_frame_is_preserved(self):
        self.assertEqual(warped_range(10, 28, 1.5)[0], 10)

    def test_factor_of_one_is_identity(self):
        self.assertEqual(warped_range(0, 28, 1.0), (0, 28))
        self.assertEqual(warped_frame_count(29, 1.0), 29)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            warped_range(0, 10, 0.0)
        with self.assertRaises(ValueError):
            warped_range(10, 0, 1.0)


class TestRetimeMapping(unittest.TestCase):
    """The frame grid a retime samples sits between the original keys."""

    def test_identity_at_factor_one(self):
        for frame in range(0, 29):
            self.assertEqual(retime_source_time(frame, 0, 1.0), float(frame))

    def test_sped_up_advances_further_per_frame(self):
        # factor 0.85 = 15% faster, so each output frame steps 1/0.85 of a
        # source frame.
        self.assertAlmostEqual(retime_source_time(1, 0, 0.85), 1 / 0.85)

    def test_lands_between_original_keys(self):
        value = retime_source_time(1, 0, 0.85)
        self.assertGreater(value, 1.0)
        self.assertLess(value, 2.0)

    def test_last_output_frame_lands_within_a_source_frame_of_the_end(self):
        # The output grid is integer, so the final frame lands *near* the
        # source end rather than exactly on it — 32/1.15 = 27.83 for a
        # 28-frame clip. Inherent to snapping the grid, not a defect.
        end = 28
        new_end = warped_range(0, end, 1.15)[1]
        self.assertLess(abs(retime_source_time(new_end, 0, 1.15) - end), 1.0)

    def test_anchor_frame_is_preserved(self):
        self.assertEqual(retime_source_time(10, 10, 1.5), 10.0)

    def test_rejects_bad_factor(self):
        with self.assertRaises(ValueError):
            retime_source_time(0, 0, 0.0)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def foot_report(name="foot_l", role="foot", speed=0.0, peak=0.0, total=0.0, measurable=True):
    return FootReport(
        foot=name,
        total_frames=10,
        contact_frames=5,
        contact_ratio=0.5,
        contact_events=1,
        root_motion=False,
        slide_total_norm=total,
        slide_max_norm=peak,
        slide_speed_norm=speed,
        role=role,
        measurable=measurable,
    )


def clip(name, feet):
    return ClipBaseline(clip=name, fps=30.0, root_motion=False, feet=feet)


def scan(*clips):
    return BaselineScan(clips=list(clips))


class TestGate(unittest.TestCase):
    @staticmethod
    def _thresholds(speed=0.05):
        return Thresholds({"slide_speed_norm": speed})

    def test_passing_clip_is_accepted(self):
        report = evaluate(scan(clip("a", [foot_report(speed=0.01)])), self._thresholds())
        self.assertEqual(report.accepted(), ["a"])
        self.assertTrue(report.verdicts[0].checks)
        self.assertAlmostEqual(report.acceptance_rate(), 1.0)

    def test_failing_clip_is_rejected_with_the_numbers(self):
        report = evaluate(scan(clip("a", [foot_report(speed=0.09)])), self._thresholds())
        self.assertEqual(report.rejected(), ["a"])
        self.assertIn("0.0900", report.verdicts[0].reasons[0])
        self.assertIn("0.0500", report.verdicts[0].reasons[0])

    def test_worst_foot_decides(self):
        # One clean foot must not carry a sliding one.
        report = evaluate(
            scan(
                clip(
                    "a",
                    [foot_report("foot_l", speed=0.01), foot_report("foot_r", speed=0.09)],
                )
            ),
            self._thresholds(),
        )
        self.assertFalse(report.verdicts[0].accepted)

    def test_toe_tip_cannot_fail_a_clip(self):
        # A toe tip rolls through stance by design; it is not a grounding
        # signal, so it is neither judged nor allowed to justify a pass.
        report = evaluate(
            scan(clip("a", [foot_report("toe_l", role="toe_tip", speed=0.9)])),
            self._thresholds(),
        )
        self.assertEqual(report.rejected(), ["a"])
        self.assertIn("no measurable planting foot", report.verdicts[0].reasons[0])

    def test_unmeasurable_foot_cannot_validate_a_clip(self):
        report = evaluate(
            scan(clip("a", [foot_report(speed=0.0, measurable=False)])),
            self._thresholds(),
        )
        self.assertEqual(report.rejected(), ["a"])

    def test_metrics_without_a_cut_are_ignored(self):
        report = evaluate(scan(clip("a", [foot_report(speed=0.9, peak=0.9)])), Thresholds({}))
        self.assertEqual(report.accepted(), ["a"])
        self.assertEqual(report.verdicts[0].checks, [])

    def test_worst_check_is_the_one_with_least_headroom(self):
        thresholds = Thresholds({"slide_speed_norm": 0.10, "slide_max_norm": 0.05})
        report = evaluate(
            scan(clip("a", [foot_report(speed=0.02, peak=0.045)])), thresholds
        )
        metric, _, _, _ = report.verdicts[0].worst()
        # 0.02/0.10 = 0.2 of the budget, 0.045/0.05 = 0.9.
        self.assertEqual(metric, "slide_max_norm")

    def test_thresholds_from_calibration_suggestions(self):
        suggestions = [
            ThresholdSuggestion(
                metric="slide_speed_norm",
                cut=0.07,
                percentile=95.0,
                good_count=8,
                false_positive_rate=0.0,
                bad_count=0,
                true_positive_rate=None,
            )
        ]
        thresholds = Thresholds.from_suggestions(suggestions)
        self.assertEqual(thresholds.cuts, {"slide_speed_norm": 0.07})
        self.assertIn("0.0700", thresholds.describe())

    def test_empty_thresholds_describe_themselves(self):
        self.assertEqual(Thresholds({}).describe(), "none configured")

    def test_report_states_the_split(self):
        report = evaluate(
            scan(
                clip("good", [foot_report(speed=0.01)]),
                clip("bad", [foot_report(speed=0.5)]),
            ),
            self._thresholds(),
        )
        text = format_gate_report(report)
        self.assertIn("# Quality gate", text)
        self.assertIn("Accepted 1/2 (50%)", text)
        self.assertIn("## Rejected", text)
        self.assertIn("`bad`", text)


class TestRelativeGate(unittest.TestCase):
    """Augmentation is judged against the clip it came from."""

    def test_variant_within_tolerance_passes(self):
        source = scan(clip("walk", [foot_report(speed=0.04)]))
        variant = scan(clip("walk_w1.15", [foot_report(speed=0.045)]))
        report = evaluate_against_source(
            variant, source, {"walk_w1.15": "walk"}, tolerance=0.25
        )
        self.assertEqual(report.accepted(), ["walk_w1.15"])

    def test_variant_beyond_tolerance_fails(self):
        source = scan(clip("walk", [foot_report(speed=0.04)]))
        variant = scan(clip("walk_w0.85", [foot_report(speed=0.12)]))
        report = evaluate_against_source(
            variant, source, {"walk_w0.85": "walk"}, tolerance=0.25
        )
        self.assertEqual(report.rejected(), ["walk_w0.85"])
        self.assertIn("source 0.0400", report.verdicts[0].reasons[0])

    def test_identical_clip_passes_its_own_source(self):
        # Regression: the unmodified control was rejected by a global cut
        # derived from the very corpus it belongs to.
        source = scan(clip("walk", [foot_report(speed=0.07, peak=0.033)]))
        variant = scan(clip("walk_w1.00", [foot_report(speed=0.07, peak=0.033)]))
        report = evaluate_against_source(variant, source, {"walk_w1.00": "walk"})
        self.assertEqual(report.accepted(), ["walk_w1.00"])

    def test_unmapped_variant_is_rejected(self):
        source = scan(clip("walk", [foot_report(speed=0.04)]))
        variant = scan(clip("orphan", [foot_report(speed=0.01)]))
        report = evaluate_against_source(variant, source, {})
        self.assertEqual(report.rejected(), ["orphan"])
        self.assertIn("no source baseline", report.verdicts[0].reasons[0])

    def test_floor_allows_a_small_absolute_allowance(self):
        source = scan(clip("walk", [foot_report(speed=0.0)]))
        variant = scan(clip("walk_m", [foot_report(speed=0.001)]))
        self.assertEqual(
            evaluate_against_source(variant, source, {"walk_m": "walk"}).rejected(),
            ["walk_m"],
        )
        self.assertEqual(
            evaluate_against_source(
                variant, source, {"walk_m": "walk"}, floor=0.01
            ).accepted(),
            ["walk_m"],
        )


if __name__ == "__main__":
    unittest.main()
