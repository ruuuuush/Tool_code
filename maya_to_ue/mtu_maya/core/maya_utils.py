"""maya.core.maya_utils

Thin wrappers around maya.cmds used by the validators and exporter.

All functions here import maya.cmds lazily so that this module can be
imported (and its non-Maya helpers tested) without a Maya session.
"""

from __future__ import annotations

from typing import List, Optional

# Cached cmds module reference. Kept for compatibility with code that injects a
# fake Maya module in tests; `cmds()` otherwise imports the active session module.
_cmds = None


def cmds():
    """Return maya.cmds, importing it lazily.

    Raises ImportError with a helpful message if Maya is not available,
    so callers can surface a clear error instead of a raw ImportError.
    """
    global _cmds
    if _cmds is not None:
        return _cmds
    try:
        import maya.cmds as maya_cmds  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "maya.cmds is not available. Run this inside Maya's Python "
            "interpreter (e.g. via the Script Editor or a shelf button)."
        ) from exc
    return maya_cmds


# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------

def current_scene_name() -> str:
    """Return the scene name without extension, or 'untitled'."""
    c = cmds()
    path = c.file(query=True, sceneName=True) or ""
    if not path:
        return "untitled"
    import os
    return os.path.splitext(os.path.basename(path))[0]


def scene_units() -> str:
    """Return the linear working unit, e.g. 'cm', 'm', 'mm'."""
    c = cmds()
    return c.currentUnit(query=True, linear=True)


def scene_up_axis() -> str:
    """Return 'y' or 'z' (the world up axis).

    currentUnit() has no 'up' flag — the up axis is queried via the dedicated
    upAxis command. Returns lowercase for consistent comparisons.
    """
    c = cmds()
    return str(c.upAxis(query=True, axis=True)).lower()


# Maya time-unit name -> actual frames-per-second.
# currentUnit(query=True, time=True) returns one of these *names*, not a number.
_TIME_UNIT_FPS = {
    "game": 15.0,
    "film": 24.0,
    "pal": 25.0,
    "ntsc": 30.0,
    "show": 48.0,
    "palf": 50.0,
    "ntscf": 60.0,
    # sub-frame / misc units
    "2fps": 2.0, "3fps": 3.0, "4fps": 4.0, "5fps": 5.0, "6fps": 6.0,
    "8fps": 8.0, "10fps": 10.0, "12fps": 12.0, "16fps": 16.0, "20fps": 20.0,
    "40fps": 40.0, "75fps": 75.0, "80fps": 80.0, "100fps": 100.0,
    "120fps": 120.0, "125fps": 125.0, "150fps": 150.0, "200fps": 200.0,
    "240fps": 240.0, "250fps": 250.0, "300fps": 300.0, "375fps": 375.0,
    "400fps": 400.0, "500fps": 500.0, "600fps": 600.0, "750fps": 750.0,
    "1000fps": 1000.0, "1200fps": 1200.0, "1500fps": 1500.0,
    "2000fps": 2000.0, "3000fps": 3000.0, "6000fps": 6000.0,
    # milliseconds / seconds based
    "millisec": 1000.0, "sec": 1.0, "min": 1.0 / 60.0, "hour": 1.0 / 3600.0,
}


def scene_fps() -> float:
    """Return the scene frame rate as a float (e.g. 30.0, 24.0).

    currentUnit(time) returns a unit *name* like 'film'/'ntsc', so map it to
    its fps value. Custom "<n>fps" units are parsed numerically.
    """
    c = cmds()
    unit = str(c.currentUnit(query=True, time=True)).strip()
    if unit in _TIME_UNIT_FPS:
        return _TIME_UNIT_FPS[unit]
    if unit.endswith("fps"):
        try:
            return float(unit[:-3])
        except ValueError:
            pass
    # Unknown unit — surface a clear default rather than crash.
    return 30.0


def set_scene_units_cm() -> None:
    cmds().currentUnit(linear="cm")


def set_scene_up_axis_z() -> None:
    """Rotate the scene so Z is the up axis (uses the upAxis command)."""
    cmds().upAxis(axis="z", rotateView=True)


def set_scene_fps(fps: float) -> None:
    """Set the scene time unit to an exact Maya frame rate."""
    c = cmds()
    rate_map = {
        24.0: "film",
        25.0: "pal",
        30.0: "ntsc",
        48.0: "show",
        50.0: "palf",
        60.0: "ntscf",
    }
    rate = float(fps)
    unit = rate_map.get(rate, f"{rate:g}fps")
    c.currentUnit(time=unit)


def timeline_range() -> tuple:
    """Return (start_frame, end_frame) of the playback range."""
    c = cmds()
    start = int(c.playbackOptions(query=True, animationStartTime=True))
    end = int(c.playbackOptions(query=True, animationEndTime=True))
    return start, end


# ---------------------------------------------------------------------------
# Selection / node helpers
# ---------------------------------------------------------------------------

def selected(long: bool = False) -> List[str]:
    """Return the current selection as a list of node names."""
    return cmds().ls(selection=True, long=long) or []


def select(nodes, add: bool = False) -> None:
    c = cmds()
    if not nodes:
        return
    if add:
        c.select(nodes, add=True)
    else:
        c.select(nodes)


def exists(node: str) -> bool:
    return cmds().objExists(node)


