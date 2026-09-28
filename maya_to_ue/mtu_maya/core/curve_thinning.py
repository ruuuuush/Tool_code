"""mtu_maya.core.curve_thinning

Error-bounded keyframe reduction for baked animation.

The FBX plugin bakes internally (FBXExportBakeComplexAnimation), so the only
real hook for thinning is the scene's animCurves before export. This module
splits along the project's usual line:

    - thin_samples()  — pure (times, values, tolerance) -> kept indices.
      No Maya, fully unit-testable.
    - thin_skeleton_curves() — the Maya adapter: enumerate curves under the
      skeleton root, read keys, call the pure function, delete the rest
      inside ONE undo chunk.

Algorithm: greedy chord deviation. Anchor at the last kept key, walk a
candidate forward; if any intermediate key deviates from the anchor→candidate
chord (in value, at its own time) by more than `tolerance`, the previous
candidate becomes a kept key. O(n), deterministic, endpoints always kept.
This is the standard key-reduction scheme — RDP's perpendicular distance in
(t, v) space makes no sense when the axes have incomparable units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------

# level -> (translate cm, rotate degrees, scale ratio). Rotation is measured
# in degrees because that is what artists read; the Maya adapter converts
# when the scene uses radians.
THINNING_LEVELS: Dict[str, Tuple[float, float, float]] = {
    "low": (0.01, 0.05, 0.0001),
    "medium": (0.05, 0.25, 0.0005),
    "high": (0.20, 1.00, 0.0020),
}

LEVEL_OFF = "off"
LEVELS = (LEVEL_OFF, "low", "medium", "high")


def tolerance_for(level: str, channel_kind: str) -> float:
    """Tolerance for *level* and channel kind ('translate'|'rotate'|'scale')."""
    t, r, s = THINNING_LEVELS[level]
    return {"translate": t, "rotate": r, "scale": s}.get(channel_kind, t)


# ---------------------------------------------------------------------------
# Pure algorithm
# ---------------------------------------------------------------------------

def thin_samples(
    times: Sequence[float],
    values: Sequence[float],
    tolerance: float,
) -> List[int]:
    """Return the indices of the keys to KEEP.

    Every removed key deviates from the linear interpolation of its kept
    neighbours by at most *tolerance* (in value units, at the key's own
    time). Endpoints are always kept.
    """
    n = len(times)
    if n <= 2:
        return list(range(n))

    keep = [0]
    anchor = 0
    candidate = anchor + 2
    while candidate < n:
        # Deviation of every key strictly between anchor and candidate from
        # the anchor→candidate chord, evaluated at each key's own time.
        t0, v0 = times[anchor], values[anchor]
        t1, v1 = times[candidate], values[candidate]
        span = t1 - t0
        worst = 0.0
        for i in range(anchor + 1, candidate):
            if span > 0:
                f = (times[i] - t0) / span
                interp = v0 + (v1 - v0) * f
            else:
                interp = v1
            worst = max(worst, abs(values[i] - interp))
        if worst > tolerance:
            # The key before the candidate is the furthest we can stretch.
            keep.append(candidate - 1)
            anchor = candidate - 1
            candidate = anchor + 2
        else:
            candidate += 1
    if keep[-1] != n - 1:
        keep.append(n - 1)
    return keep


def max_removal_error(
    times: Sequence[float],
    values: Sequence[float],
    keep: Sequence[int],
) -> float:
    """Largest deviation of a removed key from the kept-keys interpolation."""
    if len(keep) >= len(times):
        return 0.0
    keep_set = set(keep)
    worst = 0.0
    for seg in range(len(keep) - 1):
        a, b = keep[seg], keep[seg + 1]
        t0, v0 = times[a], values[a]
        t1, v1 = times[b], values[b]
        span = t1 - t0
        for i in range(a + 1, b):
            if i in keep_set:
                continue
            f = (times[i] - t0) / span if span > 0 else 1.0
            interp = v0 + (v1 - v0) * f
            worst = max(worst, abs(values[i] - interp))
    return worst


def downsample_polyline(
    times: Sequence[float],
    values: Sequence[float],
    max_points: int = 240,
) -> List[Tuple[float, float]]:
    """Reduce a curve to at most *max_points* (t, v) pairs for plotting."""
    n = len(times)
    if n <= max_points:
        return list(zip(times, values))
    step = (n - 1) / float(max_points - 1)
    points = []
    for k in range(max_points):
        i = min(n - 1, int(round(k * step)))
        points.append((times[i], values[i]))
    return points


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class CurvePanel:
    """One channel's before/after polylines, ready for plotting."""

    title: str                                  # e.g. "root.translateY"
    before: List[Tuple[float, float]] = field(default_factory=list)
    after: List[Tuple[float, float]] = field(default_factory=list)
    keys_before: int = 0
    keys_after: int = 0


