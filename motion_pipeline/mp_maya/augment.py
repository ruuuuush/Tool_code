"""mp_maya.augment

Applies the augmentation plans from ``mp_core.augment`` to real Maya
animation curves, and exports the result.

The deliverable of Step 3 is animation data, so this is where the actual
production happens. Everything decidable (which bone mirrors onto which,
what a warped range becomes) lives in mp_core and is unit-tested; this
module only touches the scene.

Each variant is produced in a fresh scene from the source FBX rather than
by duplicating the rig in place. Duplicating a joint hierarchy does not
reliably carry its animation curves (they are upstream nodes), and
getting a silent copy-without-animation would be far more expensive to
diagnose than paying the re-import.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

from mp_core.augment import (
    mirror_diagonal,
    mirror_map,
    retime_source_time,
    warped_range,
)


def _cmds():
    try:
        import maya.cmds as cmds  # type: ignore
        return cmds
    except ImportError as exc:
        raise ImportError(
            "maya.cmds is only available inside a Maya session."
        ) from exc


# ---------------------------------------------------------------------------
# 4x4 maths, in Maya's row-major layout
# ---------------------------------------------------------------------------

# Attributes worth carrying across a mirror. Anything the source clip does
# not key stays unkeyed in the variant, so the export does not grow
# channels the rig never had.
_KEYABLE = (
    "translateX",
    "translateY",
    "translateZ",
    "rotateX",
    "rotateY",
    "rotateZ",
    "scaleX",
    "scaleY",
    "scaleZ",
)


def _mat_mul(a: Sequence[float], b: Sequence[float]) -> List[float]:
    """Multiply two 4x4 matrices given as 16 floats, row-major."""
    out = [0.0] * 16
    for row in range(4):
        for col in range(4):
            total = 0.0
            for k in range(4):
                total += a[row * 4 + k] * b[k * 4 + col]
            out[row * 4 + col] = total
    return out


def _diagonal(values: Sequence[float]) -> List[float]:
    return [
        values[0], 0.0, 0.0, 0.0,
        0.0, values[1], 0.0, 0.0,
        0.0, 0.0, values[2], 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


# ---------------------------------------------------------------------------
# Time warp
# ---------------------------------------------------------------------------


def retime(
    nodes: Sequence[str], start: int, end: int, factor: float
) -> Tuple[int, int]:
    """Retime a clip by dense resampling, in place. Returns the new range.

    Samples the source curve at the *fractional* times the new frame grid
    falls on, then writes those values onto integer frames.

    Why not ``cmds.scaleKey``: scaling key times lands them on fractional
    positions while leaving the curve tangents computed for the original
    spacing. The retimed curve is then not a clean resample — the planted
    foot's sweep turns lumpy and the gate rejects it (measured +199% slide
    at factor 0.85; docs/01 §10.2). Sampling the source and re-keying
    never touches a tangent.

    The bake is dense (one output frame), which is what makes the
    resample faithful. Thinning it afterwards is a separate, optional
    concern.

    Ordering rule: retime must run BEFORE any operation that re-keys the
    curves (mirroring included). Re-keyed curves carry default tangents
    instead of the source FBX's, and this function samples at fractional
    times where tangents decide the value. Retiming a mirrored clip
    measured ~2x the slide of retiming the source directly; mirroring a
    retimed clip was exact (docs/01 §10.2).
    """
    cmds = _cmds()
    if factor <= 0:
        raise ValueError("factor must be > 0, got {}".format(factor))

    new_start, new_end = warped_range(start, end, factor)
    if factor == 1.0:
        return new_start, new_end

    channels = {
        node: attrs
        for node, attrs in ((node, keyed_attributes(node)) for node in nodes)
        if attrs
    }
    if not channels:
        return new_start, new_end

    original_time = cmds.currentTime(query=True)
    try:
        # Phase 1: read the entire result before writing anything. Reading
        # while writing would sample curves that are already retimed.
        snapshot: Dict[int, Dict[str, List[float]]] = {}
        for frame in range(new_start, new_end + 1):
            cmds.currentTime(retime_source_time(frame, new_start, factor))
            snapshot[frame] = {
                node: [cmds.getAttr("{}.{}".format(node, a)) for a in attrs]
                for node, attrs in channels.items()
            }

        # Phase 2: replace the curves with the snapshot.
        for node, attrs in channels.items():
            cmds.cutKey(node, attribute=attrs, time=(start, end), clear=True)
            for frame in range(new_start, new_end + 1):
                for attribute, value in zip(attrs, snapshot[frame][node]):
                    cmds.setAttr("{}.{}".format(node, attribute), value)
                cmds.setKeyframe(node, attribute=attrs, time=frame)
    finally:
        cmds.currentTime(original_time)
    return new_start, new_end


# ---------------------------------------------------------------------------
# Mirror
# ---------------------------------------------------------------------------


def keyed_attributes(node: str) -> List[str]:
    cmds = _cmds()
    found = []
    for attribute in _KEYABLE:
        count = cmds.keyframe(node, attribute=attribute, query=True, keyframeCount=True)
        if count:
            found.append(attribute)
    return found


def mirror_animation(
    bones: Sequence[str],
    up_index: Optional[int] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> Dict[str, str]:
    """Reflect the animation across the skeletal midline, in place.

    Every bone's world matrix is reflected as ``S @ M @ S``. Applying the
    reflection on both sides is what keeps the result a valid rotation:
    the two reflections cancel the handedness flip, so the mirrored pose
    is a real pose rather than an inside-out one.

    Matrices for the whole frame are snapshotted before anything is
    written. Writing as we read would let a bone that has already been
    mirrored feed the next one.

    Returns the bone mapping that was applied.
    """
    cmds = _cmds()

    mapping = mirror_map(bones)
    if mapping is None:
        raise ValueError(
            "skeleton is not mirrorable: a side is missing its opposite, "
            "or short names are ambiguous"
        )

    if up_index is None:
        axis = cmds.upAxis(query=True, axis=True)
        up_index = {"y": 1, "z": 2}.get(axis)
        if up_index is None:
            raise ValueError("unrecognised up axis: {}".format(axis))

    reflection = _diagonal(mirror_diagonal(up_index))

    if start is None or end is None:
        from .pose_sampler import timeline

        scene_start, scene_end = timeline()
        start = scene_start if start is None else start
        end = scene_end if end is None else end

    keyed = {bone: keyed_attributes(bone) for bone in bones}
    original_time = cmds.currentTime(query=True)
    try:
        for frame in range(int(start), int(end) + 1):
            cmds.currentTime(frame)
            snapshot = {
                bone: cmds.xform(bone, query=True, matrix=True, worldSpace=True)
                for bone in bones
            }
            for bone, partner in mapping.items():
                mirrored = _mat_mul(_mat_mul(reflection, snapshot[bone]), reflection)
                cmds.xform(partner, matrix=mirrored, worldSpace=True)
                if keyed.get(partner):
                    cmds.setKeyframe(partner, attribute=keyed[partner], time=frame)
    finally:
        cmds.currentTime(original_time)
    return mapping


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def export_fbx(path: str, root: str) -> str:
    """Export a joint hierarchy and its animation to FBX.

    Selects the root and its descendants rather than exporting the whole
    scene, so the variant file carries the rig and nothing else.

    The FBX plugin's call surface moves between Maya versions — on 2022
    ``cmds.file`` refuses the type outright with "To save FBX file type
    use FBXExport command", and the flag spellings differ. The known forms
    are tried in order and each is verified by the file appearing, which
    is cheaper than pinning one and breaking on the next version.

    Returns the name of the form that worked.
    """
    cmds = _cmds()
    cmds.select(clear=True)
    children = cmds.listRelatives(root, allDescendents=True, fullPath=True) or []
    cmds.select(children, add=True)
    cmds.select(root, add=True)
    try:
        cmds.loadPlugin("fbxmaya", quiet=True)
    except Exception:
        pass

    # A stale file from a previous run would make a failed attempt look
    # like a success.
    if os.path.isfile(path):
        os.remove(path)

    attempts = (
        ("FBXExport(f=..., s=True)", lambda: cmds.FBXExport(f=path, s=True)),
        ("FBXExport('-f', path, '-s')", lambda: cmds.FBXExport("-f", path, "-s")),
        (
            "FBXExport(file=..., selected=True)",
            lambda: cmds.FBXExport(file=path, selected=True),
        ),
        (
            "file(type='FBX', exportSelected=True)",
            lambda: cmds.file(path, type="FBX", exportSelected=True, force=True),
        ),
    )

    failures = []
    for name, call in attempts:
        try:
            call()
        except Exception as exc:
            failures.append("{}: {}".format(name, exc))
            continue
        if os.path.isfile(path):
            return name
        failures.append("{}: reported success but wrote no file".format(name))

    raise RuntimeError(
        "could not export {}; every known call form failed:\n  {}".format(
            path, "\n  ".join(failures)
        )
    )


__all__ = [
    "export_fbx",
    "keyed_attributes",
    "mirror_animation",
    "retime",
]
