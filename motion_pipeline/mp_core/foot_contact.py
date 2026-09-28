"""mp_core.foot_contact

Foot-ground contact detection and slide measurement.

Pure stdlib maths — no Maya, no UE — mirroring the split the Maya->UE
pipeline already uses: reading the scene is one job, judging it is
another. Every metric here is one the Step 2 quality gate will threshold
on, so it has to be testable without either application installed.

Positions are world space. ``up_index`` names the component that points
up (2 = Z as in UE and Z-up Maya, 1 = Y).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

Vec3 = Tuple[float, float, float]

# Roles whose contact actually pins the character to the ground.
#
# A toe tip rolls through stance, so its "slide" is large and legitimate;
# mixing it into the same distribution as the ankle makes the ankle's
# numbers unreadable (measured: ~10x on a stock Mixamo walk). Toe tips are
# still measured, just kept out of the gate — see baseline.calibrate().
PLANTING_ROLES = ("foot", "ball", "unknown")

ROLE_TOE_TIP = "toe_tip"
ROLE_BALL = "ball"
ROLE_FOOT = "foot"
ROLE_UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContactConfig:
    """Thresholds used to *detect* contact — not to judge quality.

    Deciding what counts as a failing slide is ``baseline.calibrate()``'s
    job. These values only answer "is the foot on the ground right now".
    """

    # How close to the clip's lowest foot height still counts as contact,
    # as a fraction of skeleton height.
    height_tolerance_ratio: float = 0.02

    # Frames dropped from each end of a contact run. Being inside the
    # height tolerance does not mean the foot has settled: the frames
    # where it is still descending or already lifting travel at swing
    # speed and would otherwise be scored as slide.
    contact_trim_frames: int = 1

    # A contact run shorter than this is noise, not a contact event.
    min_contact_frames: int = 2

    # Net root displacement above this fraction of skeleton height means
    # the clip carries root motion rather than being authored in place.
    #
    # Net displacement, deliberately not path length: an in-place walk
    # still sways the hips a few centimetres side to side, and path length
    # calls that root motion — which then makes the planted foot's
    # legitimate backward sweep score as slide.
    root_motion_travel_ratio: float = 0.05

    # Below this fraction of frames in contact, the clip is reported as
    # unmeasurable instead of scored (airborne clips, pedestal idles).
    min_contact_ratio_for_measurement: float = 0.05

    # Movement below this fraction of skeleton height counts as frozen.
    # Leading and trailing frozen frames are dropped before measuring: an
    # export whose keys extend past the animation leaves a static pose at
    # the end, and sampling it would dilute every ratio.
    frozen_tolerance_ratio: float = 1e-4


# ---------------------------------------------------------------------------
# Input / output shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FootInfo:
    """What a tracked bone represents, so metrics can be grouped by role."""

    role: str = ROLE_UNKNOWN
    side: str = ""

    def label(self) -> str:
        return "{} {}".format(self.side, self.role).strip()


@dataclass
class ClipSamples:
    """World-space bone positions for one clip, one entry per sampled frame."""

    name: str
    fps: float
    frames: List[int]
    feet: Dict[str, List[Vec3]]
    root: List[Vec3]
    scale_ref: float
    up_index: int = 2
    foot_info: Dict[str, FootInfo] = field(default_factory=dict)

    def info_for(self, foot: str) -> FootInfo:
        return self.foot_info.get(foot, FootInfo())


@dataclass
class FootReport:
    """Slide metrics for a single foot."""

    foot: str
    total_frames: int
    contact_frames: int
    contact_ratio: float
    contact_events: int
    root_motion: bool
    slide_total_norm: float
    slide_max_norm: float
    slide_speed_norm: float
    role: str = ROLE_UNKNOWN
    side: str = ""
    measurable: bool = True
    notes: List[str] = field(default_factory=list)

    def plants(self) -> bool:
        """True when this bone's contact is a valid grounding signal."""
        return self.role in PLANTING_ROLES