@dataclass
class ThinningResult:
    """What thin_skeleton_curves() did, for the report and the manifest."""

    level: str
    curves_touched: int = 0
    keys_before: int = 0
    keys_after: int = 0
    max_error: float = 0.0
    panels: List[CurvePanel] = field(default_factory=list)

    @property
    def removed(self) -> int:
        return self.keys_before - self.keys_after

    @property
    def removed_pct(self) -> float:
        if not self.keys_before:
            return 0.0
        return 100.0 * self.removed / self.keys_before


# ---------------------------------------------------------------------------
# Maya adapter
# ---------------------------------------------------------------------------

_CURVE_TYPES = ("animCurveTU", "animCurveTA")  # TL = time/bool — never touch
_PANEL_COUNT = 3


def _channel_kind(attribute: str) -> str:
    attr = attribute.rsplit(".", 1)[-1].lower()
    if attr.startswith("rotate"):
        return "rotate"
    if attr.startswith("scale"):
        return "scale"
    return "translate"


def _angle_to_degrees(c, value: float) -> float:
    """cmds returns angles in the scene's angular unit; we think in degrees."""
    try:
        unit = c.currentUnit(query=True, angle=True)
    except Exception:
        return value
    if unit and unit.lower().startswith("rad"):
        return math.degrees(value)
    return value


def thin_skeleton_curves(
    root: str,
    frame_range: Tuple[float, float],
    level: str,
    cmds_module=None,
) -> Optional[ThinningResult]:
    """Thin every continuous curve under *root* inside one undo chunk.

    Returns None for the 'off' level or an unloadable scene; otherwise a
    ThinningResult (possibly all-zero when nothing was thin enough).
    """
    if level == LEVEL_OFF or level not in THINNING_LEVELS:
        return None

    if cmds_module is None:
        from mtu_maya.core import maya_utils
        c = maya_utils.cmds()
    else:
        c = cmds_module

    try:
        joints = c.listRelatives(root, allDescendents=True, type="joint", fullPath=True) or []
        joints = [root] + list(joints)
    except Exception:
        joints = [root]

    start, end = frame_range
    curves = []
    for joint in joints:
        try:
            found = c.listConnections(
                joint, type="animCurve", source=True, destination=False
            ) or []
        except Exception:
            found = []
        for curve in found:
            if curve not in curves:
                curves.append(curve)

    result = ThinningResult(level=level)
    candidates = []
    for curve in curves:
        try:
            if c.nodeType(curve) not in _CURVE_TYPES:
                continue
            out_types = c.keyTangent(curve, query=True, outTangentType=True) or []
            if "stepped" in out_types:
                continue
            times = c.keyframe(curve, query=True, timeChange=True) or []
            values = c.keyframe(curve, query=True, valueChange=True) or []
        except Exception:
            continue
        if len(times) < 3 or len(times) != len(values):
            continue
        # Attribute name decides the tolerance class.
        try:
            dests = c.listConnections(curve, source=False, destination=True, plugs=True) or []
        except Exception:
            dests = []
        attribute = dests[0] if dests else curve
        kind = _channel_kind(attribute)
        if kind == "rotate":
            values = [_angle_to_degrees(c, v) for v in values]
        candidates.append((curve, attribute, kind, list(times), list(values)))

    c.undoInfo(openChunk=True, chunkName="smart_key_thinning")
    try:
        for curve, attribute, kind, times, values in candidates:
            keep = thin_samples(times, values, tolerance_for(level, kind))
            removed = [i for i in range(len(times)) if i not in set(keep)]
            if not removed:
                continue
            err = max_removal_error(times, values, keep)
            for i in removed:
                # 删 key 用 cutKey(clear=True)：keyframe 没有 clear 旗标。
                c.cutKey(curve, time=(times[i],), clear=True)
            result.curves_touched += 1
            result.keys_before += len(times)
            result.keys_after += len(keep)
            result.max_error = max(result.max_error, err)
            result.panels.append(CurvePanel(
                title=attribute,
                before=downsample_polyline(times, values),
                after=downsample_polyline(
                    [times[i] for i in keep], [values[i] for i in keep]),
                keys_before=len(times),
                keys_after=len(keep),
            ))
    finally:
        c.undoInfo(closeChunk=True)

    # Only the biggest reductions earn a panel in the report.
    result.panels.sort(key=lambda p: p.keys_before - p.keys_after, reverse=True)
    del result.panels[_PANEL_COUNT:]
    return result


__all__ = [
    "CurvePanel",
    "LEVELS",
    "LEVEL_OFF",
    "THINNING_LEVELS",
    "ThinningResult",
    "downsample_polyline",
    "max_removal_error",
    "thin_samples",
    "thin_skeleton_curves",
    "tolerance_for",
]
