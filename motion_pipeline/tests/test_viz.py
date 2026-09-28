"""Tests for the SVG panels and the one-file HTML report.

All string assembly — no Maya, no browser. The assertions pin the parts
that carry meaning: every foot gets a lane, contact bands and slide bars
appear when and only when the data has them, the cut line lands in the
distribution, and the HTML embeds everything inline.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mp_core import (  # noqa: E402
    ClipSamples,
    ContactConfig,
    analyse_clips,
    calibrate,
    clip_inspection_svg,
    distribution_svg,
    html_report,
    measure_injection,
)


def samples(foot_x, root_x, foot_z=None, name="clip", feet_name="foot_l"):
    count = len(foot_x)
    if foot_z is None:
        foot_z = [0.0] * count
    return ClipSamples(
        name=name,
        fps=30.0,
        frames=list(range(count)),
        feet={feet_name: [(foot_x[i], 0.0, foot_z[i]) for i in range(count)]},
        root=[(root_x[i], 0.0, 0.9) for i in range(count)],
        scale_ref=1.0,
        up_index=2,
    )


def sweeping(name="clip"):
    return samples([i * -0.05 for i in range(11)], [0.0] * 11, name=name)


class TestClipInspectionSvg(unittest.TestCase):
    def test_is_a_selfcontained_svg(self):
        svg = clip_inspection_svg(sweeping())
        self.assertTrue(svg.startswith("<svg "))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)

    def test_one_lane_per_foot(self):
        data = sweeping()
        data.feet["foot_r"] = list(data.feet["foot_l"])
        svg = clip_inspection_svg(data)
        self.assertIn("foot_l", svg)
        self.assertIn("foot_r", svg)

    def test_grounded_clip_shows_contact_bands(self):
        self.assertIn("<rect", clip_inspection_svg(sweeping()))

    def test_airborne_clip_shows_almost_no_contact_bands(self):
        data = samples([0.0] * 20, [0.0] * 20, foot_z=[1.0 + i * 0.05 for i in range(20)])
        svg = clip_inspection_svg(data)
        # The mask is relative to the clip's own lowest point, so the
        # single lowest frame legitimately shows as one band; a rising
        # foot must not produce more than that.
        self.assertLessEqual(svg.count('fill="#3fb96b"'), 1)

    def test_clean_sweep_has_no_slide_bars(self):
        svg = clip_inspection_svg(sweeping())
        self.assertEqual(svg.count('fill="#e05252"'), 0)

    def test_erratic_sweep_shows_slide_bars(self):
        erratic = [0.0, -0.05, -0.05, -0.10, -0.10, -0.15, -0.15, -0.20, -0.20, -0.25, -0.25]
        svg = clip_inspection_svg(samples(erratic, [0.0] * len(erratic)))
        self.assertGreater(svg.count('fill="#e05252"'), 0)

    def test_states_root_motion_verdict(self):
        self.assertIn("in place", clip_inspection_svg(sweeping()))
        moving = samples([0.0] * 11, [i * 0.2 for i in range(11)])
        self.assertIn("root motion", clip_inspection_svg(moving))

    def test_clip_name_is_escaped(self):
        svg = clip_inspection_svg(sweeping(name="a<b&c"))
        self.assertIn("a&lt;b&amp;c", svg)
        self.assertNotIn("a<b&c", svg)


class TestDistributionSvg(unittest.TestCase):
    def test_plots_every_value(self):
        svg = distribution_svg("m", [0.01, 0.02], [0.05, 0.06, 0.07], cut=0.03)
        self.assertEqual(svg.count("<circle"), 5)
        self.assertIn("good (n=2)", svg)
        self.assertIn("injected (n=3)", svg)

    def test_cut_line_is_drawn_and_labelled(self):
        svg = distribution_svg("m", [0.01], [0.05], cut=0.03)
        self.assertIn("cut 0.0300", svg)
        self.assertIn("stroke-dasharray", svg)

    def test_without_cut_no_cut_label(self):
        svg = distribution_svg("m", [0.01], [0.05])
        self.assertNotIn("cut ", svg)

    def test_survives_empty_batches(self):
        svg = distribution_svg("m", [], [])
        self.assertIn("good (n=0)", svg)


class TestHtmlReport(unittest.TestCase):
    def _everything(self):
        batch = [sweeping(name="walk_a"), sweeping(name="walk_b")]
        good, runs = measure_injection(batch, amplitudes=(0.0, 0.01))
        suggestions = calibrate(good, runs[-1].scan)
        return batch, good, runs, suggestions

    def test_contains_every_section(self):
        batch, good, runs, suggestions = self._everything()
        html = html_report(batch, good, runs, suggestions)
        self.assertIn("<h2>Measurements</h2>", html)
        self.assertIn("<h2>Clip inspection</h2>", html)
        self.assertIn("<h2>Metric self-validation</h2>", html)
        self.assertIn("<h2>Suggested thresholds</h2>", html)

    def test_embeds_one_inspection_svg_per_clip(self):
        batch, good, runs, suggestions = self._everything()
        html = html_report(batch, good, runs, suggestions)
        self.assertEqual(html.count("<svg "), 2 + 2)  # 2 clips + 2 distributions

    def test_is_selfcontained(self):
        batch, good, runs, suggestions = self._everything()
        html = html_report(batch, good, runs, suggestions)
        self.assertNotIn("<script", html)
        self.assertNotIn("http://", html.replace("http://www.w3.org", ""))
        self.assertIn("<style>", html)

    def test_scan_only_report_skips_calibration_sections(self):
        batch = [sweeping(name="walk_a")]
        html = html_report(batch, analyse_clips(batch))
        self.assertIn("<h2>Measurements</h2>", html)
        self.assertNotIn("Metric self-validation", html)
        self.assertNotIn("Suggested thresholds", html)


if __name__ == "__main__":
    unittest.main()
