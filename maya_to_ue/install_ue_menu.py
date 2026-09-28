"""Maya→UE 交付工具 · 在 UE 编辑器里装一个菜单按钮

怎么用（只装一次）：
    1. UE 菜单 Window → Output Log，底部下拉从 Cmd 切到 Python。
    2. 粘贴这一行并回车（路径改成你的实际仓库目录）：

           exec(open(r"D:/tool_code/maya_to_ue/install_ue_menu.py").read())

装好后：主菜单栏出现「Maya→UE」，里面有三个按钮：
    · 导入动画…      选 manifest 文件并导入
    · 环境自检        确认当前引擎版本的 API 是否齐全
    · 重新载入工具    改完代码后刷新，不用重启 UE

想让它开机自动加载：把本文件所在目录加进
    Project Settings → Plugins → Python → Startup Scripts
"""

from __future__ import annotations

import os
import sys

import unreal

# ===========================================================================
# ★ 仅当本文件被 exec() 执行、无法通过 __file__ 定位时，才需要改这里。
REPO_PATH_FALLBACK = r"D:/tool_code/maya_to_ue"
# ===========================================================================


def _resolve_repo_root() -> str:
    """仓库根目录 = 本文件所在目录。

    正常 import 时用 __file__；被 exec(open(...).read()) 执行时没有
    __file__，退回到上面的常量。
    """
    here = globals().get("__file__")
    if here:
        return os.path.dirname(os.path.abspath(here))
    return os.path.abspath(REPO_PATH_FALLBACK)


REPO_ROOT = _resolve_repo_root()

MENU_NAME = "MayaToUE"
MENU_LABEL = "Maya→UE"


def _ensure_repo_on_path() -> None:
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)


def _reload_launcher():
    """Drop cached modules so code edits take effect without restarting UE."""
    _ensure_repo_on_path()
    for name in list(sys.modules):
        if name.startswith(("mtu_unreal", "launch_ue_importer", "bridge")):
            del sys.modules[name]
    import launch_ue_importer
    return launch_ue_importer


def _last_manifest_dir() -> str:
    """Remember where the user picked a manifest last time."""
    saved = unreal.Paths.project_saved_dir()
    marker = os.path.join(saved, "maya_to_ue_last_dir.txt")
    if os.path.isfile(marker):
        try:
            with open(marker, "r", encoding="utf-8") as fp:
                path = fp.read().strip()
            if os.path.isdir(path):
                return path
        except Exception:
            pass
    return unreal.Paths.project_dir()


def _remember_manifest_dir(path: str) -> None:
    saved = unreal.Paths.project_saved_dir()
    marker = os.path.join(saved, "maya_to_ue_last_dir.txt")
    try:
        os.makedirs(saved, exist_ok=True)
        with open(marker, "w", encoding="utf-8") as fp:
            fp.write(os.path.dirname(path))
    except Exception:
        pass


def import_animation() -> None:
    """Menu action: pick a manifest and run the import."""
    picked = []
    ok = unreal.EditorDialog.open_file_dialog(
        "选择 Maya 导出的 manifest",
        _last_manifest_dir(),
        "",
        "Manifest JSON (*.json)|*.json",
        unreal.FileDialogFlags.NONE,
        picked,
    )
    if not ok or not picked:
        return

    manifest_path = str(picked[0])
    _remember_manifest_dir(manifest_path)

    launcher = _reload_launcher()
    with unreal.ScopedSlowTask(1, "正在导入 Maya 动画…") as task:
        task.make_dialog(True)
        outcome = launcher.run(manifest_path)
        task.enter_progress_frame(1)

    launcher.report(outcome)

    ok_count = len(outcome.succeeded)
    fail_count = len(outcome.failed)
    skip_count = len(outcome.skipped)

    if outcome.errors:
        body = "\n".join(f"• {e}" for e in outcome.errors[:10])
        unreal.EditorDialog.show_message(
            "导入失败",
            f"没有导入任何动画。\n\n{body}\n\n完整信息见 Output Log。",
            unreal.AppMsgType.OK,
        )
        return

    lines = [f"成功 {ok_count} 段"]
    if skip_count:
        lines.append(f"跳过 {skip_count} 段（重名策略）")
    if fail_count:
        lines.append(f"失败 {fail_count} 段：{', '.join(outcome.failed)}")
    if getattr(outcome, "skeleton_created", False):
        lines.append("")
        lines.append("已新建骨架：")
        lines.append(f"  {outcome.skeleton_asset_path}")
        if getattr(outcome, "skeletal_mesh_path", ""):
            lines.append(f"  {outcome.skeletal_mesh_path}")
    else:
        lines.append(f"\n使用骨架：{outcome.skeleton_asset_path}")

    unreal.EditorDialog.show_message(
        "导入完成" if not fail_count else "部分导入失败",
        "\n".join(lines),
        unreal.AppMsgType.OK,
    )


