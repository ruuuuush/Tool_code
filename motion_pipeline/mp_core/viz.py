"""mp_core.viz

Renders measurement results as self-contained SVG panels and a single
portable HTML report.

Pure Python, zero dependencies, same philosophy as maya_to_ue's
curve_svg: the output opens in any browser or renders inline on GitHub,
so the portfolio artefact needs neither Maya nor UE to be shown.

Two panel types:

    clip_inspection_svg   one clip's "medical chart" — per-foot height
                          track, contact bands, per-step slide bars
    distribution_svg      calibration evidence — good vs injected values
                          on one axis with the suggested cut

``html_report`` stitches every panel plus the tables into one file.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from .baseline import BaselineScan, ThresholdSuggestion
from .foot_contact import (
    ClipSamples,
    ContactConfig,
    _contact_mask,
    _horizontal_distance,
    _median,
    _trim_contact_runs,
    detect_root_motion,
)
from .synth import InjectedRun

_WIDTH = 900
_LANE_H = 96
_PAD_L = 170   # bone label column
_PAD_R = 16
_LANE_PAD_T = 10
_LANE_PAD_B = 24
_TITLE_H = 40

_BG = "#1e1e1e"
_FG = "#d8d8d8"
_DIM = "#8a8a8a"
_AXIS = "#555555"
_BLUE = "#4f9cf9"     # height track
_GREEN = "#3fb96b"    # contact band
_RED = "#e05252"      # slide deviation bars
_AMBER = "#e0a832"    # cut line / warnings

_FONT = 'font-family="Consolas, Menlo, monospace"'


def _text(x: float, y: float, s: str, size: int = 12, fill: str = _FG, anchor: str = "start") -> str:
    return '<text x="{:.1f}" y="{:.1f}" font-size="{}" fill="{}" text-anchor="{}" {}>{}</text>'.format(
        x, y, size, fill, anchor, _FONT, escape(s)
    )


def _short(node: str) -> str:
    return node.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


# ---------------------------------------------------------------------------
# Panel 1: clip inspection
# ---------------------------------------------------------------------------


def _lane(
    samples: ClipSamples,
    foot: str,
    config: ContactConfig,
    root_motion: bool,
    top: float,
) -> List[str]:
    positions = samples.feet[foot]
    count = len(positions)
    up = samples.up_index
    inner_w = _WIDTH - _PAD_L - _PAD_R
    inner_h = _LANE_H - _LANE_PAD_T - _LANE_PAD_B
    out: List[str] = []

    info = samples.info_for(foot)
    label = "{} ({})".format(_short(foot), info.role)
    out.append(_text(12, top + _LANE_H / 2 - 2, label, 12))

    if count < 2:
        out.append(_text(_PAD_L, top + _LANE_H / 2, "not enough frames", 11, _DIM))
        return out

    def x_of(i: int) -> float:
        return _PAD_L + (i / (count - 1)) * inner_w

    heights = [p[up] for p in positions]
    hmin, hmax = min(heights), max(heights)
    hspan = (hmax - hmin) or 1.0

    def y_of(h: float) -> float:
        return top + _LANE_PAD_T + inner_h - (h - hmin) / hspan * inner_h

    tolerance = config.height_tolerance_ratio * samples.scale_ref
    raw_mask = _contact_mask(positions, up, tolerance)
    mask = _trim_contact_runs(raw_mask, config.contact_trim_frames)

    # Contact bands: raw contact faint, kept (trimmed) contact solid.
    half_step = inner_w / (count - 1) / 2.0
    for i in range(count):
        if not raw_mask[i]:
            continue
        band_x = x_of(i) - half_step
        out.append(
            '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" fill="{}" opacity="{}"/>'.format(
                band_x,
                top + _LANE_PAD_T,
                half_step * 2,
                inner_h,
                _GREEN,
                "0.35" if mask[i] else "0.12",
            )
        )

    # Tolerance line: everything below counts as "on the ground".
    tol_y = y_of(hmin + tolerance)
    out.append(
        '<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="{}" stroke-dasharray="4,4" stroke-width="1"/>'.format(
            _PAD_L, tol_y, _WIDTH - _PAD_R, tol_y, _AXIS
        )
    )

    # Height track.
    points = " ".join("{:.1f},{:.1f}".format(x_of(i), y_of(heights[i])) for i in range(count))
    out.append(
        '<polyline points="{}" fill="none" stroke="{}" stroke-width="1.6"/>'.format(points, _BLUE)
    )

    # Per-step slide deviation bars along the lane floor.
    steps: List[Tuple[int, float]] = []
    for i in range(1, count):
        if mask[i] and mask[i - 1]:
            steps.append((i, _horizontal_distance(positions[i], positions[i - 1], up)))
    if steps:
        baseline = 0.0 if root_motion else _median([s for _, s in steps])
        noise_floor = 1e-9 * (samples.scale_ref or 1.0)
        deviations = [
            (i, dev)
            for i, dev in ((i, abs(s - baseline)) for i, s in steps)
            # Float noise in accumulated positions lands around 1e-16 and
            # would otherwise render as 1px bars on a perfectly clean clip.
            if dev > noise_floor
        ]
        if deviations:
            dev_max = max(d for _, d in deviations)
            floor = top + _LANE_H - _LANE_PAD_B
            bar_max = inner_h * 0.45
            for i, dev in deviations:
                bar_h = max(dev / dev_max * bar_max, 1.0)
                out.append(
                    '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" fill="{}" opacity="0.85"/>'.format(
                        x_of(i) - half_step * 0.6, floor - bar_h, half_step * 1.2, bar_h, _RED
                    )
                )

    contact_ratio = sum(mask) / count
    out.append(
        _text(
            12,
            top + _LANE_H / 2 + 14,
            "contact {:.0%}".format(contact_ratio),
            11,
            _DIM,
        )
    )
    out.append(
        '<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="{}" stroke-width="1"/>'.format(
            _PAD_L, top + _LANE_H - _LANE_PAD_B, _WIDTH - _PAD_R, top + _LANE_H - _LANE_PAD_B, _AXIS
        )
    )
    return out


def clip_inspection_svg(
    samples: ClipSamples, config: Optional[ContactConfig] = None
) -> str:
    """One clip's medical chart: a lane per tracked foot bone.

    Blue = the foot's height over the clip. Green bands = frames counted
    as ground contact (faint green = detected but trimmed as settling).
    Red bars = per-step slide deviation while planted — the taller, the
    worse. A clean clip shows green blocks with no red inside them.
    """
    config = config or ContactConfig()
    feet = sorted(samples.feet)
    root_motion = detect_root_motion(samples, config)
    height = _TITLE_H + _LANE_H * len(feet) + 12

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'.format(
            w=_WIDTH, h=height
        ),
        '<rect width="{}" height="{}" fill="{}"/>'.format(_WIDTH, height, _BG),
        _text(12, 24, samples.name, 15),
        _text(
            _WIDTH - _PAD_R,
            24,
            "{} frames @ {:.0f} fps · {}".format(
                len(samples.frames),
                samples.fps,
                "root motion" if root_motion else "in place",
            ),
            12,
            _DIM,
            "end",
        ),
    ]
    for index, foot in enumerate(feet):
        out.extend(_lane(samples, foot, config, root_motion, _TITLE_H + index * _LANE_H))
    out.append("</svg>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Panel 2: calibration distribution
# ---------------------------------------------------------------------------

_STRIP_H = 96


def distribution_svg(
    metric: str,
    good: Sequence[float],
    bad: Sequence[float],
    cut: Optional[float] = None,
    bad_label: str = "injected",
) -> str:
    """Good vs degraded values of one metric on a shared axis.

    Strip plot rather than histogram: with a small corpus a histogram
    manufactures shapes that are not there, while a strip shows every
    measurement as-is — including how few there are.
    """
    values = list(good) + list(bad) + ([cut] if cut is not None else [])
    vmax = max(values) if values else 1.0
    vmax = vmax * 1.08 or 1.0
    inner_w = _WIDTH - _PAD_L - _PAD_R

    def x_of(v: float) -> float:
        return _PAD_L + (v / vmax) * inner_w

    good_y = 38.0
    bad_y = 66.0
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'.format(
            w=_WIDTH, h=_STRIP_H
        ),
        '<rect width="{}" height="{}" fill="{}"/>'.format(_WIDTH, _STRIP_H, _BG),
        _text(12, 22, metric, 13),
        _text(12, good_y + 4, "good (n={})".format(len(good)), 11, _GREEN),
        _text(12, bad_y + 4, "{} (n={})".format(bad_label, len(bad)), 11, _RED),
        '<line x1="{}" y1="82" x2="{}" y2="82" stroke="{}" stroke-width="1"/>'.format(
            _PAD_L, _WIDTH - _PAD_R, _AXIS
        ),
        _text(_PAD_L, 94, "0", 10, _DIM),
        _text(_WIDTH - _PAD_R, 94, "{:.4f}".format(vmax), 10, _DIM, "end"),
    ]
    for value in good:
        out.append(
            '<circle cx="{:.1f}" cy="{:.1f}" r="4" fill="{}" opacity="0.8"/>'.format(
                x_of(value), good_y, _GREEN
            )
        )
    for value in bad:
        out.append(
            '<circle cx="{:.1f}" cy="{:.1f}" r="4" fill="{}" opacity="0.8"/>'.format(
                x_of(value), bad_y, _RED
            )
        )
    if cut is not None:
        cx = x_of(cut)
        out.append(
            '<line x1="{:.1f}" y1="12" x2="{:.1f}" y2="82" stroke="{}" stroke-dasharray="5,3" stroke-width="1.5"/>'.format(
                cx, cx, _AMBER
            )
        )
        out.append(_text(cx + 5, 20, "cut {:.4f}".format(cut), 11, _AMBER))
    out.append("</svg>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# The one-file report
# ---------------------------------------------------------------------------

_CSS = """
body { background:#161616; color:#d8d8d8; font-family:Consolas,Menlo,monospace;
       max-width:960px; margin:24px auto; padding:0 16px; }
