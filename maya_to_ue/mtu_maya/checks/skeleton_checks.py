"""maya.checks.skeleton_checks

Skeleton-level validators (see design.md section 4.2):

    skeleton.root_exists     - a root joint must exist          (error)
    skeleton.naming          - joint names match the preset regex (warning)
    skeleton.scale           - all joints scale == 1            (warning, auto-fixable)
    skeleton.single_root     - exactly one skeleton root        (error)
    skeleton.duplicate_names - joint short names are unique     (error)
    skeleton.segment_scale   - segmentScaleCompensate is off    (warning, auto-fixable)
"""

from __future__ import annotations

from mtu_maya.checks.registry import (
    BaseValidator,
    CheckContext,
    CheckResult,
    register_validator,
)


@register_validator
class SkeletonRootExistsValidator(BaseValidator):
    id = "skeleton.root_exists"
    category = "skeleton"
    level = "error"
    auto_fixable = False
    description = "A skeleton root joint must exist."

    def check(self, ctx: CheckContext) -> CheckResult:
        # Prefer the user-selected root; fall back to the auto-detected one.
        root = ctx.skeleton_root_selected or ctx.root_joint
        if not root:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message="场景里没找到根骨骼，也没在③里指定骨架根节点",
                auto_fixable=self.auto_fixable,
            )
        selected_root = ctx.skeleton_root_selected
        resolved = root if root in ctx.joints else None
        if resolved is None and selected_root:
            try:
                from mtu_maya.core import maya_utils
                resolved = maya_utils.resolve_joint(root)
            except Exception:
                resolved = None
        if resolved is None or resolved not in ctx.joints:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"选中的根 {root!r} 在场景里找不到对应的关节（joint）",
                auto_fixable=self.auto_fixable,
                select_on_locate=[root],
            )
        # NOTE: we intentionally do NOT require the root to sit exactly at the
        # origin. Real rigs often have a tiny root offset; that was producing
        # false positives the user couldn't reasonably "fix". Existence + being
        # a joint is the meaningful contract for export.
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"根骨骼 = {resolved}",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SkeletonNamingValidator(BaseValidator):
    id = "skeleton.naming"
    category = "skeleton"
    level = "warning"
    auto_fixable = False
    description = "Joint names should match the active preset's naming regex."

    def check(self, ctx: CheckContext) -> CheckResult:
        if ctx.preset is None:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="no preset selected, naming check skipped",
                auto_fixable=self.auto_fixable,
            )
        rx = ctx.preset.naming.compiled_regex()
        if rx is None:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="preset has no naming regex, check skipped",
                auto_fixable=self.auto_fixable,
            )
        bad = []
        bad_paths = []
        for path in ctx.joints:
            # Keep the namespace: some conventions (Mixamo's "mixamorig:") make
            # it part of the expected name, so stripping it first would make
            # those presets impossible to satisfy. Presets that don't care can
            # simply allow an optional prefix in their regex.
            full_name = path.rsplit("|", 1)[-1]
            short_name = full_name.rsplit(":", 1)[-1]
            if not (rx.fullmatch(full_name) or rx.fullmatch(short_name)):
                bad.append(full_name)
                bad_paths.append(path)
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=(
                    f"{len(bad)} 根骨骼名字不符合预设 {ctx.preset.id} 的规则 —— "
                    "若骨架本身没问题，先确认右上角预设选对了"
                ),
                auto_fixable=self.auto_fixable,
                details=bad[:20],
                select_on_locate=bad_paths[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"全部 {len(ctx.joints)} 根骨骼都符合预设 {ctx.preset.id} 的命名规则",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SkeletonScaleValidator(BaseValidator):
    id = "skeleton.scale"
    category = "skeleton"
    level = "warning"
    auto_fixable = False
    description = "Joint scale should be reviewed before export."

    TOLERANCE = 1e-3

    def check(self, ctx: CheckContext) -> CheckResult:
        bad = []
        bad_paths = []
        for path, (sx, sy, sz) in ctx.joint_scales.items():
            if any(abs(v - 1.0) > self.TOLERANCE for v in (sx, sy, sz)):
                name = path.rsplit("|", 1)[-1]
                bad.append(f"{name} ({sx:.3f}, {sy:.3f}, {sz:.3f})")
                bad_paths.append(path)
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(bad)} joint(s) with non-unit scale",
                auto_fixable=self.auto_fixable,
                details=bad[:20],
                select_on_locate=bad_paths[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"all {len(ctx.joint_scales)} joints have unit scale",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SkeletonSingleRootValidator(BaseValidator):
    id = "skeleton.single_root"
    category = "skeleton"
    level = "error"
    auto_fixable = False
    description = "The export hierarchy must contain exactly one skeleton root."

    def check(self, ctx: CheckContext) -> CheckResult:
        roots = ctx.skeleton_roots
        if not ctx.joints:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="场景里没有关节，跳过",
                auto_fixable=self.auto_fixable,
            )
        if len(roots) > 1:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"导出根层级有 {len(roots)} 个骨架根 —— UE 只接受一套",
                auto_fixable=self.auto_fixable,
                details=[r.rsplit("|", 1)[-1] for r in roots[:20]],
                select_on_locate=roots[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message="导出根骨架只有一个根节点",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SkeletonDuplicateNamesValidator(BaseValidator):
    id = "skeleton.duplicate_names"
    category = "skeleton"
    level = "error"
    auto_fixable = False
    description = "Joint short names must be unique; UE flattens the hierarchy by name."

    def check(self, ctx: CheckContext) -> CheckResult:
        dupes = ctx.duplicate_joint_names
        if dupes:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(dupes)} 个骨骼短名重复 —— UE 按名字建骨架，会丢骨骼",
                auto_fixable=self.auto_fixable,
                details=dupes[:20],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"{len(ctx.joints)} 根骨骼名字唯一",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SkeletonRealWorldScaleValidator(BaseValidator):
    id = "skeleton.real_world_scale"
    category = "skeleton"
    level = "warning"
    auto_fixable = False
    description = "Skeleton height should be plausible for a UE character (cm scale)."

    # A human character is ~180 cm. Anything far outside this band means the
    # asset was authored in metres (or inches) and will look wrong in UE.
    MIN_PLAUSIBLE = 20.0
    MAX_PLAUSIBLE = 2000.0

    def check(self, ctx: CheckContext) -> CheckResult:
        height = ctx.skeleton_height
        if not ctx.joints or height <= 0:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="没有骨架或量不到高度，跳过",
                auto_fixable=self.auto_fixable,
            )
        if height < self.MIN_PLAUSIBLE:
            factor = round(180.0 / height) if height else 0
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=(
                    f"骨架高度只有 {height:.2f} {ctx.scene_units} —— "
                    f"UE 里会小到看不见（人形角色应约 180 cm）"
                ),
                auto_fixable=self.auto_fixable,
                details=[
                    f"当前高度：{height:.2f} {ctx.scene_units}",
                    f"UE 导入时建议缩放：约 {factor} 倍",
                    "常见原因：模型以【米】为单位制作，放进厘米场景",
                ],
            )
        if height > self.MAX_PLAUSIBLE:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=(
                    f"骨架高度达 {height:.2f} {ctx.scene_units} —— "
                    "比正常角色大一个量级，UE 里会撑满整个场景"
                ),
                auto_fixable=self.auto_fixable,
                details=[f"当前高度：{height:.2f} {ctx.scene_units}"],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"骨架高度 {height:.1f} {ctx.scene_units}，尺寸合理",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SkeletonBindPoseValidator(BaseValidator):
    id = "skeleton.bind_pose"
    category = "skeleton"
    level = "warning"
    auto_fixable = False
    description = "When shipping a rig, flag a non-neutral export-start pose for review."

    # Arms more than this far off horizontal are clearly not a T-pose.
    MAX_ARM_DEVIATION = 25.0

    def check(self, ctx: CheckContext) -> CheckResult:
        if not ctx.include_rig:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="没有勾选【同时导出模型】，不会创建骨架，跳过",
                auto_fixable=self.auto_fixable,
            )
        deviation = ctx.tpose_arm_deviation
        if deviation < 0:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="当前预设没有手臂骨骼映射，量不出姿势，跳过",
                auto_fixable=self.auto_fixable,
            )
        if deviation > self.MAX_ARM_DEVIATION:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=(
                    f"导出起始帧不是 T-pose（手臂偏离水平 {deviation:.0f}°）—— "
                    "请确认 FBX 含正确 Bind Pose 且 UE 未启用 Use T0 As Ref Pose"
                ),
                auto_fixable=self.auto_fixable,
                details=[
                    f"手臂偏离水平：{deviation:.1f}°",
                    "若 FBX 含正确 Bind Pose，且 Use T0 As Ref Pose 关闭，动画首帧通常不会污染参考姿势",
                    "要做重定向、物理资产或加法动画时，建议单独核验生成的 Skeleton Reference Pose",
                ],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"起始帧接近 T-pose（手臂偏离 {deviation:.0f}°），建议仍在 UE 核验参考姿势",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class SkeletonSegmentScaleValidator(BaseValidator):
    id = "skeleton.segment_scale"
    category = "skeleton"
    level = "warning"
    auto_fixable = False
    description = "segmentScaleCompensate is a Maya-only feature UE does not support."

    def check(self, ctx: CheckContext) -> CheckResult:
        bad = ctx.segment_scale_compensate
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(bad)} 根骨骼开着 segmentScaleCompensate —— UE 不支持，带缩放动画会错位",
                auto_fixable=self.auto_fixable,
                details=[b.rsplit("|", 1)[-1] for b in bad[:20]],
                select_on_locate=bad[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message="没有骨骼使用 segmentScaleCompensate",
            auto_fixable=self.auto_fixable,
        )
