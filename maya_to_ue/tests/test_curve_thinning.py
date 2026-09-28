"""tests.test_curve_thinning

Pure algorithm + Maya-adapter (fake cmds) coverage for keyframe thinning.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mtu_maya.core.curve_thinning import (
    LEVELS,
    LEVEL_OFF,
    THINNING_LEVELS,
    downsample_polyline,
    max_removal_error,
    thin_samples,
    thin_skeleton_curves,
    tolerance_for,
)


class TestThinSamples(unittest.TestCase):
    def test_linear_curve_collapses_to_endpoints(self):
        times = list(range(50))
        values = [2.0 * t + 1.0 for t in times]
        self.assertEqual(thin_samples(times, values, 0.001), [0, 49])

    def test_flat_curve_collapses_to_endpoints(self):
        times = list(range(30))
        values = [5.0] * 30
        self.assertEqual(thin_samples(times, values, 0.0001), [0, 29])

    def test_endpoints_always_kept(self):
        times = [0, 1, 2, 3, 4, 5]
        values = [0.0, 10.0, -10.0, 10.0, -10.0, 0.0]  # 锯齿，谁也删不掉
        keep = thin_samples(times, values, 0.5)
        self.assertEqual(keep[0], 0)
        self.assertEqual(keep[-1], 5)

    def test_removed_keys_stay_within_tolerance(self):
        # 正弦 + 微噪：在 0.05 容差下应删一批，且每个被删 key 的插值误差 ≤ ε。
        import math
        times = [t * 0.5 for t in range(120)]
        values = [math.sin(t) + (0.01 if i % 7 == 3 else 0.0)
                  for i, t in enumerate(times)]
        tol = 0.05
        keep = thin_samples(times, values, tol)
        self.assertLess(len(keep), len(times))
        self.assertLessEqual(max_removal_error(times, values, keep), tol + 1e-9)

    def test_zero_tolerance_keeps_noisy_curve_intact(self):
        times = list(range(10))
        values = [0.0, 0.3, 0.0, 0.4, 0.0, 0.5, 0.0, 0.6, 0.0, 0.7]
        keep = thin_samples(times, values, 0.0)
        self.assertEqual(len(keep), 10)

    def test_two_or_fewer_keys_untouched(self):
        self.assertEqual(thin_samples([1], [1.0], 1.0), [0])
        self.assertEqual(thin_samples([1, 2], [1.0, 2.0], 1.0), [0, 1])


class TestLevels(unittest.TestCase):
    def test_tolerances_monotonic_per_channel(self):
        for kind in ("translate", "rotate", "scale"):
            low = tolerance_for("low", kind)
            mid = tolerance_for("medium", kind)
            high = tolerance_for("high", kind)
            self.assertLess(low, mid)
            self.assertLess(mid, high)

    def test_off_has_no_tolerance_entry(self):
        self.assertNotIn(LEVEL_OFF, THINNING_LEVELS)
        self.assertEqual(LEVELS[0], LEVEL_OFF)


class TestDownsample(unittest.TestCase):
    def test_short_curve_unchanged(self):
        pts = downsample_polyline([0, 1, 2], [1.0, 2.0, 3.0])
        self.assertEqual(pts, [(0, 1.0), (1, 2.0), (2, 3.0)])

    def test_long_curve_capped(self):
        times = list(range(1000))
        values = [float(i) for i in range(1000)]
        pts = downsample_polyline(times, values, max_points=100)
        self.assertEqual(len(pts), 100)
        self.assertEqual(pts[0], (0, 0.0))
        self.assertEqual(pts[-1], (999, 999.0))


class _FakeCmds(object):
    """Minimal cmds stub: just enough surface for thin_skeleton_curves."""

    def __init__(self, curves):
        # curves: {name: {"times": [], "values": [], "type": str,
        #                 "stepped": bool, "dest": "node.attr"}}
        self.curves = curves
        self.undo_open = 0
        self.undo_close = 0
        self.deleted = {}

    def listRelatives(self, root, allDescendents=True, type=None, fullPath=True):
        return []

    def listConnections(self, node, type=None, source=True, destination=False, plugs=False):
        if type == "animCurve":
            return [name for name in self.curves]
        if plugs:
            return [self.curves[node]["dest"]]
        return []

    def nodeType(self, node):
        return self.curves[node]["type"]

    def keyTangent(self, curve, query=True, outTangentType=True):
        if self.curves[curve]["stepped"]:
            return ["stepped"] * len(self.curves[curve]["times"])
        return ["linear"] * len(self.curves[curve]["times"])

    def keyframe(self, curve, query=False, timeChange=False, valueChange=False,
                 edit=False, time=None, clear=False):
        data = self.curves[curve]
        if query and timeChange:
            return list(data["times"])
        if query and valueChange:
            return list(data["values"])
        return []

    def cutKey(self, curve, time=None, clear=False):
        # 真实的删除 API：keyframe 没有 clear 旗标，测假桩就得用真的那套。
        data = self.curves[curve]
        t = time[0]
        idx = min(range(len(data["times"])), key=lambda i: abs(data["times"][i] - t))
        data["times"].pop(idx)
        data["values"].pop(idx)
        self.deleted[curve] = self.deleted.get(curve, 0) + 1
        return None

    def currentUnit(self, query=True, angle=False):
        return "deg"

    def undoInfo(self, openChunk=False, closeChunk=False, chunkName=""):
        if openChunk:
            self.undo_open += 1
        if closeChunk:
            self.undo_close += 1


def _curve(times, values, dest="root.translateY", type="animCurveTU", stepped=False):
    return {"times": list(times), "values": list(values),
            "type": type, "dest": dest, "stepped": stepped}


class TestThinSkeletonCurves(unittest.TestCase):
    def test_off_level_returns_none_and_touches_nothing(self):
        fake = _FakeCmds({"root_translateY": _curve(range(10), [1.0] * 10)})
        self.assertIsNone(thin_skeleton_curves("root", (1, 10), LEVEL_OFF, fake))
        self.assertEqual(len(fake.curves["root_translateY"]["times"]), 10)

    def test_flat_curve_reduced_to_endpoints(self):
        fake = _FakeCmds({"root_translateY": _curve(range(20), [3.0] * 20)})
        result = thin_skeleton_curves("root", (1, 20), "medium", fake)
        self.assertEqual(result.keys_before, 20)
        self.assertEqual(result.keys_after, 2)
        self.assertEqual(fake.deleted["root_translateY"], 18)
        self.assertEqual(result.max_error, 0.0)
        self.assertEqual(result.panels[0].title, "root.translateY")

    def test_stepped_curve_never_touched(self):
        fake = _FakeCmds({"root_translateY": _curve(range(10), [1.0] * 10,
                                                    stepped=True)})
        result = thin_skeleton_curves("root", (1, 10), "high", fake)
        self.assertEqual(result.keys_before, 0)
        self.assertEqual(fake.deleted.get("root_translateY", 0), 0)

    def test_timelocked_curve_never_touched(self):
        fake = _FakeCmds({"switch": _curve(range(10), [1.0] * 10,
                                           type="animCurveTL")})
        result = thin_skeleton_curves("root", (1, 10), "high", fake)
        self.assertEqual(result.keys_before, 0)

    def test_deletions_wrapped_in_one_undo_chunk(self):
        fake = _FakeCmds({"root_translateY": _curve(range(20), [3.0] * 20)})
        thin_skeleton_curves("root", (1, 20), "medium", fake)
        self.assertEqual(fake.undo_open, 1)
        self.assertEqual(fake.undo_close, 1)

    def test_rotate_values_converted_when_scene_uses_radians(self):
        class RadCmds(_FakeCmds):
            def currentUnit(self, query=True, angle=False):
                return "rad"

        import math
        # 常数弧度值：换成度之后仍是平的，照删不误。
        fake = RadCmds({"root_rotateX": _curve(range(10), [math.pi / 2] * 10,
                                               dest="root.rotateX")})
        result = thin_skeleton_curves("root", (1, 10), "medium", fake)
        self.assertEqual(result.keys_after, 2)


if __name__ == "__main__":
    unittest.main()
