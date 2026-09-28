"""Maya→UE 交付工具 · 一键安装到 Maya 工具架（shelf）

怎么用（只装一次，以后点工具架按钮即可）：
    1. 打开 Maya → Script Editor（脚本编辑器）→ 切到 Python 标签页。
    2. 把这个文件整个【复制粘贴】进脚本编辑器（或 File → Open 打开它）。
    3. 点【运行】（Ctrl+Enter / 上方蓝色播放键）。

    ※ 直接粘贴运行也能用 —— 脚本里有个 REPO_PATH_FALLBACK 常量兜底。
      只有当你的仓库不在默认位置时，才需要改那一行。

装好后会发生什么：
    • 顶部工具架（Shelf）多出一个「MayaToUE」页，里面有一个「动画交付」按钮。
    • 把实际仓库路径永久写进 Maya 的 userSetup.py —— 重启 Maya 也能用。
    • 装完会自动弹出一次工具，确认能打开。

这个脚本只写两处东西，都是 Maya 常规做法，随时可卸：
    • <Documents>/maya/<版本>/prefs/shelves/shelf_MayaToUE.mel   （按钮）
    • <Documents>/maya/<版本>/scripts/userSetup.py              （自动加 sys.path）

想卸载：删掉上面 shelf 文件，再把 userSetup.py 里那两行删掉即可。
"""

from __future__ import annotations

import os
import sys

# ===========================================================================
# ★ 仅在将本文件直接粘贴到 Maya Script Editor 运行、且无法通过 __file__
# 自动定位仓库时，才需要把这里改为真实仓库目录。
REPO_PATH_FALLBACK = r"D:/tool_code/maya_to_ue"
# ===========================================================================


def _resolve_repo_root() -> str:
    """仓库根目录。

    优先用 __file__（File → Open 打开运行时有效）；
    粘进 Script Editor 运行时没有 __file__，就回退到上面的常量。
    """
    here = globals().get("__file__")
    if here:
        return os.path.dirname(os.path.abspath(here))
    # 安装器以 File → Open 方式运行时 __file__ 一定存在；直接粘贴时只能
    # 使用明确配置的回退路径，避免错误猜测当前工作目录。
    return os.path.abspath(REPO_PATH_FALLBACK)


# 本安装器所在的目录就是仓库根目录（launch 用）。
REPO_ROOT = _resolve_repo_root()

# 工具架按钮显示的文字 / 图标。
BUTTON_LABEL = "动画交付"
BUTTON_ANNOTATION = "Maya → UE 动画交付工具（检查 / 片段 / 导出）"
BUTTON_ICON = "animCurve.png"      # Maya 自带图标，避免依赖外部文件
SHELF_NAME = "MayaToUE"

# 写进 userSetup.py 和 shelf 按钮里的那两行启动命令（保持幂等、可重复运行）。
LAUNCH_SNIPPET = (
    "# [maya_to_ue] auto-added by install_shelf_button.py\n"
    "import sys as _s\n"
    "if r\"{root}\" not in _s.path: _s.path.insert(0, r\"{root}\")\n"
).format(root=REPO_ROOT)

# 写进 shelf 按钮里的启动命令。userSetup.py 只负责加入 sys.path，不能在 Maya
# 启动阶段弹出工具窗口。
SHELF_LAUNCH_SNIPPET = (
    "import sys as _s\n"
    "if r\"{root}\" not in _s.path: _s.path.insert(0, r\"{root}\")\n"
    "import launch_maya_tool as _lm\n"
    "_lm.show()\n"
).format(root=REPO_ROOT)

MARKER = "[maya_to_ue]"


# --------------------------------------------------------------------------- helpers

def _maya_scripts_dir() -> str:
    """userSetup.py 所在的目录（<Documents>/maya/<ver>/scripts）。"""
    import maya.cmds as cmds
    return cmds.internalVar(userScriptDir=True)


def _maya_shelves_dir() -> str:
    """shelf 文件所在目录（<Documents>/maya/<ver>/prefs/shelves）。"""
    import maya.cmds as cmds
    return cmds.internalVar(userShelfDir=True)


