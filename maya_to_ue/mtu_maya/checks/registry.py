"""maya.checks.registry

The validator framework: a registry that lets new checks be added by
simply writing a class and decorating it. The UI discovers all checks
via the registry, so adding a check requires no UI changes.

Design (see design.md section 4.2):
    - Each check is a class implementing the Validator protocol.
    - Checks are categorised (scene/skeleton/mesh/anim/export).
    - Each check has a severity level (error/warning/info).
    - Error-level failures block export; warning/info do not.
    - Checks may optionally provide an auto-fix.

Testability:
    Check.run() takes a CheckContext, not a maya.cmds reference. The
    context carries all the data the check needs (scene state + user
    export settings + the active skeleton preset). Tests can build a
    context in plain Python without Maya and verify check logic.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Type

from bridge.schema import Clip, Severity
from mtu_maya.core.preset_loader import SkeletonPreset


# ---------------------------------------------------------------------------
# Context passed to every check
# ---------------------------------------------------------------------------

@dataclass
class CheckContext:
    """Everything a validator needs to inspect the scene.

    Built once per "Run Checks" click and passed to every registered
    validator. Carrying data (instead of letting each check call cmds
    itself) keeps checks pure and testable.
    """

    # Scene state (populated from mtu_maya.core.maya_utils by the runner)
    scene_name: str = "untitled"
    scene_units: str = "cm"
    scene_up_axis: str = "z"
    scene_fps: float = 30.0
    target_frame_rate: float = 30.0
    timeline_start: int = 1
    timeline_end: int = 1

    # Skeleton state
    joints: List[str] = field(default_factory=list)           # full DAG paths
    root_joint: Optional[str] = None
    joint_scales: Dict[str, tuple] = field(default_factory=dict)   # path -> (sx,sy,sz)
    preset: Optional[SkeletonPreset] = None

    # Mesh state (only populated when meshes are present)
    has_mesh: bool = False
    mesh_nodes: List[str] = field(default_factory=list)
    mesh_history: Dict[str, bool] = field(default_factory=dict)    # mesh -> history is clean
    mesh_frozen: Dict[str, bool] = field(default_factory=dict)     # mesh -> transforms frozen
    mesh_has_uvs: Dict[str, bool] = field(default_factory=dict)
    mesh_skin_normalized: Dict[str, bool] = field(default_factory=dict)
    mesh_skinned: Dict[str, bool] = field(default_factory=dict)    # mesh -> bound to a skinCluster

    # Animation state
    animated_nodes: List[str] = field(default_factory=list)       # animCurve nodes
    animation_curve_targets: Dict[str, List[str]] = field(default_factory=dict)
    stray_anim_layers: List[str] = field(default_factory=list)
    # Curves baked at ~1 key/frame, densest first — candidates for thinning.
    dense_curves: List[str] = field(default_factory=list)
    # 本次导出的抽稀档位（off/low/medium/high）；检查据此决定是否点名稠密曲线。
    thinning_level: str = "off"
    # Joints that have no animation curve driving them at all.
    unanimated_joints: List[str] = field(default_factory=list)
    # Joints whose keys fall outside the requested clip ranges.
    keys_outside_clip_range: List[str] = field(default_factory=list)
    # Joints driven by constraints (baked at export, but worth surfacing).
    constrained_joints: List[str] = field(default_factory=list)
    # Skeleton roots found in the scene; more than one is a real UE problem.
    skeleton_roots: List[str] = field(default_factory=list)
    # Nodes in the export hierarchy whose names collide after namespace strip.
    duplicate_joint_names: List[str] = field(default_factory=list)
    # Joints carrying a non-zero segment scale compensate flag.
    segment_scale_compensate: List[str] = field(default_factory=list)
    # World-space height of the skeleton along the scene's up axis, in scene units.
    skeleton_height: float = 0.0
    # True when the rig will be shipped so UE can build a Skeleton from it.
    include_rig: bool = False
    # Rough T-pose signature measured at the export start frame: how far the
    # arms deviate from horizontal, in degrees. -1.0 means "could not measure".
    tpose_arm_deviation: float = -1.0

    # Export settings (user input from the UI)
    clips: List[Clip] = field(default_factory=list)
    fbx_path: str = ""
    skeleton_root_selected: Optional[str] = None

    # UE destination settings (user input from the UI). These end up in the
    # manifest, which refuses to serialise invalid values — so they have to be
    # checked here, before the FBX is written.
    ue_content_root: str = ""
    ue_skeleton_path: str = ""
    create_skeleton_if_missing: bool = False

    # FBX plugin
    fbx_plugin_loaded: bool = True


# ---------------------------------------------------------------------------
# Result of a single check
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Outcome of running one validator.

    `details` carries per-node or per-clip specifics so the UI can show
    them (e.g. the list of joints whose scale != 1).
    """

    check_id: str
    category: str
    level: Severity
    passed: bool
    message: str = ""
    auto_fixable: bool = False
    # 用户明确关掉了这一项：它没有跑过。既不是通过也不是失败——
    # 伪装成通过会让 manifest 写着"全部通过"，那是说谎。
    skipped: bool = False
    details: List[str] = field(default_factory=list)
    # Node names to select when the user double-clicks the result.
    select_on_locate: List[str] = field(default_factory=list)
    # Chinese display metadata (optional; filled from check_info registry by the UI).
    title: str = ""          # short Chinese name, e.g. "场景帧率"
    why: str = ""            # why this check exists
    how_to_fix: str = ""     # how to make it pass / where to fix it

    def to_entry(self):
        """Convert to a bridge.schema.CheckResultEntry for the manifest."""
        from bridge.schema import CheckResultEntry
        return CheckResultEntry(
            check=self.check_id,
            level=self.level,
            passed=self.passed,
            message=self.message,
            auto_fixable=self.auto_fixable,
            skipped=self.skipped,
        )