# ---------------------------------------------------------------------------
# Small vector helpers (kept local — nothing else needs them yet)
# ---------------------------------------------------------------------------


def _horizontal_distance(a: Vec3, b: Vec3, up: int) -> float:
    total = 0.0
    for i in range(3):
        if i == up:
            continue
        delta = a[i] - b[i]
        total += delta * delta
    return total ** 0.5


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("median() of empty sequence")
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_root_motion(samples: ClipSamples, config: ContactConfig) -> bool:
    """True when the root bone actually translates across the clip.

    Uses net displacement, not path length. An in-place walk sways the
    hips several centimetres and returns to where it started; path length
    would call that root motion, and root-motion mode then scores the
    planted foot's legitimate backward sweep as slide — measured at ~40x
    the real figure on a stock Mixamo walk.
    """
    if len(samples.root) < 2:
        return False
    net = _horizontal_distance(samples.root[0], samples.root[-1], samples.up_index)
    return net > config.root_motion_travel_ratio * (samples.scale_ref or 1.0)


def _distance(a: Vec3, b: Vec3) -> float:
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def moving_window(samples: ClipSamples, config: ContactConfig) -> Tuple[int, int]:
    """First and last frame index where anything actually moves.

    An export can carry keys well past the animation, leaving a static
    pose at the end — measured on a real file: a 273-frame scene that only
    walks for its first 36 frames. Sampling that tail dilutes every
    contact ratio and anchors the slide maxima, so the window is worth
    knowing rather than averaging over.
    """
    count = len(samples.root)
    if count < 2:
        return 0, max(count - 1, 0)

    tolerance = config.frozen_tolerance_ratio * (samples.scale_ref or 1.0)
    tracks = list(samples.feet.values()) + [samples.root]
    moving = [False] * count
    for track in tracks:
        if len(track) != count:
            continue
        for i in range(1, count):
            if _distance(track[i], track[i - 1]) > tolerance:
                moving[i] = True
                moving[i - 1] = True

    indices = [i for i, flag in enumerate(moving) if flag]
    if not indices:
        return 0, count - 1
    # Keep one lead-in frame so the step into motion stays measurable.
    return max(min(indices) - 1, 0), min(max(indices) + 1, count - 1)


def trim_to_motion(
    samples: ClipSamples, config: Optional[ContactConfig] = None
) -> Tuple[ClipSamples, int]:
    """Drop leading and trailing frozen frames. Returns (samples, dropped)."""
    config = config or ContactConfig()
    start, end = moving_window(samples, config)
    dropped = len(samples.frames) - (end - start + 1)
    if dropped <= 0:
        return samples, 0
    window = slice(start, end + 1)
    return (
        replace(
            samples,
            frames=samples.frames[window],
            feet={name: track[window] for name, track in samples.feet.items()},
            root=samples.root[window],
        ),
        dropped,
    )


def _contact_mask(positions: Sequence[Vec3], up: int, tolerance: float) -> List[bool]:
    ground = min(p[up] for p in positions)
    return [(p[up] - ground) <= tolerance for p in positions]


def _trim_contact_runs(mask: List[bool], trim: int) -> List[bool]:
    """Drop the first and last ``trim`` frames of every contact run.

    Runs no longer than ``2 * trim`` are left alone — trimming them would
    erase short contacts entirely rather than tighten them.
    """
    if trim <= 0:
        return list(mask)
    trimmed = list(mask)
    index = 0
    while index < len(mask):
        if not mask[index]:
            index += 1
            continue
        end = index
        while end < len(mask) and mask[end]:
            end += 1
        if end - index > 2 * trim:
            for offset in range(trim):
                trimmed[index + offset] = False
                trimmed[end - 1 - offset] = False
        index = end
    return trimmed


def _count_contact_events(mask: Sequence[bool], min_frames: int) -> int:
    events = 0
    run = 0
    for flag in mask:
        if flag:
            run += 1
        else:
            if run >= min_frames:
                events += 1
            run = 0
    if run >= min_frames:
        events += 1
    return events