def node_type(node: str) -> str:
    return cmds().nodeType(node)


# ---------------------------------------------------------------------------
# Skeleton helpers
# ---------------------------------------------------------------------------

def list_joints() -> List[str]:
    """Return all joints in the scene, full DAG paths."""
    return cmds().ls(type="joint", long=True) or []


def joint_scale(node: str) -> tuple:
    """Return (sx, sy, sz) of a joint's scale."""
    c = cmds()
    return (
        float(c.getAttr(f"{node}.scaleX")),
        float(c.getAttr(f"{node}.scaleY")),
        float(c.getAttr(f"{node}.scaleZ")),
    )


def find_root_joint() -> Optional[str]:
    """Return the top-most joint in the scene (no joint parent), or None.

    Returns the long DAG path. If multiple roots exist, returns the first
    by alphabetical order — callers may want to validate that there is
    exactly one.
    """
    joints = list_joints()
    if not joints:
        return None
    roots = [j for j in joints if "|" not in j.lstrip("|").replace("|", "", 1)]
    # A root joint has no joint ancestor: its parent (if any) is not a joint.
    c = cmds()
    true_roots = []
    for j in joints:
        parent = c.listRelatives(j, parent=True, fullPath=True)
        if not parent or c.nodeType(parent[0]) != "joint":
            true_roots.append(j)
    if not true_roots:
        return None
    true_roots.sort()
    return true_roots[0]


def _shallowest(paths: List[str]) -> Optional[str]:
    """在一堆候选长路径里挑层级最浅的（'|' 最少）—— 最靠近根的那个。

    同名关节匹配到多个时，用户几乎总是想要根那个（Hips），
    而不是嵌套深处的某个。'|' 数相同再按路径长度、字典序稳定取舍。
    """
    if not paths:
        return None
    return min(paths, key=lambda p: (p.count("|"), len(p), p))


def subtree_joints(root: str) -> List[str]:
    """Return *root* plus every joint below it, full DAG paths.

    A root joint often carries no animation at all (in-place clips leave it
    untouched), so anything asking "does this rig have keys" has to look at
    the descendants too.
    """
    if not root:
        return []
    c = cmds()
    try:
        if not c.objExists(root):
            return []
        kids = c.listRelatives(root, allDescendents=True, type="joint", fullPath=True) or []
        found = c.ls(root, long=True) or [root]
        return list(found) + list(kids)
    except Exception:
        return []


def keyframe_range(nodes) -> Optional[tuple]:
    """Return (first_frame, last_frame) across every key on *nodes*.

    This is the animation's real extent. The playback range is a view
    setting — it says where the time slider happens to sit, not how long
    the animation is.

    Returns None when the nodes carry no keys at all, so callers can fall
    through to the next candidate instead of trusting a bogus (0, 0).
    """
    if not nodes:
        return None
    c = cmds()
    try:
        times = c.keyframe(nodes, query=True, timeChange=True) or []
    except Exception:
        return None
    if not times:
        return None
    # Keys land on fractional times after a time warp / scale; 34.6 belongs
    # to frame 35, not 34.
    return int(round(min(times))), int(round(max(times)))


def resolve_joint(name: str) -> Optional[str]:
    """把用户输入的骨骼名解析成场景里真实存在的关节（返回长路径）。

    制作人员可能敲短名（Hips）、带命名空间（char:Hips）、或粘贴长路径
    （|group|Hips）—— 这些都该认得出来，而不是只认精确长路径。
    多个同名时返回【层级最浅】的那个（最可能是根），找不到返回 None。
    """
    if not name or not str(name).strip():
        return None
    name = str(name).strip()
    c = cmds()

    # 1) 原样就是个关节（短名唯一 或 已是长路径）。
    #    c.ls(name, long=True) 可能返回多个匹配（同名层级），挑最浅的，
    #    不能盲信 long[0]（Maya 按创建顺序排，深层节点可能在前）。
    try:
        if c.objExists(name) and c.nodeType(name) == "joint":
            long = c.ls(name, long=True) or []
            picked = _shallowest(long)
            if picked:
                return picked
        # fall through to the by-short-name pass below
    except Exception:
        pass

    # 2) 在全部关节里按"短名"匹配（忽略命名空间），同样挑最浅的。
    short_want = name.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
    matches = []
    for j in list_joints():
        short = j.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
        if short == short_want:
            matches.append(j)
    return _shallowest(matches)


# ---------------------------------------------------------------------------
# FBX plugin helpers
# ---------------------------------------------------------------------------

def fbx_plugin_loaded() -> bool:
    """Return True if the FBX plugin (plugin=True) is loaded."""
    c = cmds()
    try:
        loaded = bool(c.pluginInfo("fbxmaya", query=True, loaded=True))
        if loaded:
            return True
    except Exception:
        pass
    try:
        return bool(c.pluginInfo("fbxmaya.mll", query=True, loaded=True))
    except Exception:
        return False


def ensure_fbx_plugin() -> bool:
    """Try to load the FBX plugin. Returns True if loaded after the call."""
    c = cmds()
    if fbx_plugin_loaded():
        return True
    for plugin in ("fbxmaya", "fbxmaya.mll"):
        try:
            c.loadPlugin(plugin, quiet=True)
        except Exception:
            continue
        if fbx_plugin_loaded():
            return True
    return False
