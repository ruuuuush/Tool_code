"""mp_core.baseline

Turns per-clip contact metrics into a distribution, then into threshold
suggestions for the Step 2 quality gate.

Why calibrate instead of picking a number: a made-up threshold is either
so loose it waves sliding clips through, or so tight it rejects good
ones — and without both distributions you cannot tell which. Feeding
known-good and known-bad batches in is what makes the number defensible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from .foot_contact import (
    PLANTING_ROLES,
    ClipSamples,
    ContactConfig,
    FootReport,
    analyse_clip,
    trim_to_motion,
)

# Metrics the gate thresholds on. Names match FootReport fields.
QUALITY_METRICS = ("slide_speed_norm", "slide_max_norm", "slide_total_norm")


# ---------------------------------------------------------------------------
# Statistics (stdlib only; numpy's percentile definition, so numbers match)
# ---------------------------------------------------------------------------


def median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("median() of empty sequence")
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def percentile(values: Sequence[float], p: float) -> float:
    """Linear-interpolated percentile, ``p`` in [0, 100]."""
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("percentile() of empty sequence")
    if n == 1 or p <= 0:
        return ordered[0]
    if p >= 100:
        return ordered[-1]
    rank = (p / 100.0) * (n - 1)
    low = int(rank)
    high = min(low + 1, n - 1)
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean() of empty sequence")
    return sum(values) / len(values)


def _short(node: str) -> str:
    return node.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


# ---------------------------------------------------------------------------
# Scan shapes
# ---------------------------------------------------------------------------


@dataclass
class ClipBaseline:
    clip: str
    fps: float
    root_motion: bool
    feet: List[FootReport]
    # Frames dropped because the skeleton was frozen there (see
    # foot_contact.moving_window).
    frozen_trimmed: int = 0


@dataclass
class BaselineScan:
    clips: List[ClipBaseline] = field(default_factory=list)

    def foot_reports(
        self,
        measurable_only: bool = True,
        roles: Optional[Sequence[str]] = None,
    ) -> List[FootReport]:
        reports = [f for c in self.clips for f in c.feet]
        if measurable_only:
            reports = [f for f in reports if f.measurable]
        if roles is not None:
            reports = [f for f in reports if f.role in roles]
        return reports


def analyse_clips(
    samples: Iterable[ClipSamples],
    config: Optional[ContactConfig] = None,
    trim_frozen: bool = True,
) -> BaselineScan:
    """Measure a batch of clips into one scan.

    ``trim_frozen`` drops leading/trailing frames where nothing moves.
    Leave it on unless the samples have already been trimmed: a clip whose
    keys outrun its animation would otherwise be measured mostly on a
    static pose.
    """
    config = config or ContactConfig()
    scan = BaselineScan()
    for item in samples:
        dropped = 0
        if trim_frozen:
            item, dropped = trim_to_motion(item, config)
        feet = analyse_clip(item, config)
        root_motion = any(f.root_motion for f in feet)
        scan.clips.append(
            ClipBaseline(
                clip=item.name,
                fps=item.fps,
                root_motion=root_motion,
                feet=feet,
                frozen_trimmed=dropped,
            )
        )
    return scan


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


@dataclass
class ThresholdSuggestion:
    """A cut-off plus how well it actually separates the two batches."""

    metric: str
    cut: float
    percentile: float
    good_count: int
    # Fraction of known-good feet the cut would wrongly reject.
    false_positive_rate: float
    bad_count: int
    # Fraction of known-bad feet the cut would catch. None if no bad batch.
    true_positive_rate: Optional[float]

    def verdict(self) -> str:
        if self.true_positive_rate is None:
            return "no bad batch supplied — separation unknown"
        if self.true_positive_rate >= 0.9 and self.false_positive_rate <= 0.1:
            return "separates well"
        if self.true_positive_rate >= 0.6:
            return "partial separation — tighten or gather more data"
        return "does not separate — the metric or the labels are wrong"


def _metric_values(
    scan: BaselineScan, metric: str, roles: Optional[Sequence[str]]
) -> List[float]:
    return [getattr(f, metric) for f in scan.foot_reports(roles=roles)]


def calibrate(
    good: BaselineScan,
    bad: Optional[BaselineScan] = None,
    percentile_cut: float = 95.0,
    metrics: Sequence[str] = QUALITY_METRICS,
    roles: Optional[Sequence[str]] = PLANTING_ROLES,
) -> List[ThresholdSuggestion]:
    """Suggest gate thresholds from a known-good batch.

    The cut is the ``percentile_cut``-th percentile of the good batch, so
    by construction it rejects ``100 - percentile_cut`` percent of known
    good data. When a known-bad batch is supplied, the suggestion also
    reports how much of it the cut would catch — that number is the whole
    reason for doing this instead of guessing.

    ``roles`` limits which bones feed the distribution. It defaults to the
    bones that actually ground the character: a toe tip rolls through
    stance, so including it would set the cut from a movement that is not
    slide at all. Pass ``roles=None`` to pool every bone.
    """
    suggestions: List[ThresholdSuggestion] = []
    for metric in metrics:
        good_values = _metric_values(good, metric, roles)
        if not good_values:
            continue
        cut = percentile(good_values, percentile_cut)
        false_positive_rate = sum(1 for v in good_values if v > cut) / len(good_values)

        bad_count = 0
        true_positive_rate: Optional[float] = None
        if bad is not None:
            bad_values = _metric_values(bad, metric, roles)
            bad_count = len(bad_values)
            if bad_values:
                true_positive_rate = sum(1 for v in bad_values if v > cut) / len(
                    bad_values
                )
        suggestions.append(
            ThresholdSuggestion(
                metric=metric,
                cut=cut,
                percentile=percentile_cut,
                good_count=len(good_values),
                false_positive_rate=false_positive_rate,
                bad_count=bad_count,
                true_positive_rate=true_positive_rate,
            )
        )
    return suggestions


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _distribution(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {}
    return {
        "n": len(values),
        "min": min(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values),
    }


def format_report(
    scan: BaselineScan, suggestions: Optional[Sequence[ThresholdSuggestion]] = None
) -> str:
    """Render a scan as Markdown — paste it back into docs/01."""
    lines: List[str] = ["# Baseline scan", ""]
    lines.append(
        "| clip | fps | root motion | frozen | foot | role | contact | events | slide/s | slide max |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for clip in scan.clips:
        for foot in clip.feet:
            prefix = "| {} | {:.0f} | {} | {} | {} | {} |".format(
                clip.clip,
                clip.fps,
                "yes" if clip.root_motion else "no",
                clip.frozen_trimmed or "-",
                _short(foot.foot),
                foot.role,
            )
            if not foot.measurable:
                lines.append(prefix + " — | — | — | — |")
                continue
            lines.append(
                prefix
                + " {:.1%} | {} | {:.4f} | {:.4f} |".format(
                    foot.contact_ratio,
                    foot.contact_events,
                    foot.slide_speed_norm,
                    foot.slide_max_norm,
                )
            )

    unmeasurable = [
        (clip.clip, foot)
        for clip in scan.clips
        for foot in clip.feet
        if not foot.measurable
    ]
    if unmeasurable:
        lines.extend(["", "## Not measured", ""])
        for clip_name, foot in unmeasurable:
            lines.append(
                "- `{}` / {}: {}".format(
                    clip_name, _short(foot.foot), "; ".join(foot.notes) or "unknown reason"
                )
            )

    planting = scan.foot_reports(roles=PLANTING_ROLES)
    lines.extend(
        [
            "",
            "## Distribution (planting roles: {})".format(", ".join(PLANTING_ROLES)),
            "",
        ]
    )
    lines.append("| metric | n | min | p50 | p95 | max |")
    lines.append("|---|---|---|---|---|---|")
    for metric in QUALITY_METRICS:
        stats = _distribution([getattr(f, metric) for f in planting])
        if not stats:
            continue
        lines.append(
            "| {} | {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} |".format(
                metric,
                stats["n"],
                stats["min"],
                stats["p50"],
                stats["p95"],
                stats["max"],
            )
        )

    roles = sorted({f.role for f in scan.foot_reports()})
    if len(roles) > 1:
        lines.extend(
            ["", "## By role (slide/s)", "", "| role | n | p50 | max |", "|---|---|---|---|"]
        )
        for role in roles:
            values = [f.slide_speed_norm for f in scan.foot_reports(roles=(role,))]
            if not values:
                continue
            lines.append(
                "| {} | {} | {:.4f} | {:.4f} |".format(
                    role, len(values), percentile(values, 50), max(values)
                )
            )

    if suggestions:
        lines.extend(["", "## Suggested thresholds", ""])
        lines.append("| metric | cut | from | good n | catches bad | rejects good |")
        lines.append("|---|---|---|---|---|---|")
        for s in suggestions:
            catches = (
                "—"
                if s.true_positive_rate is None
                else "{:.0%}".format(s.true_positive_rate)
            )
            lines.append(
                "| {} | {:.4f} | p{:.0f} | {} | {} | {:.0%} |".format(
                    s.metric,
                    s.cut,
                    s.percentile,
                    s.good_count,
                    catches,
                    s.false_positive_rate,
                )
            )
        lines.extend(["", "Verdicts:"])
        for s in suggestions:
            lines.append("- `{}`: {}".format(s.metric, s.verdict()))
    return "\n".join(lines)


__all__ = [
    "PLANTING_ROLES",
    "QUALITY_METRICS",
    "BaselineScan",
    "ClipBaseline",
    "ThresholdSuggestion",
    "analyse_clips",
    "calibrate",
    "format_report",
    "mean",
    "median",
    "percentile",
]
