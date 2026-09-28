"""mtu_maya.export.curve_svg

Render before/after curve panels as a self-contained SVG document.

Pure Python, zero dependencies: the export report links this file and GitHub
renders SVG natively, so the curve comparison is viewable without Maya, UE,
or any image tooling. Red = original, blue = thinned.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple
from xml.sax.saxutils import escape

from mtu_maya.core.curve_thinning import CurvePanel

_WIDTH = 760
_PANEL_HEIGHT = 180
_MARGIN = 8
_PAD_L = 56   # value labels
_PAD_R = 12
_PAD_T = 26   # panel title
_PAD_B = 22   # frame labels
_HEADER = 34  # legend row

_RED = "#e05252"
_BLUE = "#4f9cf9"
_DIM = "#8a8a8a"
_AXIS = "#555555"
_BG = "#1e1e1e"


def _polyline(
    points: Sequence[Tuple[float, float]],
    t_range: Tuple[float, float],
    v_range: Tuple[float, float],
    top: float,
) -> str:
    tmin, tmax = t_range
    vmin, vmax = v_range
    inner_w = _WIDTH - _PAD_L - _PAD_R
    inner_h = _PANEL_HEIGHT - _PAD_T - _PAD_B
    tspan = (tmax - tmin) or 1.0
    vspan = (vmax - vmin) or 1.0

    def xy(p):
        x = _PAD_L + (p[0] - tmin) / tspan * inner_w
        y = top + _PAD_T + inner_h - (p[1] - vmin) / vspan * inner_h
        return f"{x:.1f},{y:.1f}"

    return " ".join(xy(p) for p in points)


def _panel_svg(panel: CurvePanel, top: float) -> List[str]:
    out = []
    both = list(panel.before) + list(panel.after)
    tmin = min(p[0] for p in both)
    tmax = max(p[0] for p in both)
    vmin = min(p[1] for p in both)
    vmax = max(p[1] for p in both)

    inner_h = _PANEL_HEIGHT - _PAD_T - _PAD_B
    inner_w = _WIDTH - _PAD_L - _PAD_R

    out.append(
        f'<text x="{_PAD_L}" y="{top + 16}" fill="{_DIM}" font-size="12" '
        f'font-family="monospace">{escape(panel.title)} '
        f'({panel.keys_before} → {panel.keys_after} keys)</text>'
    )
    # Axes.
    out.append(
        f'<line x1="{_PAD_L}" y1="{top + _PAD_T + inner_h}" '
        f'x2="{_WIDTH - _PAD_R}" y2="{top + _PAD_T + inner_h}" stroke="{_AXIS}"/>'
    )
    out.append(
        f'<line x1="{_PAD_L}" y1="{top + _PAD_T}" x2="{_PAD_L}" '
        f'y2="{top + _PAD_T + inner_h}" stroke="{_AXIS}"/>'
    )
    # Value extremes + time range.
    out.append(
        f'<text x="4" y="{top + _PAD_T + 4}" fill="{_DIM}" font-size="10">{vmax:.3g}</text>'
    )
    out.append(
        f'<text x="4" y="{top + _PAD_T + inner_h}" fill="{_DIM}" font-size="10">{vmin:.3g}</text>'
    )
    out.append(
        f'<text x="{_PAD_L}" y="{top + _PAD_T + inner_h + 14}" fill="{_DIM}" '
        f'font-size="10">{tmin:g}</text>'
    )
    out.append(
        f'<text x="{_WIDTH - _PAD_R}" y="{top + _PAD_T + inner_h + 14}" fill="{_DIM}" '
        f'font-size="10" text-anchor="end">{tmax:g}</text>'
    )

    if panel.before:
        out.append(
            f'<polyline fill="none" stroke="{_RED}" stroke-width="1.5" '
            f'points="{_polyline(panel.before, (tmin, tmax), (vmin, vmax), top)}"/>'
        )
    if panel.after:
        out.append(
            f'<polyline fill="none" stroke="{_BLUE}" stroke-width="1.5" '
            f'points="{_polyline(panel.after, (tmin, tmax), (vmin, vmax), top)}"/>'
        )
    return out


def render_curve_panels(panels: List[CurvePanel]) -> str:
    """Render up to a few panels as one SVG document. Empty input -> ""."""
    if not panels:
        return ""

    height = _HEADER + len(panels) * (_PANEL_HEIGHT + _MARGIN)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height}" '
        f'viewBox="0 0 {_WIDTH} {height}">',
        f'<rect width="{_WIDTH}" height="{height}" fill="{_BG}"/>',
        # Legend.
        f'<line x1="{_PAD_L}" y1="16" x2="{_PAD_L + 24}" y2="16" stroke="{_RED}" stroke-width="2"/>',
        f'<text x="{_PAD_L + 30}" y="20" fill="{_DIM}" font-size="12">original</text>',
        f'<line x1="{_PAD_L + 110}" y1="16" x2="{_PAD_L + 134}" y2="16" stroke="{_BLUE}" stroke-width="2"/>',
        f'<text x="{_PAD_L + 140}" y="20" fill="{_DIM}" font-size="12">thinned</text>',
    ]
    for i, panel in enumerate(panels):
        parts.extend(_panel_svg(panel, _HEADER + i * (_PANEL_HEIGHT + _MARGIN)))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


__all__ = ["render_curve_panels"]