# ---------------------------------------------------------------------------
# Validator protocol
# ---------------------------------------------------------------------------

class Validator:
    """A single validator interface."""

    id: str
    category: str
    level: Severity
    auto_fixable: bool
    description: str

    def check(self, ctx: CheckContext) -> CheckResult:
        raise NotImplementedError

    def fix(self, ctx: CheckContext) -> None:
        raise NotImplementedError


class BaseValidator:
    """Base class for validators. Subclasses set the class attributes and
    implement check(). fix() is optional and only meaningful when
    auto_fixable is True.

    Subclasses do NOT need to import maya.cmds at module level — they
    receive all scene data via CheckContext. If a fix needs to mutate
    the scene, it can import maya.cmds lazily inside fix().
    """

    id: str = ""
    category: str = ""
    level: Severity = "warning"
    auto_fixable: bool = False
    description: str = ""
    # Optional Chinese display metadata. If left empty, the UI falls back to
    # the central mtu_maya.checks.check_info registry (keyed by id).
    title: str = ""
    why: str = ""
    how_to_fix: str = ""

    # Default fix is a no-op; subclasses override.
    def fix(self, ctx: CheckContext) -> None:  # noqa: ARG002
        raise NotImplementedError(
            f"{type(self).__name__} is not auto-fixable (auto_fixable=False)"
        )

    def check(self, ctx: CheckContext) -> CheckResult:  # noqa: ARG002
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ValidatorRegistry:
    """In-memory collection of all validators, keyed by id."""

    def __init__(self) -> None:
        self._validators: Dict[str, BaseValidator] = {}

    def register(self, validator: BaseValidator) -> BaseValidator:
        if not validator.id:
            raise ValueError(
                f"Validator {type(validator).__name__} has empty id"
            )
        # Re-registering the same id REPLACES the old instance instead of
        # raising. This is required for importlib.reload() to work: reloading a
        # check module re-runs @register_validator, and that must not blow up
        # just because the id already exists (e.g. inside Maya's long-lived
        # Python session). Raising here previously left modules half-initialised
        # and produced an empty check list in the UI.
        self._validators[validator.id] = validator
        return validator

    def get(self, check_id: str) -> Optional[BaseValidator]:
        return self._validators.get(check_id)

    def require(self, check_id: str) -> BaseValidator:
        v = self._validators.get(check_id)
        if v is None:
            raise KeyError(f"Unknown validator: {check_id!r}")
        return v

    # Display order for categories (matches design.md section 4.2).
    # Categories not in this list sort after, alphabetically.
    _CATEGORY_ORDER = ("scene", "skeleton", "mesh", "anim", "export")

    def _category_sort_key(self, category: str) -> tuple:
        try:
            return (0, self._CATEGORY_ORDER.index(category))
        except ValueError:
            return (1, category)

    def all(self) -> List[BaseValidator]:
        """All validators, ordered by (category order, id) for stable UI order."""
        return sorted(
            self._validators.values(),
            key=lambda v: (self._category_sort_key(v.category), v.id),
        )

    def by_category(self) -> Dict[str, List[BaseValidator]]:
        """Group validators by category, in design.md category order."""
        groups: Dict[str, List[BaseValidator]] = {}
        for v in self.all():
            groups.setdefault(v.category, []).append(v)
        return groups

    def categories(self) -> List[str]:
        """Category names in design.md order (scene, skeleton, mesh, anim, export)."""
        seen: List[str] = []
        for v in self.all():
            if v.category not in seen:
                seen.append(v.category)
        return seen

    def __len__(self) -> int:
        return len(self._validators)

    def __contains__(self, check_id: object) -> bool:
        return check_id in self._validators


