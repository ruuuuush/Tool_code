"""mp_core

Application-agnostic core of the Motion Pipeline: contact detection,
slide metrics, and threshold calibration for the Step 2 quality gate.

Nothing in here imports Maya or Unreal. Samplers (``mp_maya``, later
``mp_unreal``) feed these functions plain data, which is what keeps every
metric unit-testable without either application installed.
"""

from .foot_contact import (
    PLANTING_ROLES,
    ROLE_BALL,
    ROLE_FOOT,
    ROLE_TOE_TIP,
    ROLE_UNKNOWN,
    ClipSamples,
    ContactConfig,
    FootInfo,
    FootReport,
    analyse_clip,
    analyse_foot,
    detect_root_motion,
    moving_window,
    trim_to_motion,
)
from .baseline import (
    QUALITY_METRICS,
    BaselineScan,
    ClipBaseline,
    ThresholdSuggestion,
    analyse_clips,
    calibrate,
    format_report,
    mean,
    median,
    percentile,
)
from .synth import (
    DEFAULT_AMPLITUDES,
    InjectedRun,
    degrade_batch,
    format_calibration_report,
    inject_sweep_jitter,
    measure_injection,
    sweep_axis,
)
from .augment import (
    is_mirrorable,
    lateral_index,
    mirror_diagonal,
    mirror_map,
    opposite_name,
    retime_source_time,
    short_name,
    warped_frame_count,
    warped_range,
)
from .gate import (
    Check,
    ClipVerdict,
    GateReport,
    Thresholds,
    evaluate,
    evaluate_against_source,
    format_gate_report,
)
from .viz import (
    clip_inspection_svg,
    distribution_svg,
    html_report,
)

__all__ = [
    # foot_contact
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
    # baseline
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
    # synth
    "DEFAULT_AMPLITUDES",
    "InjectedRun",
    "degrade_batch",
    "format_calibration_report",
    "inject_sweep_jitter",
    "measure_injection",
    "sweep_axis",
    # augment
    "is_mirrorable",
    "lateral_index",
    "mirror_diagonal",
    "mirror_map",
    "opposite_name",
    "retime_source_time",
    "short_name",
    "warped_frame_count",
    "warped_range",
    # gate
    "Check",
    "ClipVerdict",
    "GateReport",
    "Thresholds",
    "evaluate",
    "evaluate_against_source",
    "format_gate_report",
    # viz
    "clip_inspection_svg",
    "distribution_svg",
    "html_report",
]
