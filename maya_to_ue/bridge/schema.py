"""bridge.schema

Manifest data classes for the Maya→UE animation pipeline.

The manifest is the single source of truth that decouples the Maya exporter
from the UE importer. Both ends read/write this structure; nothing about
the export/import convention is hard-coded into tool logic.

Schema versioning: only ``SCHEMA_VERSION`` is supported in v1. A future
``migrate()`` function will be added when the schema changes.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Severity levels (mirror design.md §4.2)
# ---------------------------------------------------------------------------

Severity = str


# ---------------------------------------------------------------------------
# Source / convention / destination
# ---------------------------------------------------------------------------

@dataclass
class Source:
    """Where the animation came from (Maya side)."""

    maya_scene: str = ""
    maya_version: str = ""
    preset: str = ""            # skeleton preset id, e.g. "ue_mannequin"
    skeleton_root: str = ""     # root bone name

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Source":
        if not isinstance(data, dict):
            raise ValueError("Source must be a mapping")
        return cls(
            maya_scene=data.get("maya_scene", ""),
            maya_version=data.get("maya_version", ""),
            preset=data.get("preset", ""),
            skeleton_root=data.get("skeleton_root", ""),
        )


@dataclass
class Convention:
    """Locked export conventions (see design.md §0)."""

    up_axis: str = "z"                  # recorded from source scene
    unit: str = "cm"                    # locked to cm
    frame_rate: int = 30
    axis_conversion: bool = False       # locked: no conversion

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Convention":
        if not isinstance(data, dict):
            raise ValueError("Convention must be a mapping")
        frame_rate = data.get("frame_rate", 30)
        if isinstance(frame_rate, bool):
            raise ValueError("Convention.frame_rate must be a positive integer")
        if isinstance(frame_rate, float) and not frame_rate.is_integer():
            raise ValueError("Convention.frame_rate must be a positive integer")
        if isinstance(frame_rate, str) and not frame_rate.strip().isdigit():
            raise ValueError("Convention.frame_rate must be a positive integer")
        try:
            frame_rate = int(frame_rate)
        except (TypeError, ValueError) as exc:
            raise ValueError("Convention.frame_rate must be a positive integer") from exc
        if frame_rate <= 0:
            raise ValueError("Convention.frame_rate must be a positive integer")
        up_axis = data.get("up_axis", "z")
        unit = data.get("unit", "cm")
        axis_conversion = data.get("axis_conversion", False)
        if not isinstance(up_axis, str) or not isinstance(unit, str):
            raise ValueError("Convention.up_axis and Convention.unit must be strings")
        if axis_conversion is not False:
            raise ValueError("Convention.axis_conversion is locked to False")
        return cls(
            up_axis=up_axis,
            unit=unit,
            frame_rate=frame_rate,
            axis_conversion=False,
        )


@dataclass
class SkeletonDelivery:
    """How the target Skeleton should be produced on the UE side.

    A rig has to exist in UE before any animation can bind to it. Rather
    than making that a manual prerequisite, the exporter can ship the rig
    in the same FBX and let the importer create the Skeleton first.
    """

    # Export the bind pose / skinned mesh alongside the animation.
    include_rig: bool = False
    # Create the Skeleton (and its SkeletalMesh) if skeleton_path is missing.
    create_if_missing: bool = False
    # Uniform scale applied when creating the SkeletalMesh, e.g. 50.0 for
    # assets authored in metres. Animations inherit this automatically.
    import_uniform_scale: float = 1.0
    # Name for the generated SkeletalMesh; empty means derive from the FBX.
    mesh_asset_name: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkeletonDelivery":
        if not isinstance(data, dict):
            raise ValueError("SkeletonDelivery must be a mapping")
        raw_scale = data.get("import_uniform_scale", 1.0)
        if isinstance(raw_scale, bool):
            raise ValueError("SkeletonDelivery.import_uniform_scale must be a number")
        try:
            scale = float(raw_scale)
        except (TypeError, ValueError):
            raise ValueError("SkeletonDelivery.import_uniform_scale must be a number")
        if scale <= 0:
            raise ValueError("SkeletonDelivery.import_uniform_scale must be > 0")
        return cls(
            include_rig=bool(data.get("include_rig", False)),
            create_if_missing=bool(data.get("create_if_missing", False)),
            import_uniform_scale=scale,
            mesh_asset_name=data.get("mesh_asset_name", ""),
        )


@dataclass
class UEDestination:
    """Where the assets should land in UE Content Browser."""

    content_root: str = ""              # e.g. /Game/Animations/Hero
    skeleton_path: str = ""             # e.g. /Game/Animations/Hero/Hero_Skeleton
    overwrite_policy: str = "rename"
    skeleton_delivery: SkeletonDelivery = field(default_factory=SkeletonDelivery)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UEDestination":
        if not isinstance(data, dict):
            raise ValueError("UEDestination must be a mapping")
        policy = data.get("overwrite_policy", "rename")
        if policy not in ("overwrite", "skip", "rename"):
            raise ValueError(
                "UEDestination.overwrite_policy must be 'overwrite', 'skip', or 'rename'"
            )
        return cls(
            content_root=data.get("content_root", ""),
            skeleton_path=data.get("skeleton_path", ""),
            overwrite_policy=policy,
            skeleton_delivery=SkeletonDelivery.from_dict(
                data.get("skeleton_delivery", {})
            ),
        )


# ---------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------

@dataclass
class Clip:
    """A single animation clip to be sliced from the FBX on the UE side."""

    name: str
    start: int
    end: int
    root_motion: bool = False

    def validate(self) -> None:
        """Raise ValueError if the clip definition is internally invalid."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Clip name cannot be empty")
        if isinstance(self.start, bool) or not isinstance(self.start, int):
            raise ValueError(f"Clip '{self.name}': start must be an integer, got {self.start!r}")
        if isinstance(self.end, bool) or not isinstance(self.end, int):
            raise ValueError(f"Clip '{self.name}': end must be an integer, got {self.end!r}")
        if self.start < 0:
            raise ValueError(f"Clip '{self.name}': start must be >= 0, got {self.start}")
        if self.end < self.start:
            raise ValueError(
                f"Clip '{self.name}': end ({self.end}) must be >= start ({self.start})"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Clip":
        if not isinstance(data, dict):
            raise ValueError("Clip must be a mapping")
        try:
            start = data["start"]
            end = data["end"]
            if isinstance(start, bool) or isinstance(end, bool):
                raise ValueError("Clip start and end must be integers")
            if isinstance(start, float) and not start.is_integer():
                raise ValueError("Clip start and end must be integers")
            if isinstance(end, float) and not end.is_integer():
                raise ValueError("Clip start and end must be integers")
            if isinstance(start, str) and not start.strip().lstrip("-").isdigit():
                raise ValueError("Clip start and end must be integers")
            if isinstance(end, str) and not end.strip().lstrip("-").isdigit():
                raise ValueError("Clip start and end must be integers")
            return cls(
                name=data["name"],
                start=int(start),
                end=int(end),
                root_motion=bool(data.get("root_motion", False)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid clip: {exc}") from exc


# ---------------------------------------------------------------------------
# Validation results (Maya-side check results embedded in manifest)
# ---------------------------------------------------------------------------

@dataclass
class CheckResultEntry:
    """A single validator's outcome, embedded in the manifest."""

    check: str                  # validator id, e.g. "scene.unit"
    level: Severity
    passed: bool
    message: str = ""
    auto_fixable: bool = False
    skipped: bool = False       # user switched it off; it never ran

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckResultEntry":
        if not isinstance(data, dict):
            raise ValueError("CheckResultEntry must be a mapping")
        level = data["level"]
        if level not in ("error", "warning", "info"):
            raise ValueError("CheckResultEntry.level is invalid")
        return cls(
            check=data["check"],
            level=level,
            passed=bool(data["passed"]),
            message=data.get("message", ""),
            auto_fixable=bool(data.get("auto_fixable", False)),
            skipped=bool(data.get("skipped", False)),
        )


@dataclass
class SkippedCheck:
    """A check the user switched off before exporting.

    Recorded so downstream can tell "passed" from "never ran" — a manifest
    that hides this is worse than one that reports failures.
    """

    check: str
    level: Severity

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkippedCheck":
        if not isinstance(data, dict):
            raise ValueError("SkippedCheck must be a mapping")
        level = data.get("level", "info")
        if level not in ("error", "warning", "info"):
            raise ValueError("SkippedCheck.level is invalid")
        check = data.get("check", "")
        if not check:
            raise ValueError("SkippedCheck.check is required")
        return cls(check=check, level=level)


@dataclass
class ValidationSummary:
    """Aggregated validation status written by the Maya exporter."""

    status: str = "passed"
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    results: List[CheckResultEntry] = field(default_factory=list)
    skipped: List[SkippedCheck] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationSummary":
        if not isinstance(data, dict):
            raise ValueError("ValidationSummary must be a mapping")
        status = data.get("status", "passed")
        if status not in ("passed", "passed_with_warnings", "failed"):
            raise ValueError("ValidationSummary.status is invalid")
        result_entries = data.get("results", [])
        if not isinstance(result_entries, list):
            raise ValueError("ValidationSummary.results must be a list")
        result_entries = [CheckResultEntry.from_dict(r) for r in result_entries]
        # 旧 manifest 没有这个键：缺就是没跳过任何东西，不该报错。
        skipped_entries = data.get("skipped", [])
        if not isinstance(skipped_entries, list):
            raise ValueError("ValidationSummary.skipped must be a list")
        skipped_entries = [SkippedCheck.from_dict(s) for s in skipped_entries]
        raw_counts = (data.get("errors", 0), data.get("warnings", 0), data.get("infos", 0))
        if any(isinstance(value, bool) for value in raw_counts):
            raise ValueError("ValidationSummary counts must be integers")
        errors, warnings, infos = (int(value) for value in raw_counts)
        if min(errors, warnings, infos) < 0:
            raise ValueError("ValidationSummary counts cannot be negative")
        return cls(
            status=status,
            errors=errors,
            warnings=warnings,
            infos=infos,
            results=result_entries,
            skipped=skipped_entries,
        )

    @classmethod
    def from_entries(cls, entries: List[CheckResultEntry]) -> "ValidationSummary":
        """Build a summary from a list of check results.

        Skipped entries never ran, so they count as neither pass nor failure —
        they are listed separately instead.
        """
        errors = sum(1 for e in entries if e.level == "error" and not e.passed and not e.skipped)
        warnings = sum(1 for e in entries if e.level == "warning" and not e.passed and not e.skipped)
        infos = sum(1 for e in entries if e.level == "info" and not e.passed and not e.skipped)
        if errors:
            status = "failed"
        elif warnings:
            status = "passed_with_warnings"
        else:
            status = "passed"
        return cls(
            status=status,
            errors=errors,
            warnings=warnings,
            infos=infos,
            results=list(entries),
            skipped=[SkippedCheck(check=e.check, level=e.level) for e in entries if e.skipped],
        )


# ---------------------------------------------------------------------------
# Import result (UE-side, written back after import)
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    """UE-side import outcome, written back into the manifest."""

    status: str = "pending"
    imported_clips: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    # Clips skipped by overwrite policy; lets the UI tell "跳过" from "没提".
    skipped_clips: List[str] = field(default_factory=list)
    # Set when the import created the rig assets (first delivery); "" = reused.
    skeleton_path: str = ""
    skeletal_mesh_path: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImportResult":
        if not isinstance(data, dict):
            raise ValueError("ImportResult must be a mapping")
        status = data.get("status", "pending")
        if status not in ("pending", "success", "partial", "failed"):
            raise ValueError("ImportResult.status is invalid")
        imported_clips = data.get("imported_clips", [])
        errors = data.get("errors", [])
        if not isinstance(imported_clips, list) or not isinstance(errors, list):
            raise ValueError("ImportResult.imported_clips and ImportResult.errors must be lists")
        skipped_clips = data.get("skipped_clips", [])
        if not isinstance(skipped_clips, list):
            raise ValueError("ImportResult.skipped_clips must be a list")
        return cls(
            status=status,
            imported_clips=list(imported_clips),
            errors=list(errors),
            skipped_clips=list(skipped_clips),
            # Older manifests lack these keys; "" means "no rig was created".
            skeleton_path=data.get("skeleton_path", "") or "",
            skeletal_mesh_path=data.get("skeletal_mesh_path", "") or "",
        )


# ---------------------------------------------------------------------------
# Root manifest
# ---------------------------------------------------------------------------

@dataclass
class Manifest:
    """Top-level manifest structure."""

    version: str = SCHEMA_VERSION
    export_time: str = ""
    tool_version: str = ""
    source: Source = field(default_factory=Source)
    convention: Convention = field(default_factory=Convention)
    clips: List[Clip] = field(default_factory=list)
    fbx_path: str = ""
    ue_destination: UEDestination = field(default_factory=UEDestination)
    validation: ValidationSummary = field(default_factory=ValidationSummary)
    result: ImportResult = field(default_factory=ImportResult)
    # 本次导出执行的关键帧抽稀摘要：{"level", "keys_before", "keys_after"}。
    # None = 未抽稀（档位关闭）。交付可复现性留痕，UE 导入不读它。
    thinning: Optional[Dict[str, Any]] = None

    # -- construction -------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Manifest":
        if not isinstance(data, dict):
            raise ValueError("Manifest root must be a mapping")
        source = data.get("source", {})
        convention = data.get("convention", {})
        clips = data.get("clips", [])
        ue_destination = data.get("ue_destination", {})
        validation = data.get("validation", {})
        result = data.get("result", {})
        if not all(isinstance(value, dict) for value in (source, convention, ue_destination, validation, result)):
            raise ValueError("Manifest object sections must be mappings")
        if not isinstance(clips, list):
            raise ValueError("Manifest.clips must be a list")
        return cls(
            version=data.get("version", SCHEMA_VERSION),
            export_time=data.get("export_time", ""),
            tool_version=data.get("tool_version", ""),
            source=Source.from_dict(source),
            convention=Convention.from_dict(convention),
            clips=[Clip.from_dict(c) for c in clips],
            fbx_path=data.get("fbx_path", ""),
            ue_destination=UEDestination.from_dict(ue_destination),
            validation=ValidationSummary.from_dict(validation),
            result=ImportResult.from_dict(result),
            # 旧 manifest 没有这个键：未抽稀与"记录缺失"同等对待。
            thinning=data.get("thinning"),
        )

    @classmethod
    def new(cls, **kwargs: Any) -> "Manifest":
        """Create a fresh manifest with export_time set to now (UTC)."""
        m = cls(**kwargs)
        m.export_time = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        return m

    # -- serialization ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # -- validation ---------------------------------------------------------

    def validate(self) -> None:
        """Validate the whole manifest. Raises ValueError on any problem."""
        if self.version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported manifest version: {self.version} (expected {SCHEMA_VERSION})"
            )
        if not isinstance(self.convention.up_axis, str) or self.convention.up_axis.lower() not in ("y", "z"):
            raise ValueError("Convention.up_axis must be 'y' or 'z'")
        if not isinstance(self.convention.unit, str) or self.convention.unit != "cm":
            raise ValueError("Convention.unit is locked to 'cm'")
        if isinstance(self.convention.frame_rate, bool) or not isinstance(self.convention.frame_rate, int) or self.convention.frame_rate <= 0:
            raise ValueError("Convention.frame_rate must be a positive integer")
        if self.convention.axis_conversion is not False:
            raise ValueError("Convention.axis_conversion is locked to False")
        if self.validation.status not in ("passed", "passed_with_warnings", "failed"):
            raise ValueError("ValidationSummary.status is invalid")
        expected_summary = ValidationSummary.from_entries(self.validation.results)
        if (
            (self.validation.errors, self.validation.warnings, self.validation.infos, self.validation.status)
            != (expected_summary.errors, expected_summary.warnings, expected_summary.infos, expected_summary.status)
        ):
            raise ValueError("ValidationSummary does not match its results")
        if not isinstance(self.validation.errors, int) or isinstance(self.validation.errors, bool) or not isinstance(self.validation.warnings, int) or isinstance(self.validation.warnings, bool) or not isinstance(self.validation.infos, int) or isinstance(self.validation.infos, bool):
            raise ValueError("ValidationSummary counts must be integers")
        if self.validation.errors < 0 or self.validation.warnings < 0 or self.validation.infos < 0:
            raise ValueError("ValidationSummary counts cannot be negative")
        if self.result.status not in ("pending", "success", "partial", "failed"):
            raise ValueError("ImportResult.status is invalid")
        if self.ue_destination.overwrite_policy not in ("overwrite", "skip", "rename"):
            raise ValueError(
                "UEDestination.overwrite_policy must be 'overwrite', 'skip', or 'rename'"
            )
        if not isinstance(self.ue_destination.content_root, str) or not self.ue_destination.content_root.startswith("/Game"):
            raise ValueError("UEDestination.content_root must start with '/Game'")
        if self.ue_destination.skeleton_path and (
            not isinstance(self.ue_destination.skeleton_path, str)
            or not self.ue_destination.skeleton_path.startswith("/Game")
        ):
            raise ValueError("UEDestination.skeleton_path must start with '/Game'")
        delivery = self.ue_destination.skeleton_delivery
        if delivery.create_if_missing and not delivery.include_rig:
            raise ValueError(
                "SkeletonDelivery.create_if_missing requires include_rig: "
                "UE cannot build a Skeleton from an animation-only FBX"
            )
        if not self.ue_destination.skeleton_path and not delivery.create_if_missing:
            raise ValueError(
                "UEDestination.skeleton_path is required unless "
                "skeleton_delivery.create_if_missing is enabled"
            )
        if not isinstance(self.clips, list):
            raise ValueError("Manifest.clips must be a list")

        names = set()
        for clip in self.clips:
            clip.validate()
            if clip.name in names:
                raise ValueError(f"Duplicate clip name: {clip.name}")
            names.add(clip.name)

        if not isinstance(self.fbx_path, str) or not self.fbx_path.strip():
            raise ValueError("fbx_path cannot be empty")

    # -- convenience --------------------------------------------------------

    def can_export(self) -> bool:
        """True if validation status allows export (no blocking errors)."""
        return self.validation.status != "failed"

    def clip_names(self) -> List[str]:
        return [c.name for c in self.clips]