def check_environment() -> None:
    """Menu action: verify this engine build can run the importer."""
    launcher = _reload_launcher()
    problems = launcher.check()
    if not problems:
        unreal.EditorDialog.show_message(
            "环境自检",
            "通过。当前引擎版本支持本工具需要的全部 API。",
            unreal.AppMsgType.OK,
        )
        return
    body = "\n".join(f"• {p}" for p in problems)
    unreal.EditorDialog.show_message(
        "环境自检未通过", f"{body}\n\n详情见 Output Log。", unreal.AppMsgType.OK
    )


def reload_tool() -> None:
    """Menu action: re-read the Python sources after editing them."""
    _reload_launcher()
    unreal.log("[maya_to_ue] 工具代码已重新载入。")
    unreal.EditorDialog.show_message(
        "重新载入", "工具代码已重新载入。", unreal.AppMsgType.OK
    )


# ---------------------------------------------------------------------------
# Menu registration
# ---------------------------------------------------------------------------

_ENTRY_SPECS = [
    ("ImportAnimation", "导入动画…", "选择 manifest 并按片段导入 AnimSequence", "import_animation"),
    ("CheckEnvironment", "环境自检", "确认当前引擎版本的 API 是否齐全", "check_environment"),
    ("ReloadTool", "重新载入工具", "改完 Python 代码后刷新，不用重启 UE", "reload_tool"),
]


def install() -> None:
    """Create (or refresh) the Maya→UE menu in the main menu bar."""
    _ensure_repo_on_path()
    menus = unreal.ToolMenus.get()

    main_menu = menus.find_menu("LevelEditor.MainMenu")
    if main_menu is None:
        unreal.log_error("[maya_to_ue] 找不到主菜单，无法安装。")
        return

    # Re-running the installer should refresh, not stack duplicates.
    menus.remove_menu(f"LevelEditor.MainMenu.{MENU_NAME}")

    tool_menu = main_menu.add_sub_menu(
        main_menu.menu_name, "", MENU_NAME, MENU_LABEL, "Maya→UE 动画交付"
    )

    for entry_name, label, tooltip, func_name in _ENTRY_SPECS:
        entry = unreal.ToolMenuEntry(
            name=entry_name,
            type=unreal.MultiBlockType.MENU_ENTRY,
        )
        entry.set_label(label)
        entry.set_tool_tip(tooltip)
        entry.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON,
            "",
            string=(
                f'import sys\n'
                f'sys.path.insert(0, r"{REPO_ROOT}") '
                f'if r"{REPO_ROOT}" not in sys.path else None\n'
                f'import install_ue_menu\n'
                f'install_ue_menu.{func_name}()'
            ),
        )
        tool_menu.add_menu_entry("Actions", entry)

    menus.refresh_all_widgets()
    unreal.log(f"[maya_to_ue] 菜单已安装：主菜单栏 → 「{MENU_LABEL}」")
    unreal.log(f"[maya_to_ue] 仓库路径：{REPO_ROOT}")


install()
