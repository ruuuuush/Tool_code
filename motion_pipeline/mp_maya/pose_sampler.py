"""mp_maya.pose_sampler

Samples world-space bone positions out of the open Maya scene so
``mp_core`` can measure contact and slide.

Why Maya and not UE for this step: the source clips are FBX on disk, and
``maya.cmds`` yields exact evaluated world positions per frame with no
version-dependent API guesswork. UE's Python API does not expose
``GetBonePoseForFrame`` — it is a Blueprint/C++ node only — so an
in-engine sampler would need a SkeletalMeshComponent rig to be accurate.
That can come later if the augmentation path moves in-engine; see
docs/01 §7.

All ``maya.cmds`` use is lazy so this module imports cleanly (and its
logic stays inspectable) outside Maya.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from mp_core.foot_contact import (
    ROLE_BALL,
    ROLE_FOOT,
    ROLE_TOE_TIP,
    ROLE_UNKNOWN,
    ClipSamples,
    FootInfo,
    Vec3,
)

# Short-name fragments that identify a foot-ish joint.
FOOT_PATTERNS = ("foot", "toe", "ball", "ankle")

# Role patterns. Toe tip is tested first: "LeftToe_End" also contains
# "toe", and the ball pattern would otherwise swallow it.
_TOE_TIP_PATTERNS = ("toe_end", "toeend", "toe_tip", "toetip")
_BALL_PATTERNS = ("toebase", "toe_base", "ball")
_FOOT_ROLE_PATTERNS = ("foot", "ankle")

# Maya time units that map to a fixed frame rate. Time-based units
# (sec/min/hour) are rejected rather than guessed at.
_FPS_BY_TIME_UNIT: Dict[str, float] = {
    "game": 15.0,
    "film": 24.0,
    "pal": 25.0,
    "ntsc": 30.0,
    "show": 48.0,
    "palf": 50.0,
    "ntscf": 60.0,
}

_TIME_UNIT_BY_FPS: Dict[float, str] = {v: k for k, v in _FPS_BY_TIME_UNIT.items()}

_UP_INDEX_BY_AXIS = {"y": 1, "z": 2}


def _cmds():
    try:
        import maya.cmds as cmds  # type: ignore
        return cmds
    except ImportError as exc:
        raise ImportError(
            "maya.cmds is only available inside a Maya session."
        ) from exc


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def check_environment() -> List[str]:
    """Return a list of problems; empty means the sampler can run."""
    problems: List[str] = []
    try:
        cmds = _cmds()
    except ImportError as exc:
        return [str(exc)]

    for name in (
        "currentTime",
        "currentUnit",
        "keyframe",
        "listRelatives",
        "loadPlugin",
        "ls",
        "playbackOptions",
        "upAxis",
        "xform",
    ):
        if not hasattr(cmds, name):
            problems.append("maya.cmds.{} is missing".format(name))

    unit = cmds.currentUnit(query=True, time=True)
    if unit not in _FPS_BY_TIME_UNIT:
        problems.append(
            "time unit '{}' is not a fixed frame rate; set the scene to one of {}".format(
                unit, ", ".join(sorted(_FPS_BY_TIME_UNIT))
            )
        )

    axis = cmds.upAxis(query=True, axis=True)
    if axis not in _UP_INDEX_BY_AXIS:
        problems.append("unrecognised up axis: {}".format(axis))
    return problems


def scene_fps() -> float:
    cmds = _cmds()
    unit = cmds.currentUnit(query=True, time=True)
    if unit not in _FPS_BY_TIME_UNIT:
        raise ValueError(
            "time unit '{}' has no fixed frame rate; cannot measure slide speed".format(unit)
        )
    return _FPS_BY_TIME_UNIT[unit]


def set_scene_fps(fps: float) -> None:
    """Align the scene time unit to a source frame rate.

    Maya defaults to ``film`` (24) while most mocap FBX — Mixamo included —
    is ``ntsc`` (30). Maya does not rescale keys across that gap, so the
    clip silently plays 25% slow and every per-second metric is off by the
    same factor. Aligning first is what makes "slide per second" mean
    something.
    """
    unit = _TIME_UNIT_BY_FPS.get(float(fps))
    if unit is None:
        raise ValueError(
            "no Maya time unit maps to {} fps; supported: {}".format(
                fps, sorted(_TIME_UNIT_BY_FPS)
            )
        )
    _cmds().currentUnit(time=unit)


def scene_up_index() -> int:
    cmds = _cmds()
    axis = cmds.upAxis(query=True, axis=True)
    if axis not in _UP_INDEX_BY_AXIS:
        raise ValueError("unrecognised up axis: {}".format(axis))
    return _UP_INDEX_BY_AXIS[axis]


def timeline() -> tuple:
    """(start, end) of the playback range, as ints."""
    cmds = _cmds()
    start = int(cmds.playbackOptions(query=True, minTime=True))
    end = int(cmds.playbackOptions(query=True, maxTime=True))
    return start, end


def animation_range(nodes: Optional[Sequence[str]] = None) -> Optional[tuple]:
    """(first key, last key) across the given nodes, or None if unkeyed.

    An imported FBX keeps its own key range, which usually does not match
    the playback range. Sampling past the last key would repeat the final
    pose and quietly corrupt every slide number, so this is what the
    sampler defaults to rather than the timeline.
    """
    cmds = _cmds()
    targets = list(nodes) if nodes is not None else list_joints()
    if not targets:
        return None
    times = cmds.keyframe(targets, query=True, timeChange=True) or []
    if not times:
        return None
    return int(round(min(times))), int(round(max(times)))


# ---------------------------------------------------------------------------
# Joint discovery and classification
# ---------------------------------------------------------------------------


def _short_name(node: str) -> str:
    return node.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


def list_joints() -> List[str]:
    return sorted(_cmds().ls(type="joint", long=True) or [])


def find_foot_bones(joints: Optional[Sequence[str]] = None) -> List[str]:
    """Joints whose short name looks like a foot. Heuristic, not a promise.

    Deliberately loose: the caller sees the list and can override it. A
    wrong guess here would silently shift every slide number.
    """
    joints = list(joints) if joints is not None else list_joints()
    hits = [
        j for j in joints
        if any(pattern in _short_name(j).lower() for pattern in FOOT_PATTERNS)
    ]
    return sorted(hits)


def classify_role(short_name: str) -> str:
    """Classify a bone's short name as foot / ball / toe_tip / unknown.

    A toe tip is not a grounding signal — it rolls through stance by
    design — so it must be distinguishable from the ankle, which is.
    """
    lower = short_name.lower()
    if any(pattern in lower for pattern in _TOE_TIP_PATTERNS):
        return ROLE_TOE_TIP
    if any(pattern in lower for pattern in _BALL_PATTERNS):
        return ROLE_BALL
    if any(pattern in lower for pattern in _FOOT_ROLE_PATTERNS):
        return ROLE_FOOT
    return ROLE_UNKNOWN


def classify_side(short_name: str) -> str:
    """Classify a bone's short name as left / right / empty.

    Handles both conventions in the wild: Mixamo-style ``LeftFoot`` and
    UE-style ``foot_l``.
    """
    lower = short_name.lower()
    if "left" in lower:
        return "left"
    if "right" in lower:
        return "right"
    stripped = lower.rstrip("0123456789")
    if stripped.endswith(("_l", ".l", "-l")):
        return "left"
    if stripped.endswith(("_r", ".r", "-r")):
        return "right"
    return ""


def classify_foot_bone(node: str) -> FootInfo:
    short = _short_name(node)
    return FootInfo(role=classify_role(short), side=classify_side(short))


def find_feet(joints: Optional[Sequence[str]] = None) -> Dict[str, FootInfo]:
    """Foot-ish joints mapped to what each one represents."""
    return {bone: classify_foot_bone(bone) for bone in find_foot_bones(joints)}


def find_root_joint(joints: Optional[Sequence[str]] = None) -> Optional[str]:
    """The topmost joint, i.e. the one with no joint parent."""
    joints = list(joints) if joints is not None else list_joints()
    joint_set = set(joints)
    for joint in joints:
        parents = _cmds().listRelatives(joint, parent=True, fullPath=True) or []
        if not any(p in joint_set for p in parents):
            return joint
    return None


def estimate_scale_ref(joints: Optional[Sequence[str]] = None, up_index: Optional[int] = None) -> float:
    """Character height, used to normalise every measurement.

    Measured as the vertical extent of the joints at the current frame —
    crude, but it is the same crude number for good and bad clips, which
    is all normalisation needs.
    """
    cmds = _cmds()
    joints = list(joints) if joints is not None else list_joints()
    up = up_index if up_index is not None else scene_up_index()
    if not joints:
        return 0.0
    heights = [cmds.xform(j, query=True, worldSpace=True, translation=True)[up] for j in joints]
    return max(heights) - min(heights)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def world_position(node: str) -> Vec3:
    coords = _cmds().xform(node, query=True, worldSpace=True, translation=True)
    return (float(coords[0]), float(coords[1]), float(coords[2]))


def sample_clip(
    name: str,
    root_bone: str,
    foot_bones: Sequence[str],
    start: Optional[int] = None,
    end: Optional[int] = None,
    step: int = 1,
    foot_info: Optional[Dict[str, FootInfo]] = None,
) -> ClipSamples:
    """Evaluate every joint of interest across a frame range.

    Restores the scene's current frame afterwards — sampling must not
    move the user's playhead. Roles are classified from bone names unless
    ``foot_info`` overrides them.
    """
    cmds = _cmds()
    if start is None or end is None:
        detected = animation_range() or timeline()
        start = detected[0] if start is None else start
        end = detected[1] if end is None else end
    if end < start:
        raise ValueError("end frame {} is before start frame {}".format(end, start))
    if step < 1:
        raise ValueError("step must be >= 1")

    info = (
        dict(foot_info)
        if foot_info is not None
        else {bone: classify_foot_bone(bone) for bone in foot_bones}
    )

    original_time = cmds.currentTime(query=True)
    frames: List[int] = []
    feet: Dict[str, List[Vec3]] = {foot: [] for foot in foot_bones}
    root_track: List[Vec3] = []

    try:
        for frame in range(int(start), int(end) + 1, step):
            cmds.currentTime(frame)
            frames.append(frame)
            for foot in foot_bones:
                feet[foot].append(world_position(foot))
            root_track.append(world_position(root_bone))
        up_index = scene_up_index()
        scale_ref = estimate_scale_ref(up_index=up_index)
    finally:
        cmds.currentTime(original_time)

    return ClipSamples(
        name=name,
        fps=scene_fps(),
        frames=frames,
        feet=feet,
        root=root_track,
        scale_ref=scale_ref,
        up_index=up_index,
        foot_info=info,
    )


# ---------------------------------------------------------------------------
# FBX workflow glue (used by the launcher, which owns the destructive bits)
# ---------------------------------------------------------------------------


def import_fbx(path: str, source_fps: Optional[float] = None) -> None:
    """Import an FBX into whatever scene is currently open.

    Pass ``source_fps`` to align the scene time unit first — see
    ``set_scene_fps`` for why that matters.
    """
    cmds = _cmds()
    if source_fps is not None:
        set_scene_fps(source_fps)
    # In a bare mayapy session the FBX plugin is not loaded yet; in a Maya
    # GUI session it already is, and loadPlugin is a no-op.
    try:
        cmds.loadPlugin("fbxmaya", quiet=True)
    except Exception:
        pass
    cmds.file(path, i=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=True)


def open_new_scene() -> None:
    """Discard the current scene. The launcher asks before calling this."""
    _cmds().file(new=True, force=True)


def ensure_maya_ready() -> None:
    """Start Maya standalone when running under mayapy outside the GUI.

    Safe to call in a normal Maya session: initialisation then fails and
    is swallowed, because the session is already up.
    """
    try:
        import maya.standalone  # type: ignore
    except ImportError:
        return
    try:
        maya.standalone.initialize(name="python")
    except Exception:
        pass


__all__ = [
    "FOOT_PATTERNS",
    "animation_range",
    "check_environment",
    "classify_foot_bone",
    "classify_role",
    "classify_side",
    "ensure_maya_ready",
    "estimate_scale_ref",
    "find_feet",
    "find_foot_bones",
    "find_root_joint",
    "import_fbx",
    "list_joints",
    "open_new_scene",
    "sample_clip",
    "scene_fps",
    "scene_up_index",
    "set_scene_fps",
    "timeline",
    "world_position",
]
