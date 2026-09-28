"""maya.checks.mesh_checks

Mesh-level validators (see design.md section 4.2). Only run when the
scene contains meshes:

    mesh.history      - construction history deleted  (warning, auto-fixable)
    mesh.transforms   - transforms frozen             (warning, auto-fixable)
    mesh.uv           - UVs present, no major overlap (warning)
    mesh.skin_weight  - skinCluster weights normalized (warning, auto-fixable)
"""

from __future__ import annotations

from mtu_maya.checks.registry import (
    BaseValidator,
    CheckContext,
    CheckResult,
    register_validator,
)


class _MeshOnlyValidator(BaseValidator):
    """Base for checks that pass automatically when no mesh is present."""

    def check(self, ctx: CheckContext) -> CheckResult:
        if not ctx.has_mesh:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="no mesh in scene, check skipped",
                auto_fixable=self.auto_fixable,
            )
        return self._check_meshes(ctx)

    def _check_meshes(self, ctx: CheckContext) -> CheckResult:
        raise NotImplementedError


@register_validator
class MeshHistoryValidator(_MeshOnlyValidator):
    id = "mesh.history"
    category = "mesh"
    level = "info"
    auto_fixable = False
    description = "Modelling history should be cleaned; deformer history is kept."

    def _check_meshes(self, ctx: CheckContext) -> CheckResult:
        # Skinned meshes carry deformer history by design — never flag them.
        bad = [
            m for m, clean in ctx.mesh_history.items()
            if not clean and not ctx.mesh_skinned.get(m, False)
        ]
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(bad)} 个未蒙皮网格还留着建模历史",
                auto_fixable=self.auto_fixable,
                details=bad[:20],
                select_on_locate=bad[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"{len(ctx.mesh_history)} 个网格历史正常（蒙皮变形器已保留）",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class MeshTransformsValidator(_MeshOnlyValidator):
    id = "mesh.transforms"
    category = "mesh"
    level = "info"
    auto_fixable = False
    description = "Unskinned mesh transforms should be frozen before export."

    def _check_meshes(self, ctx: CheckContext) -> CheckResult:
        # Freezing a skinned mesh breaks the bind pose — never flag or fix it.
        bad = [
            m for m, ok in ctx.mesh_frozen.items()
            if not ok and not ctx.mesh_skinned.get(m, False)
        ]
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(bad)} 个未蒙皮网格的变换没冻结",
                auto_fixable=self.auto_fixable,
                details=bad[:20],
                select_on_locate=bad[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"{len(ctx.mesh_frozen)} 个网格变换正常（蒙皮网格已跳过）",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class MeshUVValidator(_MeshOnlyValidator):
    id = "mesh.uv"
    category = "mesh"
    level = "info"
    auto_fixable = False
    description = "Meshes should have UVs (only matters when exporting mesh)."

    def _check_meshes(self, ctx: CheckContext) -> CheckResult:
        bad = [m for m, ok in ctx.mesh_has_uvs.items() if not ok]
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(bad)} mesh(es) have no UVs",
                auto_fixable=self.auto_fixable,
                details=bad[:20],
                select_on_locate=bad[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"all {len(ctx.mesh_has_uvs)} meshes have UVs",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class MeshSkinWeightValidator(_MeshOnlyValidator):
    id = "mesh.skin_weight"
    category = "mesh"
    level = "warning"
    auto_fixable = False
    description = "Skin weights should be normalized before export."

    def _check_meshes(self, ctx: CheckContext) -> CheckResult:
        bad = [m for m, ok in ctx.mesh_skin_normalized.items() if not ok]
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(bad)} mesh(es) have non-normalized skin weights",
                auto_fixable=self.auto_fixable,
                details=bad[:20],
                select_on_locate=bad[:50],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"all {len(ctx.mesh_skin_normalized)} meshes have normalized weights",
            auto_fixable=self.auto_fixable,
        )
