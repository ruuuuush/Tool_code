"""Launcher for the Maya->UE pipeline tool inside Maya.

How to use:
    1. Add this folder to PYTHONPATH (or place the script on a shelf).
    2. In Maya's Script Editor (Python tab), run:

           import launch_maya_tool
           launch_maya_tool.show()

    Or bind it to a shelf button with the same two lines.

    After editing the tool's source, reopen it with the freshly-read code:

           launch_maya_tool.reload_and_show()

This launcher is intentionally tiny — it only wires the repo onto
sys.path and calls into maya.ui.show(). All real logic lives inside the
mtu_maya/ package, so the launcher never needs updating when checks or UI
panels change.
"""

from __future__ import annotations

import os
import sys

# Packages that make up the tool. Everything under these names is dropped
# from the module cache on reload, which is what makes edits take effect
# without restarting Maya.
_TOOL_PACKAGES = ("mtu_maya", "bridge")


def _ensure_repo_on_path() -> str:
    """Add the repo root (parent of this file) to sys.path if missing.

    Returns the repo root so callers know where the tool lives.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    return here


def _require_pyside() -> None:
    try:
        import PySide6  # noqa: F401
    except ImportError:
        try:
            import PySide2  # noqa: F401
        except ImportError as exc:
            print(f"[maya_to_ue] PySide6/PySide2 not available: {exc}")
            raise


def show():
    """Open the pipeline tool window."""
    _ensure_repo_on_path()
    _require_pyside()
    from mtu_maya.ui import show as _show
    return _show()


def unload(modules=None) -> int:
    """Drop the tool's modules from the module table. Returns how many went.

    Maya keeps one Python session alive for its whole run, so an edited
    module stays invisible until its cached copy is thrown away.

    *modules* defaults to the live ``sys.modules``; tests pass a throwaway
    dict so checking this logic doesn't yank packages out from under the
    rest of the suite.
    """
    table = sys.modules if modules is None else modules
    prefixes = tuple(p + "." for p in _TOOL_PACKAGES)
    stale = [
        name for name in list(table)
        if name in _TOOL_PACKAGES or name.startswith(prefixes)
    ]
    for name in stale:
        del table[name]
    return len(stale)


def reload_and_show():
    """Reload the tool from disk and reopen the window.

    Use this after changing the source; plain show() would hand back the
    version Maya loaded the first time.
    """
    _ensure_repo_on_path()
    _require_pyside()
    dropped = unload()
    print(f"[maya_to_ue] reloaded ({dropped} modules)")
    return show()


if __name__ == "__main__":
    show()