# Module-level singleton registry. Importing a checks submodule triggers
# its @register_validator decorators, which populate this registry.
_default_registry = ValidatorRegistry()

_CHECK_MODULES = (
    "mtu_maya.checks.scene_checks",
    "mtu_maya.checks.skeleton_checks",
    "mtu_maya.checks.mesh_checks",
    "mtu_maya.checks.anim_checks",
    "mtu_maya.checks.export_checks",
)


def _import_check_modules(force_reload: bool = False) -> None:
    """Import the check submodules so their @register_validator runs.

    Normally a plain import suffices. But after someone reloads *this* module
    (e.g. importlib.reload inside Maya to pick up code edits), the registry is
    reset to empty while the check submodules stay cached in sys.modules — so a
    plain import would NOT re-execute them and the registry would stay empty.
    force_reload=True re-executes them so their decorators re-register.
    """
    import importlib
    for name in _CHECK_MODULES:
        mod = sys.modules.get(name)
        if mod is not None and force_reload:
            importlib.reload(mod)
        else:
            importlib.import_module(name)


def default_registry() -> ValidatorRegistry:
    """Return the shared default registry, importing all check modules once."""
    if len(_default_registry) == 0:
        # Empty => either first use, or this module was reloaded (which reset
        # the registry). Force-reimport so validators are (re)registered either way.
        _import_check_modules(force_reload=True)
    return _default_registry


def register_validator(cls: Type[BaseValidator]) -> Type[BaseValidator]:
    """Class decorator: instantiate *cls* and register it on the default registry.

    Usage:
        @register_validator
        class SceneUnitValidator(BaseValidator):
            id = "scene.unit"
            ...
    """
    instance = cls()
    _default_registry.register(instance)
    return cls


# ---------------------------------------------------------------------------
# Runner: executes all (or a subset of) validators
# ---------------------------------------------------------------------------

