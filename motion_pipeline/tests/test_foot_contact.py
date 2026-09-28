"""Tests for mp_core foot-contact metrics and threshold calibration.

Synthetic data only: these run in any Python 3.7+ interpreter, no Maya.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mp_core import (  # noqa: E402
    ROLE_FOOT,
    ROLE_TOE_TIP,
    ClipSamples,
    ContactConfig,
    FootInfo,
    analyse_clip,
    analyse_clips,
    calibrate,
    detect_root_motion,
    format_report,
    median,
    moving_window,
    percentile,
    trim_to_motion,
)

SCALE = 1.0


def samples(foot_x, root_x, foot_z=None, name="clip"):
    """Build a ClipSamples with one foot, Z-up, 30 fps, unit-scale character."""
    count = len(foot_x)
    if foot_z is None:
        foot_z = [0.0] * count
    return ClipSamples(
        name=name,
        fps=30.0,
        frames=list(range(count)),
        feet={"foot_l": [(foot_x[i], 0.0, foot_z[i]) for i in range(count)]},
        root=[(root_x[i], 0.0, 0.9) for i in range(count)],
        scale_ref=SCALE,
        up_index=2,
    )


class TestRootMotionDetection(unittest.TestCase):
    def test_moving_root_is_root_motion(self):
        data = samples([0.0] * 11, [i * 0.1 for i in range(11)])
        self.assertTrue(detect_root_motion(data, ContactConfig()))

    def test_stationary_root_is_in_place(self):
        data = samples([0.0] * 11, [0.0] * 11)
        self.assertFalse(detect_root_motion(data, ContactConfig()))

    def test_hip_sway_without_net_travel_is_in_place(self):
        # Regression: a stock in-place Mixamo walk sways the hips several
        # centimetres and returns to start. Path length called that root
        # motion, which then scored the planted foot's backward sweep as
        # slide — about 40x the real figure.
        sway = [0.0, 0.03, 0.06, 0.08, 0.06, 0.03, 0.0, -0.03, -0.06, -0.03, 0.0]
        data = samples([0.0] * len(sway), sway)
        self.assertFalse(detect_root_motion(data, ContactConfig()))

    def test_drift_below_threshold_is_in_place(self):
        drift = [i * 0.002 for i in range(11)]  # net 0.02, under 0.05 * scale
        data = samples([0.0] * 11, drift)
        self.assertFalse(detect_root_motion(data, ContactConfig()))


class TestSlideMetrics(unittest.TestCase):
    def test_planted_foot_in_root_motion_clip_has_no_slide(self):
        data = samples([0.0] * 11, [i * 0.2 for i in range(11)])
        report = analyse_clip(data)[0]
        self.assertTrue(report.measurable)
        self.assertTrue(report.root_motion)
        self.assertAlmostEqual(report.slide_total_norm, 0.0, places=6)
        self.assertAlmostEqual(report.slide_max_norm, 0.0, places=6)

    def test_sliding_foot_in_root_motion_clip_is_caught(self):
        data = samples([i * 0.05 for i in range(11)], [i * 0.2 for i in range(11)])
        report = analyse_clip(data)[0]
        self.assertGreater(report.slide_max_norm, 0.0)
        # 11 planted frames, one trimmed from each end, leaves 8 steps.
        self.assertAlmostEqual(report.slide_total_norm, 8 * 0.05, places=6)

    def test_steady_backward_sweep_in_place_is_not_slide(self):
        # This is what in-place locomotion is *supposed* to look like.
        data = samples([-i * 0.05 for i in range(11)], [0.0] * 11)
        report = analyse_clip(data)[0]
        self.assertFalse(report.root_motion)
        self.assertAlmostEqual(report.slide_total_norm, 0.0, places=6)

    def test_irregular_backward_sweep_in_place_is_slide(self):
        erratic = [0.0, -0.05, -0.05, -0.10, -0.10, -0.15, -0.15]
        data = samples(erratic, [0.0] * len(erratic))
        report = analyse_clip(data)[0]
        self.assertGreater(report.slide_total_norm, 0.0)

    def test_contact_event_counting(self):
        # Two separate ground contacts, one frame apart.
        foot_z = [0.0, 0.0, 0.5, 0.5, 0.0, 0.0]
        data = samples([0.0] * 6, [0.0] * 6, foot_z=foot_z)
        report = analyse_clip(data)[0]
        self.assertEqual(report.contact_events, 2)

    def test_single_frame_contact_is_not_an_event(self):
        foot_z = [0.5, 0.0, 0.5, 0.5, 0.5]
        data = samples([0.0] * 5, [0.0] * 5, foot_z=foot_z)
        report = analyse_clip(data)[0]
        self.assertEqual(report.contact_events, 0)


class TestUnmeasurableClips(unittest.TestCase):
    def test_airborne_clip_is_reported_not_scored(self):
        foot_z = [1.0 + i * 0.1 for i in range(50)]
        data = samples([0.0] * 50, [0.0] * 50, foot_z=foot_z)
        report = analyse_clip(data)[0]
        self.assertFalse(report.measurable)
        self.assertTrue(report.notes)
        self.assertEqual(report.slide_total_norm, 0.0)

    def test_too_few_frames(self):
        data = samples([0.0], [0.0])
        report = analyse_clip(data)[0]
        self.assertFalse(report.measurable)
        self.assertIn("not enough frames", report.notes[0])


class TestStatistics(unittest.TestCase):
    def test_median(self):
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([4, 1, 3, 2]), 2.5)

    def test_percentile_matches_numpy_definition(self):
        self.assertEqual(percentile([1, 2, 3, 4], 50), 2.5)
        self.assertEqual(percentile([1, 2, 3, 4], 0), 1)
        self.assertEqual(percentile([1, 2, 3, 4], 100), 4)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            median([])
        with self.assertRaises(ValueError):
            percentile([], 50)


class TestCalibration(unittest.TestCase):
    def _scan(self, slide_step, root_step, count=6):
        clips = []
        for index in range(count):
            clips.append(
                samples(
                    [i * slide_step for i in range(11)],
                    [i * root_step for i in range(11)],
                    name="clip_{}".format(index),
                )
            )
        return analyse_clips(clips)

    def test_calibrated_cut_separates_good_from_bad(self):
        good = self._scan(slide_step=0.0, root_step=0.2)   # planted
        bad = self._scan(slide_step=0.05, root_step=0.2)   # sliding
        suggestions = calibrate(good, bad)
        self.assertTrue(suggestions)
        for suggestion in suggestions:
            self.assertIsNotNone(suggestion.true_positive_rate)
            self.assertAlmostEqual(suggestion.true_positive_rate, 1.0)
            self.assertAlmostEqual(suggestion.false_positive_rate, 0.0)
            self.assertEqual(suggestion.verdict(), "separates well")

    def test_without_bad_batch_separation_is_unknown(self):
        good = self._scan(slide_step=0.0, root_step=0.2)
        suggestions = calibrate(good)
        for suggestion in suggestions:
            self.assertIsNone(suggestion.true_positive_rate)
            self.assertIn("unknown", suggestion.verdict())

    def test_bad_batch_below_cut_scores_zero(self):
        good = self._scan(slide_step=0.05, root_step=0.2)
        bad = self._scan(slide_step=0.01, root_step=0.2)
        suggestions = calibrate(good, bad)
        speed = [s for s in suggestions if s.metric == "slide_speed_norm"][0]
        self.assertLess(speed.true_positive_rate, 0.5)


class TestReport(unittest.TestCase):
    def test_report_renders_clips_and_distribution(self):
        scan = analyse_clips(
            [
                samples([0.0] * 11, [i * 0.2 for i in range(11)], name="walk"),
                samples([i * 0.05 for i in range(11)], [i * 0.2 for i in range(11)], name="run"),
            ]
        )
        markdown = format_report(scan)
        self.assertIn("# Baseline scan", markdown)
        self.assertIn("walk", markdown)
        self.assertIn("run", markdown)
        self.assertIn("slide_speed_norm", markdown)

    def test_report_lists_unmeasurable_clips(self):
        scan = analyse_clips([samples([0.0], [0.0], name="stub")])
        markdown = format_report(scan)
        self.assertIn("## Not measured", markdown)
        self.assertIn("not enough frames", markdown)

    def test_report_includes_suggestions(self):
        scan = analyse_clips([samples([0.0] * 11, [i * 0.2 for i in range(11)])])
        markdown = format_report(scan, calibrate(scan))
        self.assertIn("## Suggested thresholds", markdown)


class TestRoleFiltering(unittest.TestCase):
    """A toe tip rolling through stance is not slide; it must not set the cut."""

    @staticmethod
    def _clip(foot_x, root_x, role=ROLE_FOOT, name="clip"):
        data = samples(foot_x, root_x, name=name)
        data.foot_info = {"foot_l": FootInfo(role=role, side="left")}
        return data

    def _good(self):
        return analyse_clips([self._clip([0.0] * 11, [i * 0.2 for i in range(11)])])

    def _bad_toe_tip(self):
        return analyse_clips(
            [
                self._clip(
                    [i * 0.05 for i in range(11)],
                    [i * 0.2 for i in range(11)],
                    role=ROLE_TOE_TIP,
                )
            ]
        )

    def test_toe_tip_is_not_a_grounding_signal(self):
        report = analyse_clip(self._clip([0.0] * 11, [0.0] * 11, role=ROLE_TOE_TIP))[0]
        self.assertFalse(report.plants())
        self.assertTrue(any("toe tip" in note for note in report.notes))

    def test_gate_ignores_toe_tip_by_default(self):
        suggestions = calibrate(self._good(), self._bad_toe_tip())
        speed = [s for s in suggestions if s.metric == "slide_speed_norm"][0]
        self.assertEqual(speed.bad_count, 0)
        self.assertIsNone(speed.true_positive_rate)

    def test_roles_none_pools_every_bone(self):
        suggestions = calibrate(self._good(), self._bad_toe_tip(), roles=None)
        speed = [s for s in suggestions if s.metric == "slide_speed_norm"][0]
        self.assertEqual(speed.bad_count, 1)
        self.assertAlmostEqual(speed.true_positive_rate, 1.0)

    def test_report_breaks_down_by_role(self):
        scan = analyse_clips(
            [
                self._clip([0.0] * 11, [0.0] * 11, role=ROLE_FOOT, name="a"),
                self._clip([0.0] * 11, [0.0] * 11, role=ROLE_TOE_TIP, name="b"),
            ]
        )
        self.assertIn("## By role", format_report(scan))


class TestFrozenTrimming(unittest.TestCase):
    """A clip whose keys outrun its animation must not be averaged over."""

    @staticmethod
    def _with_frozen_tail():
        # 6 animated frames, then 20 identical ones — the shape measured on
        # a real 273-frame export whose walk only occupied the first 36.
        foot_x = [i * -0.05 for i in range(6)] + [-0.25] * 20
        return samples(foot_x, [0.0] * 26, name="tail")

    def test_moving_window_excludes_the_static_tail(self):
        start, end = moving_window(self._with_frozen_tail(), ContactConfig())
        self.assertEqual(start, 0)
        self.assertLess(end, 8)

    def test_trim_drops_the_frozen_frames(self):
        trimmed, dropped = trim_to_motion(self._with_frozen_tail())
        self.assertGreater(dropped, 15)
        self.assertEqual(len(trimmed.frames), len(self._with_frozen_tail().frames) - dropped)

    def test_animated_clip_is_left_alone(self):
        data = samples([i * -0.05 for i in range(11)], [0.0] * 11)
        trimmed, dropped = trim_to_motion(data)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(trimmed.frames), 11)

    def test_wholly_frozen_clip_is_left_alone(self):
        data = samples([0.0] * 10, [0.0] * 10)
        trimmed, dropped = trim_to_motion(data)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(trimmed.frames), 10)

    def test_scan_records_what_it_trimmed(self):
        scan = analyse_clips([self._with_frozen_tail()])
        self.assertGreater(scan.clips[0].frozen_trimmed, 15)

    def test_report_shows_the_frozen_column(self):
        self.assertIn("| frozen |", format_report(analyse_clips([self._with_frozen_tail()])))


if __name__ == "__main__":
    unittest.main()