h1,h2 { font-weight:600; border-bottom:1px solid #333; padding-bottom:6px; }
table { border-collapse:collapse; margin:12px 0; width:100%; font-size:13px; }
th,td { border:1px solid #333; padding:5px 9px; text-align:left; }
th { background:#242424; }
tr.reject td { color:#e05252; }
svg { display:block; margin:14px 0; border:1px solid #2a2a2a; }
p.note { color:#8a8a8a; font-size:12px; }
"""


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]], row_classes: Optional[Sequence[str]] = None) -> str:
    parts = ["<table><tr>{}</tr>".format("".join("<th>{}</th>".format(escape(h)) for h in headers))]
    for index, row in enumerate(rows):
        cls = ' class="{}"'.format(row_classes[index]) if row_classes and row_classes[index] else ""
        parts.append(
            "<tr{}>{}</tr>".format(cls, "".join("<td>{}</td>".format(escape(str(c))) for c in row))
        )
    parts.append("</table>")
    return "".join(parts)


def _overview_section(scan: BaselineScan) -> str:
    rows = []
    for clip in scan.clips:
        for foot in clip.feet:
            if not foot.measurable:
                rows.append(
                    [clip.clip, _short(foot.foot), foot.role, "—", "—", "—", "; ".join(foot.notes)]
                )
                continue
            rows.append(
                [
                    clip.clip,
                    _short(foot.foot),
                    foot.role,
                    "{:.1%}".format(foot.contact_ratio),
                    "{:.4f}".format(foot.slide_speed_norm),
                    "{:.4f}".format(foot.slide_max_norm),
                    "root motion" if foot.root_motion else "in place",
                ]
            )
    return "<h2>Measurements</h2>" + _table(
        ["clip", "bone", "role", "contact", "slide/s", "slide max", ""], rows
    )


def _injection_section(runs: Sequence[InjectedRun]) -> str:
    rows = []
    baseline = runs[0].p50() if runs else 0.0
    for run in runs:
        p50 = run.p50()
        slope = (
            "—"
            if run.amplitude_ratio == 0
            else "{:.2f}".format((p50 - baseline) / run.expected_slide_max_norm)
        )
        rows.append(
            [
                "{:.3f}".format(run.amplitude_ratio),
                "{:.4f}".format(run.expected_slide_max_norm),
                "{:.4f}".format(p50),
                "{:.4f}".format(run.maximum()),
                slope,
            ]
        )
    return (
        "<h2>Metric self-validation</h2>"
        '<p class="note">Known slide is injected at amplitude a; a faithful metric must '
        "read back 2a. Slope 1.00 = the metric moves exactly as much as the injection.</p>"
        + _table(["injected a", "expected +2a", "measured p50", "measured max", "slope"], rows)
    )


def _threshold_section(suggestions: Sequence[ThresholdSuggestion]) -> str:
    rows = [
        [
            s.metric,
            "{:.4f}".format(s.cut),
            "p{:.0f} of good".format(s.percentile),
            str(s.good_count),
            "—" if s.true_positive_rate is None else "{:.0%}".format(s.true_positive_rate),
            "{:.0%}".format(s.false_positive_rate),
            s.verdict(),
        ]
        for s in suggestions
    ]
    return "<h2>Suggested thresholds</h2>" + _table(
        ["metric", "cut", "from", "n", "catches bad", "rejects good", "verdict"], rows
    )


def html_report(
    samples_list: Sequence[ClipSamples],
    scan: BaselineScan,
    runs: Optional[Sequence[InjectedRun]] = None,
    suggestions: Optional[Sequence[ThresholdSuggestion]] = None,
    config: Optional[ContactConfig] = None,
    title: str = "Motion Pipeline — quality report",
) -> str:
    """Everything in one self-contained HTML file.

    No external assets, no JS: SVG panels are inlined, so the file can be
    mailed, dropped into a portfolio page, or opened from disk unchanged.
    """
    config = config or ContactConfig()
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>{}</title><style>{}</style></head><body>".format(escape(title), _CSS),
        "<h1>{}</h1>".format(escape(title)),
        _overview_section(scan),
        "<h2>Clip inspection</h2>",
        '<p class="note">Blue = foot height. Green bands = ground contact '
        "(faint = trimmed as settling). Red bars = per-step slide deviation "
        "while planted; a clean clip has no red inside the green.</p>",
    ]
    for samples in samples_list:
        parts.append(clip_inspection_svg(samples, config))

    if runs:
        parts.append(_injection_section(runs))
        degraded = runs[-1]
        good_reports = scan.foot_reports(roles=degraded.roles)
        for metric in ("slide_speed_norm", "slide_max_norm"):
            cut = None
            if suggestions:
                cuts = [s.cut for s in suggestions if s.metric == metric]
                cut = cuts[0] if cuts else None
            parts.append(
                distribution_svg(
                    metric,
                    [getattr(f, metric) for f in good_reports],
                    degraded.values(metric),
                    cut,
                )
            )
    if suggestions:
        parts.append(_threshold_section(suggestions))

    parts.append("</body></html>")
    return "\n".join(parts)


__all__ = [
    "clip_inspection_svg",
    "distribution_svg",
    "html_report",
]