@dataclass
class RunReport:
    """Aggregated result of running the whole registry."""

    results: List[CheckResult] = field(default_factory=list)

    @property
    def errors(self) -> List[CheckResult]:
        return [r for r in self.results if r.level == "error" and not r.passed and not r.skipped]

    @property
    def warnings(self) -> List[CheckResult]:
        return [r for r in self.results if r.level == "warning" and not r.passed and not r.skipped]

    @property
    def infos(self) -> List[CheckResult]:
        return [r for r in self.results if r.level == "info" and not r.passed and not r.skipped]

    @property
    def skipped(self) -> List[CheckResult]:
        return [r for r in self.results if r.skipped]

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed and not r.skipped)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def status(self) -> str:
        if self.errors:
            return "failed"
        if self.warnings:
            return "passed_with_warnings"
        return "passed"

    def can_export(self) -> bool:
        return not self.errors

    def to_summary(self):
        """Convert to a bridge.ValidationSummary for the manifest."""
        from bridge.schema import SkippedCheck, ValidationSummary
        return ValidationSummary(
            status=self.status,  # type: ignore[arg-type]
            errors=len(self.errors),
            warnings=len(self.warnings),
            infos=len(self.infos),
            results=[r.to_entry() for r in self.results],
            skipped=[SkippedCheck(check=r.check_id, level=r.level) for r in self.skipped],
        )


def run_all_checks(
    ctx: CheckContext,
    registry: Optional[ValidatorRegistry] = None,
    skipped: Optional[Set[str]] = None,
) -> RunReport:
    """Run every registered validator against *ctx* and return a RunReport.

    A validator failure is converted to a failed result at that validator's
    declared severity, so one buggy check never aborts the whole run.

    Ids in *skipped* are not executed at all. They still appear in the report
    as skipped entries — a check that silently vanishes leaves no trace in the
    manifest, and the whole point of skipping is that it stays visible.
    """
    reg = registry or default_registry()
    skipped = skipped or set()
    report = RunReport()
    for v in reg.all():
        if v.id in skipped:
            report.results.append(
                CheckResult(
                    check_id=v.id,
                    category=v.category,
                    level=v.level,
                    passed=False,
                    skipped=True,
                    message="",
                    auto_fixable=False,
                )
            )
            continue
        try:
            result = v.check(ctx)
        except Exception as exc:  # defensive: don't let one check kill the run
            result = CheckResult(
                check_id=v.id,
                category=v.category,
                level=v.level,
                passed=False,
                message=f"{type(exc).__name__}: {exc}",
                auto_fixable=False,
            )
        # Sanity: ensure the result carries the validator's id/level.
        if result.check_id != v.id:
            result.check_id = v.id
        if result.category != v.category:
            result.category = v.category
        if result.level != v.level:
            result.level = v.level
        report.results.append(result)
    return report


def fix_check(check_id: str, ctx: CheckContext, registry: Optional[ValidatorRegistry] = None) -> None:
    """Run the auto-fix for a single check. No-op if not auto-fixable."""
    reg = registry or default_registry()
    v = reg.require(check_id)
    if not v.auto_fixable:
        return
    v.fix(ctx)


def fix_all_warnings(
    ctx: CheckContext,
    registry: Optional[ValidatorRegistry] = None,
    skipped: Optional[Set[str]] = None,
) -> List[str]:
    """Run auto-fix for every warning-level check that is auto_fixable.

    Ids in *skipped* are left alone: fixing a check the user explicitly
    switched off is overstepping.

    Returns the list of check ids that were actually fixed.
    """
    reg = registry or default_registry()
    skipped = skipped or set()
    fixed: List[str] = []
    for v in reg.all():
        if v.id in skipped:
            continue
        if v.level == "warning" and v.auto_fixable:
            try:
                v.fix(ctx)
                fixed.append(v.id)
            except Exception:
                # A failing fix should not block the others.
                continue
    return fixed


__all__ = [
    "CheckContext",
    "CheckResult",
    "Validator",
    "BaseValidator",
    "ValidatorRegistry",
    "RunReport",
    "default_registry",
    "register_validator",
    "run_all_checks",
    "fix_check",
    "fix_all_warnings",
]
