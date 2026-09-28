"""maya.checks.scene_checks

Scene-level validators (see design.md section 4.2):

    scene.unit            - working unit must be cm       (error, auto-fixable)
    scene.up_axis         - report scene up axis without modifying it (info)
    scene.fps             - frame rate must match target  (error, auto-fixable)
    scene.timeline_range  - timeline range sane & non-empty (warning)

All checks receive a CheckContext; fixes import maya.cmds lazily.
"""

from __future__ import annotations

from mtu_maya.checks.registry import (
    BaseValidator,
    CheckContext,
    CheckResult,
    register_validator,
)


@register_validator
class SceneUnitValidator(BaseValidator):
    id = "scene.unit"
    category = "scene"
    level = "error"
    auto_fixable = False
    description = "Working unit must be cm to match Unreal's default."

    def check(self, ctx: CheckContext) -> CheckResult:
        ok = ctx.scene_units == "cm"
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=ok,
            message=(
                f"unit = {ctx.scene_units}"
                if ok
                else f"unit is '{ctx.scene_units}', must be 'cm'"
            ),
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SceneUpAxisValidator(BaseValidator):
    id = "scene.up_axis"
    category = "scene"
    level = "info"
    auto_fixable = False
    description = "Scene up axis is reported for reference; FBX export preserves the scene axis."

    def check(self, ctx: CheckContext) -> CheckResult:
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"scene up axis = {ctx.scene_up_axis} (preserved during export)",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SceneFpsValidator(BaseValidator):
    id = "scene.fps"
    category = "scene"
    level = "error"
    auto_fixable = False
    description = "Frame rate must match the configured target."

    def check(self, ctx: CheckContext) -> CheckResult:
        target_fps = ctx.target_frame_rate
        ok = abs(ctx.scene_fps - target_fps) < 0.01
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=ok,
            message=(
                f"fps = {ctx.scene_fps:g}"
                if ok
                else f"fps is {ctx.scene_fps:g}, must be {target_fps:g}"
            ),
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SceneTimelineRangeValidator(BaseValidator):
    id = "scene.timeline_range"
    category = "scene"
    level = "warning"
    auto_fixable = False
    description = "Timeline range should be positive and non-empty."

    def check(self, ctx: CheckContext) -> CheckResult:
        start, end = ctx.timeline_start, ctx.timeline_end
        if end < start:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"timeline end ({end}) < start ({start})",
                auto_fixable=self.auto_fixable,
            )
        if end == start:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"timeline range is a single frame ({start})",
                auto_fixable=self.auto_fixable,
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"timeline {start}-{end}",
            auto_fixable=self.auto_fixable,
        )
