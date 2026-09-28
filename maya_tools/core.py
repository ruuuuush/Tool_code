"""core

Common helper functions that wrap Maya's cmds/pymel for everyday tasks.
Importing this module is lazy: heavy Maya imports happen inside functions
so that the module can be imported without Maya installed.
"""

from __future__ import annotations

from typing import List, Optional


def _cmds():
    """Import and return maya.cmds lazily.

    Raises:
        ImportError: if Maya's Python modules are not on the path.
    """
    try:
        import maya.cmds as cmds
    except ImportError as exc:  # Maya not available in this interpreter
        raise ImportError(
            "maya.cmds could not be imported. "
            "Run this inside Maya's Python interpreter or a Maya session."
        ) from exc
    return cmds


def selected(long: bool = False) -> List[str]:
    """Return the current selection as a list of node names.

    Args:
        long: If True, return full DAG paths instead of short names.
    """
    cmds = _cmds()
    return cmds.ls(selection=True, long=long) or []


def select(node: str, add: bool = False) -> None:
    """Select a node (or add to the current selection)."""
    cmds = _cmds()
    if add:
        cmds.select(node, add=True)
    else:
        cmds.select(node)


def exists(node: str) -> bool:
    """Return True if a node with the given name/path exists in the scene."""
    cmds = _cmds()
    return cmds.objExists(node)


def delete(node: str) -> None:
    """Delete a node if it exists."""
    cmds = _cmds()
    if exists(node):
        cmds.delete(node)


def rename(node: str, new_name: str) -> str:
    """Rename a node and return its new name."""
    cmds = _cmds()
    return cmds.rename(node, new_name)


def print_scene_summary() -> None:
    """Print a short summary of the current scene to the script editor."""
    cmds = _cmds()
    transforms = cmds.ls(type="transform") or []
    meshes = cmds.ls(type="mesh") or []
    joints = cmds.ls(type="joint") or []
    print(
        "Scene summary:\n"
        f"  transforms: {len(transforms)}\n"
        f"  meshes:     {len(meshes)}\n"
        f"  joints:     {len(joints)}"
    )
