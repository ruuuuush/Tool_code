"""mp_core.synth

Synthetic degradation, used to validate the slide metric and to stand up
a known-bad batch for threshold calibration.

Why synthetic: slide is a property of the *source* data, and a pipeline
cannot conjure a corpus of genuinely bad motion. Injecting a known
quantity of jitter gives a bad batch whose magnitude is controlled, which
is what turns "the metric looks reasonable" into "the metric responds to
slide at the rate it should".

That second claim is the one worth having: it is checkable arithmetic,
not an opinion.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

from .baseline import (
    BaselineScan,
    ThresholdSuggestion,
    analyse_clips,
    calibrate,
    percentile,
)
from .foot_contact import (
    PLANTING_ROLES,
    ClipSamples,
    ContactConfig,
    Vec3,
    trim_to_motion,
)

# Kept inside the linear band deliberately. A real stride is roughly 6 cm
# on a 178 cm character (~0.034 normalised), and the in-place metric
# saturates once the injected zigzag (2a) approaches that — so a default
# sweep that climbs to 2a = 0.08 measures the ceiling, not the metric.
DEFAULT_AMPLITUDES = (0.0, 0.0025, 0.005, 0.01)


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------


def sweep_axis(positions: Sequence[Vec3], up: int) -> int:
    """The horizontal axis this foot travels furthest along.

    Picked by total variation rather than start-to-end displacement, so a
    looping clip that returns to its start still reports the right axis.
    """
    horizontal = [i for i in range(3) if i != up]
    return max(
        horizontal,
        key=lambda i: sum(
            abs(positions[j][i] - positions[j - 1][i]) for j in range(1, len(positions))
        ),
    )


def inject_sweep_jitter(
    samples: ClipSamples,
    amplitude_ratio: float,
    feet: Optional[Sequence[str]] = None,
    period: int = 1,
) -> ClipSamples:
    """Perturb a foot's horizontal path to simulate slide.

    ``amplitude_ratio`` is a fraction of skeleton height, so the injected
    magnitude is independent of character scale.

    The offset is a square wave of +/-``amplitude``, which makes each
    per-step displacement alternate by ``2 * amplitude``. Since the metric
    is deviation from the median step, that lands directly in
    ``slide_max_norm`` — so a run at ratio ``a`` should measure roughly
    ``2a`` above the undegraded baseline. That predictability is the point:
    it is the assertion the tests check.
    """
    if period < 1:
        raise ValueError("period must be >= 1")

    targets = list(feet) if feet is not None else sorted(samples.feet)
    amplitude = amplitude_ratio * (samples.scale_ref or 1.0)

    new_feet: Dict[str, List[Vec3]] = {name: list(track) for name, track in samples.feet.items()}
    for foot in targets:
        positions = samples.feet.get(foot)
        if not positions:
            continue
        axis = sweep_axis(positions, samples.up_index)
        rebuilt: List[Vec3] = []
        for index, position in enumerate(positions):
            offset = amplitude if (index // period) % 2 == 0 else -amplitude
            coords = list(position)
            coords[axis] += offset
            rebuilt.append((coords[0], coords[1], coords[2]))
        new_feet[foot] = rebuilt

    return replace(
        samples,
        name="{}@jit{:.3f}".format(samples.name, amplitude_ratio),
        feet=new_feet,
    )


def degrade_batch(
    samples_list: Sequence[ClipSamples],
    amplitude_ratio: float,
    feet: Optional[Sequence[str]] = None,
    period: int = 1,
) -> List[ClipSamples]:
    return [
        inject_sweep_jitter(item, amplitude_ratio, feet=feet, period=period)
        for item in samples_list
    ]


# ---------------------------------------------------------------------------
# Calibration against the injected batch
# ---------------------------------------------------------------------------


class InjectedRun:
    """One degraded batch: what was injected, and what came back."""

    def __init__(
        self,
        amplitude_ratio: float,
        scan: BaselineScan,
        roles: Optional[Sequence[str]] = PLANTING_ROLES,
    ) -> None:
        self.amplitude_ratio = amplitude_ratio
        self.scan = scan
        self.roles = roles

    @property
    def expected_slide_max_norm(self) -> float:
        """A square-wave offset of ``a`` shifts every step by ``2a``."""
        return 2.0 * self.amplitude_ratio

    def values(self, metric: str = "slide_max_norm") -> List[float]:
        return [getattr(f, metric) for f in self.scan.foot_reports(roles=self.roles)]

    def p50(self, metric: str = "slide_max_norm") -> float:
        values = self.values(metric)
        return percentile(values, 50) if values else 0.0

    def maximum(self, metric: str = "slide_max_norm") -> float:
        values = self.values(metric)
        return max(values) if values else 0.0


def measure_injection(
    samples_list: Sequence[ClipSamples],
    amplitudes: Sequence[float] = DEFAULT_AMPLITUDES,
    config: Optional[ContactConfig] = None,
    roles: Optional[Sequence[str]] = PLANTING_ROLES,
    period: int = 1,
) -> Tuple[BaselineScan, List[InjectedRun]]:
    """Degrade a batch at each amplitude and measure every level.

    Returns (good_scan, runs) where ``runs`` is ordered by ascending
    amplitude and starts with the undegraded baseline.
    """
    config = config or ContactConfig()
    # Trim before degrading, not after: the injected zigzag moves every
    # frame, so a frozen tail would stop looking frozen and the degraded
    # batch would end up measured over a different window than the good one.
    prepared = [trim_to_motion(item, config)[0] for item in samples_list]
    good = analyse_clips(prepared, config, trim_frozen=False)
    runs: List[InjectedRun] = []
    for amplitude in amplitudes:
        scan = (
            good
            if amplitude == 0
            else analyse_clips(
                degrade_batch(prepared, amplitude, period=period),
                config,
                trim_frozen=False,
            )
        )
        runs.append(InjectedRun(amplitude, scan, roles=roles))
    return good, runs


def format_calibration_report(
    good: BaselineScan,
    runs: Sequence[InjectedRun],
    suggestions: Optional[Sequence[ThresholdSuggestion]] = None,
) -> str:
    """Render the injection response plus the thresholds it justifies."""
    lines: List[str] = ["# Calibration", ""]
    lines.extend(
        [
            "## Injected slide response",
            "",
            "Amplitude is a fraction of skeleton height. A square-wave offset of",
            "`a` shifts every per-step displacement by `2a`, so the measured",
            "`slide_max_norm` should sit about `2a` above the undegraded baseline.",
            "",
            "| injected a | expected +2a | measured p50 | measured max | slope |",
            "|---|---|---|---|---|",
        ]
    )

    baseline_p50 = runs[0].p50() if runs else 0.0
    previous = None
    for run in runs:
        p50 = run.p50()
        slope = "—" if previous is None else "{:.2f}".format(
            (p50 - previous) / (2.0 * run.amplitude_ratio)
            if run.amplitude_ratio > 0
            else 0.0
        )
        lines.append(
            "| {:.3f} | {:.4f} | {:.4f} | {:.4f} | {} |".format(
                run.amplitude_ratio,
                run.expected_slide_max_norm,
                p50,
                run.maximum(),
                slope,
            )
        )
        previous = p50

    values = [run.p50() for run in runs]
    # A 2% band, not an exact comparison. Past the saturation point the
    # metric plateaus, and a plateau carries microscopic noise; an exact
    # test calls that "not monotonic" and buries the real signal.
    span = max(values) if values else 0.0
    tolerance = 0.02 * span
    monotonic = all(
        values[i] >= values[i - 1] - tolerance for i in range(1, len(values))
    )
    lines.extend(
        [
            "",
            "Slope is measured-rise over injected-rise; 1.00 means the metric",
            "moved exactly as much as the injection.",
            "",
            "Monotonic in injected slide (within 2%): **{}**".format(
                "yes" if monotonic else "NO"
            ),
            "Baseline p50: {:.4f}".format(baseline_p50),
            "",
            "Ceiling: the in-place metric is deviation from the *median* step,",
            "so it saturates once the injected zigzag exceeds the stride itself —",
            "a bigger zigzag just flips the sign of the step, and the deviation",
            "caps at the stride length. Slope below 1.00 at large amplitudes is",
            "that ceiling, not a broken metric. Keep amplitudes inside the linear",
            "band (roughly 2a below the mean stride) when reading the slope.",
        ]
    )

    if suggestions:
        lines.extend(["", "## Suggested thresholds (from the good batch only)", ""])
        lines.append("| metric | cut | from | n |")
        lines.append("|---|---|---|---|")
        for s in suggestions:
            lines.append(
                "| {} | {:.4f} | p{:.0f} | {} |".format(
                    s.metric, s.cut, s.percentile, s.good_count
                )
            )
        degraded = runs[-1] if runs else None
        if degraded is not None and degraded.amplitude_ratio > 0:
            lines.extend(
                [
                    "",
                    "Separation against the batch injected at {:.3f}:".format(
                        degraded.amplitude_ratio
                    ),
                    "",
                    "| metric | cut | catches injected | rejects good |",
                    "|---|---|---|---|",
                ]
            )
            checks = calibrate(
                good,
                degraded.scan,
                percentile_cut=suggestions[0].percentile,
                metrics=[s.metric for s in suggestions],
                roles=degraded.roles,
            )
            for check in checks:
                catches = (
                    "—"
                    if check.true_positive_rate is None
                    else "{:.0%}".format(check.true_positive_rate)
                )
                lines.append(
                    "| {} | {:.4f} | {} | {:.0%} |".format(
                        check.metric,
                        check.cut,
                        catches,
                        check.false_positive_rate,
                    )
                )
            for check in checks:
                lines.append("- `{}`: {}".format(check.metric, check.verdict()))
    return "\n".join(lines)


__all__ = [
    "DEFAULT_AMPLITUDES",
    "InjectedRun",
    "degrade_batch",
    "format_calibration_report",
    "inject_sweep_jitter",
    "measure_injection",
    "sweep_axis",
]