def _slide_deviations(
    positions: Sequence[Vec3],
    mask: Sequence[bool],
    up: int,
    fps: float,
    root_motion: bool,
) -> Tuple[List[float], float]:
    """Per-step horizontal movement of the foot while it is planted.

    Returns (deviations, contact_seconds). A perfectly planted foot in a
    root-motion clip moves zero per step, so the ideal baseline is 0.

    In-place clips are different: the planted foot is *supposed* to sweep
    backwards at a steady rate (that is what in-place locomotion is). The
    metric there is deviation from that steady rate, so the baseline is
    the median step rather than zero.
    """
    steps: List[float] = []
    for i in range(1, len(positions)):
        if mask[i] and mask[i - 1]:
            steps.append(_horizontal_distance(positions[i], positions[i - 1], up))

    if not steps:
        return [], 0.0

    baseline = 0.0 if root_motion else _median(steps)
    deviations = [abs(step - baseline) for step in steps]
    seconds = (len(steps) / fps) if fps else 0.0
    return deviations, seconds


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def analyse_foot(
    samples: ClipSamples,
    foot: str,
    config: ContactConfig,
    root_motion: Optional[bool] = None,
) -> FootReport:
    """Measure one foot of one clip."""
    positions = samples.feet[foot]
    total = len(positions)
    info = samples.info_for(foot)
    if root_motion is None:
        root_motion = detect_root_motion(samples, config)

    report = FootReport(
        foot=foot,
        total_frames=total,
        contact_frames=0,
        contact_ratio=0.0,
        contact_events=0,
        root_motion=root_motion,
        slide_total_norm=0.0,
        slide_max_norm=0.0,
        slide_speed_norm=0.0,
        role=info.role,
        side=info.side,
    )

    if info.role == ROLE_TOE_TIP:
        report.notes.append(
            "toe tip rolls through stance; measured but not a grounding signal"
        )

    if total < 2:
        report.measurable = False
        report.notes.append("not enough frames to measure")
        return report

    up = samples.up_index
    tolerance = config.height_tolerance_ratio * samples.scale_ref
    mask = _trim_contact_runs(
        _contact_mask(positions, up, tolerance), config.contact_trim_frames
    )

    report.contact_frames = sum(mask)
    report.contact_ratio = report.contact_frames / total
    report.contact_events = _count_contact_events(mask, config.min_contact_frames)

    if report.contact_ratio < config.min_contact_ratio_for_measurement:
        report.measurable = False
        report.notes.append(
            "contact ratio {:.1%} below {:.0%} — no ground contact to measure".format(
                report.contact_ratio, config.min_contact_ratio_for_measurement
            )
        )
        return report

    deviations, seconds = _slide_deviations(
        positions, mask, up, samples.fps, root_motion
    )
    scale = samples.scale_ref or 1.0
    report.slide_total_norm = sum(deviations) / scale
    report.slide_max_norm = (max(deviations) / scale) if deviations else 0.0
    report.slide_speed_norm = (
        (sum(deviations) / seconds / scale) if seconds > 0 else 0.0
    )
    if not deviations:
        report.measurable = False
        report.notes.append("no consecutive contact frames — slide not measurable")
    return report


def analyse_clip(
    samples: ClipSamples, config: Optional[ContactConfig] = None
) -> List[FootReport]:
    """Measure every foot in a clip under one shared root-motion verdict."""
    config = config or ContactConfig()
    root_motion = detect_root_motion(samples, config)
    return [
        analyse_foot(samples, foot, config, root_motion)
        for foot in sorted(samples.feet)
    ]


__all__ = [
    "PLANTING_ROLES",
    "ROLE_BALL",
    "ROLE_FOOT",
    "ROLE_TOE_TIP",
    "ROLE_UNKNOWN",
    "ClipSamples",
    "ContactConfig",
    "FootInfo",
    "FootReport",
    "analyse_clip",
    "analyse_foot",
    "detect_root_motion",
    "moving_window",
    "trim_to_motion",
]
