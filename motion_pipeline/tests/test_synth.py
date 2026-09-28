"""Tests for synthetic slide injection and the calibration it enables.

The headline assertion is arithmetic rather than a vibe: a square-wave
offset of ``a`` shifts every per-step displacement by ``2a``, the metric
is deviation from the median step, so ``slide_max_norm`` must land on
exactly ``2a``. If that ever drifts, the metric or the injection is wrong.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mp_core import (  # noqa: E402
    BaselineScan,
    ClipBaseline,
    ClipSamples,
    FootReport,
    InjectedRun,
    analyse_clip,
    calibrate,
    format_calibration_report,
    inject_sweep_jitter,
    measure_injection,
    sweep_axis,
)


def samples(foot_x, root_x, foot_z=None, name="clip", scale=1.0):
    count = len(foot_x)
    if foot_z is None:
        foot_z = [0.0] * count
    return ClipSamples(
        name=name,
        fps=30.0,
        frames=list(range(count)),
        feet={"foot_l": [(foot_x[i], 0.0, foot_z[i]) for i in range(count)]},
        root=[(root_x[i], 0.0, 0.9) for i in range(count)],
        scale_ref=scale,
        up_index=2,
    )


def sweeping(count=11, step=-0.05, name="clip"):
    """In-place clip whose planted foot sweeps at a steady rate."""
    return samples([i * step for i in range(count)], [0.0] * count, name=name)


class TestSweepAxis(unittest.TestCase):
    def test_picks_the_axis_of_travel(self):
        path = [(0.0, 0.0, 0.0), (0.5, 0.01, 0.0), (1.0, 0.02, 0.0)]
        self.assertEqual(sweep_axis(path, up=2), 0)

    def test_uses_total_variation_not_displacement(self):
        # Loops back to its start: displacement is zero on every axis,
        # travel along X is not.
        path = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        self.assertEqual(sweep_axis(path, up=2), 0)


class TestInjection(unittest.TestCase):
    def test_offset_is_a_square_wave(self):
        data = samples([0.0] * 6, [0.0] * 6)
        xs = [p[0] for p in inject_sweep_jitter(data, 0.1).feet["foot_l"]]
        self.assertEqual(xs, [0.1, -0.1, 0.1, -0.1, 0.1, -0.1])

    def test_scales_with_skeleton_height(self):
        data = samples([0.0] * 4, [0.0] * 4, scale=2.0)
        xs = [p[0] for p in inject_sweep_jitter(data, 0.1).feet["foot_l"]]
        self.assertEqual(xs, [0.2, -0.2, 0.2, -0.2])

    def test_original_is_not_mutated(self):
        data = samples([0.0] * 6, [0.0] * 6)
        inject_sweep_jitter(data, 0.1)
        self.assertEqual([p[0] for p in data.feet["foot_l"]], [0.0] * 6)

    def test_name_records_the_amplitude(self):
        data = samples([0.0] * 6, [0.0] * 6, name="walk")
        self.assertEqual(inject_sweep_jitter(data, 0.02).name, "walk@jit0.020")

    def test_period_must_be_positive(self):
        with self.assertRaises(ValueError):
            inject_sweep_jitter(samples([0.0] * 6, [0.0] * 6), 0.02, period=0)


class TestMetricResponse(unittest.TestCase):
    """Measured slide must equal the injected 2a, in both clip modes."""

    def test_in_place_sweep(self):
        data = sweeping()
        for amplitude in (0.005, 0.01, 0.02):
            report = analyse_clip(inject_sweep_jitter(data, amplitude))[0]
            self.assertAlmostEqual(report.slide_max_norm, 2 * amplitude, places=9)

    def test_root_motion_planted_foot(self):
        data = samples([0.0] * 11, [i * 0.2 for i in range(11)])
        for amplitude in (0.005, 0.01, 0.02):
            report = analyse_clip(inject_sweep_jitter(data, amplitude))[0]
            self.assertAlmostEqual(report.slide_max_norm, 2 * amplitude, places=9)

    def test_undegraded_sweep_measures_zero(self):
        self.assertAlmostEqual(analyse_clip(sweeping())[0].slide_max_norm, 0.0, places=9)

    def test_metric_saturates_once_injection_exceeds_the_stride(self):
        # Documents the ceiling instead of pretending it away: past
        # 2a > stride the deviation caps at the stride length, because a
        # bigger zigzag only flips the sign of the step.
        data = sweeping(count=11, step=-0.02)
        small = analyse_clip(inject_sweep_jitter(data, 0.002))[0].slide_max_norm
        large = analyse_clip(inject_sweep_jitter(data, 0.05))[0].slide_max_norm
        self.assertAlmostEqual(small, 2 * 0.002, places=9)
        self.assertAlmostEqual(large, 0.02, places=9)


class TestCalibration(unittest.TestCase):
    def _batch(self):
        return [
            sweeping(name="a", step=-0.05),
            sweeping(name="b", step=-0.04),
        ]

    def test_expected_value_matches_construction(self):
        _, runs = measure_injection(self._batch(), amplitudes=(0.0, 0.02))
        self.assertAlmostEqual(runs[0].expected_slide_max_norm, 0.0)
        self.assertAlmostEqual(runs[1].expected_slide_max_norm, 0.04)

    def test_response_is_monotonic_in_injected_slide(self):
        _, runs = measure_injection(self._batch(), amplitudes=(0.0, 0.005, 0.01, 0.02))
        values = [run.p50() for run in runs]
        self.assertEqual(values, sorted(values))

    def test_slope_is_one(self):
        # Measured rise over injected rise: 1.00 means the metric moved
        # exactly as far as the injection.
        _, runs = measure_injection(self._batch(), amplitudes=(0.0, 0.01, 0.02))
        baseline = runs[0].p50()
        for run in runs[1:]:
            self.assertAlmostEqual(
                (run.p50() - baseline) / run.expected_slide_max_norm, 1.0, places=6
            )

    def _run_with(self, amplitude, slide_value):
        report = FootReport(
            foot="f",
            total_frames=10,
            contact_frames=10,
            contact_ratio=1.0,
            contact_events=1,
            root_motion=False,
            slide_total_norm=0.0,
            slide_max_norm=slide_value,
            slide_speed_norm=0.0,
        )
        scan = BaselineScan(
            clips=[ClipBaseline(clip="c", fps=30.0, root_motion=False, feet=[report])]
        )
        return InjectedRun(amplitude, scan)

    def test_report_covers_response_and_thresholds(self):
        good, runs = measure_injection(self._batch(), amplitudes=(0.0, 0.01))
        text = format_calibration_report(good, runs, calibrate(good, runs[-1].scan))
        self.assertIn("## Injected slide response", text)
        self.assertIn("Monotonic in injected slide (within 2%): **yes**", text)
        self.assertIn("## Suggested thresholds", text)

    def test_report_flags_non_monotonic_response(self):
        runs = [self._run_with(0.0, 0.0100), self._run_with(0.01, 0.0050)]
        text = format_calibration_report(BaselineScan(), runs)
        self.assertIn("**NO**", text)

    def test_microscopic_dip_does_not_read_as_non_monotonic(self):
        # Regression: a saturated plateau carries sub-0.1% noise, and the
        # check compared with a 1e-9 tolerance, so a flat response reported
        # "NO" while every printed value rose.
        runs = [
            self._run_with(0.0, 0.0400),
            self._run_with(0.01, 0.0401),
            self._run_with(0.02, 0.0401 * 0.999),
        ]
        text = format_calibration_report(BaselineScan(), runs)
        self.assertIn("**yes**", text)


if __name__ == "__main__":
    unittest.main()
