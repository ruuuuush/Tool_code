"""maya.checks.anim_checks

Animation-level validators (see design.md section 4.2):

    anim.curves_on_expected  - only expected nodes carry curves  (info)
    anim.stray_layers        - no stray animation layers        (info)
    anim.clip_ranges_valid   - clip ranges in UI table are legal (error)
    anim.root_motion_match   - root motion flag matches clip type (info)
"""

from __future__ import annotations

from mtu_maya.checks.registry import (
    BaseValidator,
    CheckContext,
    CheckResult,
    register_validator,
)


@register_validator
class AnimCurvesOnExpectedValidator(BaseValidator):
    id = "anim.curves_on_expected"
    category = "anim"
    level = "info"
    auto_fixable = False
    description = "Only expected nodes (joints, controls) should carry animation curves."

    def check(self, ctx: CheckContext) -> CheckResult:
        joint_set = set(ctx.joints)
        joint_short_names = {path.rsplit("|", 1)[-1].rsplit(":", 1)[-1] for path in ctx.joints}
        animated_nodes = set()
        for curve in ctx.animated_nodes:
            targets = ctx.animation_curve_targets.get(curve)
            if targets is None:
                continue
            animated_nodes.update(targets)
        unexpected = sorted(
            node for node in animated_nodes
            if node not in joint_set and node.rsplit("|", 1)[-1].rsplit(":", 1)[-1] not in joint_short_names
        )
        curve_count = len(ctx.animated_nodes)
        if not ctx.animation_curve_targets:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message=f"{curve_count} animation curve(s); target inspection unavailable",
                auto_fixable=self.auto_fixable,
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=not unexpected,
            message=(
                "all inspected animation curves drive joints"
                if not unexpected
                else f"{len(unexpected)} animated non-joint node(s)"
            ),
            auto_fixable=self.auto_fixable,
            details=unexpected[:20],
            select_on_locate=unexpected[:50],
        )


