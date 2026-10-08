"""maya.checks.export_checks

Export-level validators (see design.md section 4.2):

    export.fbx_plugin         - FBX plugin loaded            (error)
    export.path_valid         - export path valid & writable (error)
    export.naming_legal       - clip names have no illegal chars (error)
    export.ue_path_valid      - UE destination paths are usable (error)
    export.skeleton_root_set  - a skeleton root has been selected (error)
"""

from __future__ import annotations

import os
import re

from mtu_maya.checks.registry import (
    BaseValidator,
    CheckContext,
    CheckResult,
    register_validator,
)

# Characters banned in clip names (Windows-safe plus UE-path-safe).
# Control characters, whitespace-only names, and dot-only names are rejected
# separately so every generated UE asset path stays usable.
_ILLEGAL_CLIP_RE = re.compile(r'[\\:*?"<>|/\x00-\x1f]')


@register_validator
class ExportFbxPluginValidator(BaseValidator):
    id = "export.fbx_plugin"
    category = "export"
    level = "error"
    auto_fixable = False
    description = "Maya's FBX plugin must be loaded."

    def check(self, ctx: CheckContext) -> CheckResult:
        if ctx.fbx_plugin_loaded:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=True,
                message="FBX plugin loaded",
                auto_fixable=self.auto_fixable,
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=False,
            message="FBX plugin not loaded (load fbxmaya via Plug-in Manager)",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class ExportPathValidator(BaseValidator):
    id = "export.path_valid"
    category = "export"
    level = "error"
    # Fixable: if the only problem is a missing directory, fix() creates it.
    auto_fixable = True
    description = "The FBX export path must be valid and its directory writable."

    def check(self, ctx: CheckContext) -> CheckResult:
        path = ctx.fbx_path
        if not path:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message="还没设置导出位置 —— 请在【导出设置】里填【保存目录】和【文件名】",
                # Nothing to create when there's no path at all.
                auto_fixable=False,
            )
        if not path.lower().endswith(".fbx"):
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message="导出文件必须以 .fbx 结尾",
                auto_fixable=False,
            )
        parent = os.path.dirname(os.path.abspath(path)) or "."
        if not os.path.isdir(parent):
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"保存目录不存在：{parent}（点【修复】可自动创建）",
                auto_fixable=True,
            )
        if not os.access(parent, os.W_OK):
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"保存目录不可写：{parent}（换一个有权限的目录）",
                # Permissions are a user/OS concern; not auto-fixable.
                auto_fixable=False,
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"导出到：{path}",
            auto_fixable=self.auto_fixable,
        )

    def fix(self, ctx: CheckContext) -> None:
        """Create the missing export directory. Path still missing -> no-op."""
        path = ctx.fbx_path
        if not path or not path.lower().endswith(".fbx"):
            return
        parent = os.path.dirname(os.path.abspath(path)) or "."
        if not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        if not os.path.isdir(parent) or not os.access(parent, os.W_OK):
            raise OSError(f"保存目录不可写：{parent}")


@register_validator
class ExportNamingLegalValidator(BaseValidator):
    id = "export.naming_legal"
    category = "export"
    level = "error"
    auto_fixable = False
    description = "Clip names must not contain illegal characters: \\ : * ? \" < > | /"

    def check(self, ctx: CheckContext) -> CheckResult:
        bad = []
        for clip in ctx.clips:
            name = clip.name
            if not isinstance(name, str) or not name.strip() or name.strip(".") == "" or _ILLEGAL_CLIP_RE.search(name):
                bad.append(str(name))
        if bad:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=f"{len(bad)} clip name(s) contain illegal characters",
                auto_fixable=self.auto_fixable,
                details=bad[:20],
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message="all clip names are legal",
            auto_fixable=self.auto_fixable,
        )


@register_validator
class ExportUEPathValidator(BaseValidator):
    id = "export.ue_path_valid"
    category = "export"
    level = "error"
    auto_fixable = False
    description = (
        "UE destination paths must be valid package paths, and an "
        "animation-only delivery must name an existing Skeleton."
    )

    def check(self, ctx: CheckContext) -> CheckResult:
        content_root = (ctx.ue_content_root or "").strip()
        skeleton_path = (ctx.ue_skeleton_path or "").strip()
        problems = []

        if not content_root:
            problems.append("UE 目标路径为空 —— 在【导出设置】里填，例如 /Game/Animations/Hero")
        elif not content_root.startswith("/Game"):
            problems.append(
                f"UE 目标路径必须以 /Game 开头，现在是：{content_root}"
            )

        if not skeleton_path:
            if not ctx.create_skeleton_if_missing:
                problems.append(
                    "UE Skeleton 路径为空 —— 要么填已有骨架路径，"
                    "要么勾上【同时导出模型】让 UE 首次交付时自己建骨架"
                )
        elif not skeleton_path.startswith("/Game"):
            problems.append(
                f"UE Skeleton 路径必须以 /Game 开头，现在是：{skeleton_path}"
            )

        if problems:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message=problems[0],
                auto_fixable=self.auto_fixable,
                details=problems,
            )

        if skeleton_path:
            message = f"UE 目标 = {content_root}，骨架 = {skeleton_path}"
        else:
            message = f"UE 目标 = {content_root}，首次交付时由 UE 创建骨架"
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=message,
            auto_fixable=self.auto_fixable,
        )


@register_validator
class ExportSkeletonRootSetValidator(BaseValidator):
    id = "export.skeleton_root_set"
    category = "export"
    level = "error"
    auto_fixable = False
    description = "A skeleton root must be selected for export."

    def check(self, ctx: CheckContext) -> CheckResult:
        root = ctx.skeleton_root_selected
        if not root:
            return CheckResult(
                check_id=self.id,
                category=self.category,
                level=self.level,
                passed=False,
                message="还没指定骨架根节点 —— 在【导出设置】的【骨架根节点】里选最顶层的关节",
                auto_fixable=self.auto_fixable,
            )
        return CheckResult(
            check_id=self.id,
            category=self.category,
            level=self.level,
            passed=True,
            message=f"骨架根 = {root}",
            auto_fixable=self.auto_fixable,
        )
