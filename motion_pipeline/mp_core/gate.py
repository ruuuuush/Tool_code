"""mp_core.gate

Applies calibrated thresholds to a scan and returns an accept/reject
verdict per clip.

This is what makes augmentation safe. Generating more clips is easy; every
generated clip that slides is a *worse* database entry than the clip it
came from, so without a gate, augmentation is as likely to be
net-negative as net-positive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .baseline import QUALITY_METRICS, BaselineScan, ThresholdSuggestion
from .foot_contact import PLANTING_ROLES

Check = Tuple[str, float, float, bool]


@dataclass(frozen=True)
class Thresholds:
    """Cut-offs for the gate, one per metric name."""

    cuts: Dict[str, float]

    @classmethod
    def from_suggestions(cls, suggestions: Sequence[ThresholdSuggestion]) -> "Thresholds":
        """Build from ``baseline.calibrate()`` output."""
        return cls({s.metric: s.cut for s in suggestions})

    def describe(self) -> str:
        if not self.cuts:
            return "none configured"
        return ", ".join(
            "{} <= {:.4f}".format(metric, cut)
            for metric, cut in sorted(self.cuts.items())
        )


@dataclass
class ClipVerdict:
    clip: str
    accepted: bool
    checks: List[Check] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def worst(self) -> Optional[Check]:
        """The check with the least headroom, by value-over-cut ratio."""
        if not self.checks:
            return None

        def ratio(check: Check) -> float:
            _, value, cut, _ = check
            if cut > 0:
                return value / cut
            return float("inf") if value > 0 else 0.0

        return max(self.checks, key=ratio)


@dataclass
class GateReport:
    thresholds: Thresholds
    verdicts: List[ClipVerdict] = field(default_factory=list)

    def accepted(self) -> List[str]:
        return [v.clip for v in self.verdicts if v.accepted]

    def rejected(self) -> List[str]:
        return [v.clip for v in self.verdicts if not v.accepted]

    def acceptance_rate(self) -> float:
        if not self.verdicts:
            return 0.0
        return len(self.accepted()) / len(self.verdicts)


def evaluate(
    scan: BaselineScan,
    thresholds: Thresholds,
    roles: Optional[Sequence[str]] = PLANTING_ROLES,
    metrics: Sequence[str] = QUALITY_METRICS,
) -> GateReport:
    """Score every clip in a scan.

    A clip is only as good as its worst planted foot, so each metric is
    taken as the maximum across the planting-role feet rather than an
    average: one foot dragging is enough to make the clip unusable.
    """
    report = GateReport(thresholds=thresholds)
    for clip in scan.clips:
        planted = [
            foot
            for foot in clip.feet
            if foot.measurable and (roles is None or foot.role in roles)
        ]
        verdict = ClipVerdict(clip=clip.clip, accepted=True)

        if not planted:
            verdict.accepted = False
            verdict.reasons.append("no measurable planting foot")
            report.verdicts.append(verdict)
            continue

        for metric in metrics:
            cut = thresholds.cuts.get(metric)
            if cut is None:
                continue
            value = max(getattr(foot, metric) for foot in planted)
            passed = value <= cut
            verdict.checks.append((metric, value, cut, passed))
            if not passed:
                verdict.accepted = False
                verdict.reasons.append(
                    "{} {:.4f} over cut {:.4f}".format(metric, value, cut)
                )
        report.verdicts.append(verdict)
    return report


def _worst_by_clip(
    scan: BaselineScan,
    roles: Optional[Sequence[str]],
    metrics: Sequence[str],
) -> Dict[str, Dict[str, float]]:
    """Per clip: the worst planting-role value of each metric."""
    table: Dict[str, Dict[str, float]] = {}
    for clip in scan.clips:
        planted = [
            foot
            for foot in clip.feet
            if foot.measurable and (roles is None or foot.role in roles)
        ]
        if not planted:
            continue
        table[clip.clip] = {
            metric: max(getattr(foot, metric) for foot in planted)
            for metric in metrics
        }
    return table


def evaluate_against_source(
    variant_scan: BaselineScan,
    source_scan: BaselineScan,
    source_of: Dict[str, str],
    tolerance: float = 0.25,
    floor: float = 0.0,
    roles: Optional[Sequence[str]] = PLANTING_ROLES,
    metrics: Sequence[str] = QUALITY_METRICS,
) -> GateReport:
    """Gate each variant against the clip it was derived from.

    A global cut is the wrong instrument for augmentation. The source
    clips are acceptable by definition — they are what shipped — so a cut
    calibrated on them will reject them: measured on a 2-clip corpus,
    every source and every variant failed, including the unmodified
    control. What actually matters is whether a variant is *materially
    worse than its own source*.

    ``source_of`` maps a variant clip name to its source clip name. The
    resulting cut is stored on each check, so the report reads like an
    absolute gate even though the comparison is relative.
    """
    baselines = _worst_by_clip(source_scan, roles, metrics)
    report = GateReport(thresholds=Thresholds({}))

    for clip in variant_scan.clips:
        verdict = ClipVerdict(clip=clip.clip, accepted=True)
        baseline = baselines.get(source_of.get(clip.clip, ""))

        if baseline is None:
            verdict.accepted = False
            verdict.reasons.append(
                "no source baseline for {}".format(source_of.get(clip.clip, "<unmapped>"))
            )
            report.verdicts.append(verdict)
            continue

        planted = [
            foot
            for foot in clip.feet
            if foot.measurable and (roles is None or foot.role in roles)
        ]
        if not planted:
            verdict.accepted = False
            verdict.reasons.append("no measurable planting foot")
            report.verdicts.append(verdict)
            continue

        for metric in metrics:
            source_value = baseline.get(metric)
            if source_value is None:
                continue
            cut = source_value * (1.0 + tolerance) + floor
            value = max(getattr(foot, metric) for foot in planted)
            passed = value <= cut
            verdict.checks.append((metric, value, cut, passed))
            if not passed:
                verdict.accepted = False
                verdict.reasons.append(
                    "{} {:.4f} over {:.4f} (source {:.4f}, +{:.0%} allowed)".format(
                        metric, value, cut, source_value, tolerance
                    )
                )
        report.verdicts.append(verdict)
    return report


def format_gate_report(report: GateReport) -> str:
    """Render the verdicts as Markdown."""
    lines: List[str] = ["# Quality gate", ""]
    if report.thresholds.cuts:
        lines.append("Thresholds: {}".format(report.thresholds.describe()))
    elif any(verdict.checks for verdict in report.verdicts):
        lines.append(
            "Thresholds: per clip, relative to its source (cut shown per row)"
        )
    else:
        lines.append("Thresholds: {}".format(report.thresholds.describe()))

    lines.extend(
        [
            "",
            "| clip | verdict | tightest metric | value | cut |",
            "|---|---|---|---|---|",
        ]
    )
    for verdict in report.verdicts:
        worst = verdict.worst()
        if worst is None:
            lines.append(
                "| {} | {} | — | — | — |".format(
                    verdict.clip, "PASS" if verdict.accepted else "REJECT"
                )
            )
            continue
        metric, value, cut, _ = worst
        lines.append(
            "| {} | {} | {} | {:.4f} | {:.4f} |".format(
                verdict.clip,
                "PASS" if verdict.accepted else "REJECT",
                metric,
                value,
                cut,
            )
        )

    if report.verdicts:
        lines.extend(
            [
                "",
                "Accepted {}/{} ({:.0%}).".format(
                    len(report.accepted()),
                    len(report.verdicts),
                    report.acceptance_rate(),
                ),
            ]
        )

    rejected = [v for v in report.verdicts if not v.accepted]
    if rejected:
        lines.extend(["", "## Rejected", ""])
        for verdict in rejected:
            lines.append(
                "- `{}`: {}".format(
                    verdict.clip, "; ".join(verdict.reasons) or "unknown reason"
                )
            )
    return "\n".join(lines)


__all__ = [
    "Check",
    "ClipVerdict",
    "GateReport",
    "Thresholds",
    "evaluate",
    "evaluate_against_source",
    "format_gate_report",
]