@register_validator
class AnimStrayLayersValidator(BaseValidator):
    id = "anim.stray_layers"
    category = "anim"
    level = "info"
    auto_fixable = False
    description = "No stray/unused animation layers."

    def check(self, ctx: CheckContext) -> CheckResult:
        if ctx.stray_anim_layers:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(ctx.stray_anim_layers)} stray animation layer(s)",
                auto_fixable=self.auto_fixable,
                details=ctx.stray_anim_layers[:20],
                select_on_locate=ctx.stray_anim_layers[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message="no stray animation layers",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class AnimClipRangesValidator(BaseValidator):
    id = "anim.clip_ranges_valid"
    category = "anim"
    level = "error"
    auto_fixable = False
    description = "Every clip in the UI table must have a valid range inside the timeline."

    def check(self, ctx: CheckContext) -> CheckResult:
        if not ctx.clips:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message="no clips defined",
                auto_fixable=self.auto_fixable,
            )
        problems = []
        for clip in ctx.clips:
            if not clip.name:
                problems.append("<unnamed clip>: name is empty")
                continue
            if clip.start < 0:
                problems.append(f"{clip.name}: start {clip.start} < 0")
            if clip.end < clip.start:
                problems.append(f"{clip.name}: end {clip.end} < start {clip.start}")
            if clip.start < ctx.timeline_start:
                problems.append(f"{clip.name}: start {clip.start} < timeline start {ctx.timeline_start}")
            if clip.end > ctx.timeline_end:
                problems.append(f"{clip.name}: end {clip.end} > timeline end {ctx.timeline_end}")
        if problems:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(problems)} clip range problem(s)",
                auto_fixable=self.auto_fixable,
                details=problems[:20],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"{len(ctx.clips)} clip(s) with valid ranges",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class AnimClipOverlapValidator(BaseValidator):
    id = "anim.clip_overlap"
    category = "anim"
    level = "warning"
    auto_fixable = False
    description = "Clip ranges should not overlap; overlapping clips duplicate frames in UE."

    def check(self, ctx: CheckContext) -> CheckResult:
        ordered = sorted(
            [c for c in ctx.clips if c.name],
            key=lambda c: (c.start, c.end),
        )
        overlaps = []
        for prev, cur in zip(ordered, ordered[1:]):
            if cur.start <= prev.end:
                overlaps.append(
                    f"{prev.name}({prev.start}-{prev.end}) 与 {cur.name}({cur.start}-{cur.end}) 重叠"
                )
        if overlaps:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(overlaps)} 处片段区间重叠",
                auto_fixable=self.auto_fixable,
                details=overlaps[:20],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"{len(ordered)} 个片段区间互不重叠",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class AnimKeysInClipRangeValidator(BaseValidator):
    id = "anim.keys_in_clip_range"
    category = "anim"
    level = "warning"
    auto_fixable = False
    description = "Animated joints should have keys inside the requested clip ranges."

    def check(self, ctx: CheckContext) -> CheckResult:
        if not ctx.clips:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="还没定义片段，跳过",
                auto_fixable=self.auto_fixable,
            )
        bad = ctx.keys_outside_clip_range
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(bad)} 根骨骼的关键帧全在片段范围之外 —— 导出会得到静止动画",
                auto_fixable=self.auto_fixable,
                details=[b.rsplit("|", 1)[-1] for b in bad[:20]],
                select_on_locate=bad[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message="关键帧都落在片段范围内",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class AnimSkeletonHasAnimationValidator(BaseValidator):
    id = "anim.skeleton_animated"
    category = "anim"
    level = "error"
    auto_fixable = False
    description = "At least part of the skeleton must carry animation."

    def check(self, ctx: CheckContext) -> CheckResult:
        if not ctx.joints:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="场景里没有关节，跳过",
                auto_fixable=self.auto_fixable,
            )
        animated_count = len(ctx.joints) - len(ctx.unanimated_joints)
        if animated_count <= 0:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message="骨架上一根有动画的骨骼都没有 —— 导出的 FBX 不会有动画",
                auto_fixable=self.auto_fixable,
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"{animated_count}/{len(ctx.joints)} 根骨骼带动画",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class AnimRootMotionMatchValidator(BaseValidator):
    id = "anim.root_motion_match"
    category = "anim"
    level = "info"
    auto_fixable = False
    description = "Root motion flag should match clip type (locomotion clips on, idle off)."

    # Heuristic: clip names containing these substrings should have root motion on.
    LOCOMOTION_HINTS = ("walk", "run", "jog", "sprint", "strafe", "crawl")

    def check(self, ctx: CheckContext) -> CheckResult:
        mismatches = []
        for clip in ctx.clips:
            name_lower = clip.name.lower()
            looks_loco = any(h in name_lower for h in self.LOCOMOTION_HINTS)
            if looks_loco and not clip.root_motion:
                mismatches.append(f"{clip.name}: looks like locomotion but root_motion is off")
            # We do NOT flag idle clips with root_motion on, since that's a
            # legitimate choice (some pipelines export in-place + root motion).
        if mismatches:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(mismatches)} clip(s) may have wrong root_motion setting",
                auto_fixable=self.auto_fixable,
                details=mismatches[:20],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message="root_motion flags look consistent",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class AnimDenseKeysValidator(BaseValidator):
    id = "anim.keys_dense"
    category = "anim"
    level = "warning"
    auto_fixable = False
    description = "Per-frame baked curves carry redundant keys; thinning shrinks the FBX."

    def check(self, ctx: CheckContext) -> CheckResult:
        # 启用抽稀 = 用户已经处理了，别再报。
        if not ctx.dense_curves or ctx.thinning_level != "off":
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="no per-frame baked curves"
                if not ctx.dense_curves else "key thinning enabled",
                auto_fixable=self.auto_fixable,
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=False,
            message=(
                f"{len(ctx.dense_curves)} curve(s) baked at ~1 key/frame "
                f"(densest: {ctx.dense_curves[0]}) — thinning is off"
            ),
            auto_fixable=self.auto_fixable,
            details=ctx.dense_curves[:20],
        )