def _ensure_path_in_user_setup() -> bool:
    """把仓库根目录写进 userSetup.py（幂等）。返回是否本次新增。"""
    scripts_dir = _maya_scripts_dir()
    os.makedirs(scripts_dir, exist_ok=True)
    path = os.path.join(scripts_dir, "userSetup.py")

    existing = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            existing = fh.read()

    if MARKER in existing or REPO_ROOT in existing:
        return False  # 已经加过

    with open(path, "a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write("\n# [maya_to_ue] make the tool importable on startup\n")
        fh.write("import sys as _s\n")
        fh.write(
            "if r\"{root}\" not in _s.path: _s.path.insert(0, r\"{root}\")\n".format(
                root=REPO_ROOT
            )
        )
    return True


def _build_shelf_button() -> str:
    """在当前 Maya 会话里建/更新 shelf 按钮（幂等）。返回提示文字。"""
    import maya.cmds as cmds
    import maya.mel as mel

    # 确保顶层 shelf 布局里有一个叫 SHELF_NAME 的页。
    # 直接读全局变量 $gShelfTopLevel，不用拼 MEL 语句（单行 mel.eval 对声明式语法很挑）。
    try:
        top_shelf = mel.eval("$mtu_topShelfTmp = $gShelfTopLevel")
    except Exception:
        top_shelf = "ShelfLayout"  # 兜底：Maya 默认顶层 shelf 布局名
    if not cmds.shelfLayout(SHELF_NAME, exists=True):
        cmds.shelfLayout(SHELF_NAME, parent=top_shelf)

    # 按钮已存在（按 annotation 找）就直接复用，不删不建 —— 幂等且不会重复。
    children = cmds.shelfLayout(SHELF_NAME, query=True, childArray=True) or []
    for child in children:
        try:
            if cmds.control(child, query=True, annotation=True) == BUTTON_ANNOTATION:
                cmds.shelfButton(child, edit=True, command=SHELF_LAUNCH_SNIPPET, sourceType="python")
                return SHELF_NAME
        except Exception:
            pass

    cmds.shelfButton(
        parent=SHELF_NAME,
        label=BUTTON_LABEL,
        annotation=BUTTON_ANNOTATION,
        image=BUTTON_ICON,
        imageOverlayLabel="交付",
        overlayLabelColor=(1.0, 1.0, 1.0),
        overlayLabelBackColor=(0.12, 0.12, 0.13, 0.9),
        command=SHELF_LAUNCH_SNIPPET,
        sourceType="python",
    )
    return SHELF_NAME


def _persist_shelf() -> None:
    """把当前 shelf 布局写回磁盘，重启 Maya 后仍在。"""
    import maya.cmds as cmds
    try:
        cmds.saveAllShelves(_maya_shelves_dir())
    except Exception as exc:  # 不致命：按钮在当前会话已经有了
        print(f"[maya_to_ue] 保存 shelf 文件失败（本次会话仍可用）: {exc}")


# --------------------------------------------------------------------------- entry

def install() -> None:
    import maya.cmds as cmds

    added = _ensure_path_in_user_setup()
    shelf = _build_shelf_button()
    _persist_shelf()

    print("=" * 56)
    print("[maya_to_ue] 一键安装完成 ✔")
    print(f"  · 仓库路径: {REPO_ROOT}")
    print(f"  · sys.path 写入 userSetup.py: {'本次新增' if added else '已存在，跳过'}")
    print(f"  · 工具架按钮: 「{shelf}」页 → 「{BUTTON_LABEL}」")
    print("  · 以后直接点那个按钮就能打开工具（重启 Maya 也在）。")
    print("=" * 56)

    # 装完立刻弹一次工具，验证可用。
    try:
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        import launch_maya_tool
        launch_maya_tool.show()
    except Exception as exc:
        cmds.warning(f"[maya_to_ue] 安装成功，但自动打开工具失败：{exc}")


if __name__ == "__main__":
    install()
