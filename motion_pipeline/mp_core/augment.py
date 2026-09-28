"""mp_core.augment

The decision layer for Step 3 augmentation: which bone mirrors onto
which, and what a time-warped frame range becomes.

Production happens in Maya (``mp_maya.augment``) because the deliverable
is animation curves, not numbers. Everything in here is the part that can
be decided — and tested — without Maya.

Scope note — this narrows docs/01 §6, deliberately:

"Database pruning" is **not** here. Decimating keys degrades the clip,
and Motion Matching pruning is a database indexing setting, not a clip
edit; UE's PoseSearch already exposes it per-animation when the database
is built (Step 5). The Maya->UE tool separately covers key thinning for
FBX size, which is a third, unrelated concern. Implementing pruning here
would have produced the wrong artefact.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

# Side spellings in the wild. Mixamo writes "Left"/"Right", UE writes
# suffixes, some rigs use dot-separated tokens.
_PREFIX_PAIRS = (("Left", "Right"), ("left", "right"), ("LEFT", "RIGHT"))
_SUFFIX_PAIRS = (("_l", "_r"), (".l", ".r"), ("-l", "-r"))


def short_name(node: str) -> str:
    """Bone name without DAG path or namespace."""
    return node.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


def opposite_name(name: str) -> Optional[str]:
    """The same bone on the other side, or None if the name carries no side.

    Returning None is the signal for "centre bone" — hips, spine, head —
    which a mirror reflects onto itself.

    Both directions are handled. Mapping only left onto right would leave
    every right-side bone looking like a centre bone, and the involution
    check in ``mirror_map`` would then reject the whole skeleton.
    """
    for left, right in _PREFIX_PAIRS:
        if left in name:
            return name.replace(left, right)
        if right in name:
            return name.replace(right, left)
    for left, right in _SUFFIX_PAIRS:
        if name.endswith(left):
            return name[: -len(left)] + right
        if name.endswith(right):
            return name[: -len(right)] + left
    return None


def mirror_map(bones: Sequence[str]) -> Optional[Dict[str, str]]:
    """Map each bone to its mirror counterpart, or None if the skeleton
    cannot be mirrored as a whole.

    All-or-nothing on purpose. Mirroring half a skeleton yields a clip
    that looks plausible in a still and is wrong in motion, which is a
    worse outcome than refusing to mirror it.

    Centre bones map to themselves: they still need reflecting, they just
    do not swap partners.
    """
    by_short: Dict[str, str] = {}
    for bone in bones:
        key = short_name(bone)
        if key in by_short:
            return None  # ambiguous short name (two namespaces?)
        by_short[key] = bone

    mapping: Dict[str, str] = {}
    for bone in bones:
        partner = opposite_name(short_name(bone))
        if partner is None:
            mapping[bone] = bone
            continue
        counterpart = by_short.get(partner)
        if counterpart is None:
            return None  # a side exists without its opposite
        mapping[bone] = counterpart

    # A mirror is an involution: swapping twice must return the original.
    # If it does not, the naming is not actually symmetric.
    for bone, counterpart in mapping.items():
        if mapping.get(counterpart) != bone:
            return None
    return mapping


def is_mirrorable(bones: Sequence[str]) -> bool:
    return mirror_map(bones) is not None


def lateral_index(up_index: int) -> int:
    """Which axis separates left from right, given the up axis."""
    return up_index - 1


def mirror_diagonal(up_index: int) -> Tuple[float, float, float]:
    """Diagonal of the reflection matrix across the skeletal midline.

    Negating the lateral axis is what turns a left-foot-forward walk into
    a right-foot-forward one. Reflect twice and the handedness cancels,
    which is why a pose can be mirrored by ``S @ M @ S`` and stay a valid
    rotation.
    """
    lateral = lateral_index(up_index)
    return tuple(-1.0 if i == lateral else 1.0 for i in range(3))


def warped_range(start: int, end: int, factor: float) -> Tuple[int, int]:
    """New inclusive frame range after retiming about ``start``.

    ``factor > 1`` makes the clip take longer (slower motion); the anchor
    frame stays put so the clip still begins where it began.
    """
    if factor <= 0:
        raise ValueError("factor must be > 0, got {}".format(factor))
    if end < start:
        raise ValueError("end {} is before start {}".format(end, start))
    return start, start + int(round((end - start) * factor))


def warped_frame_count(count: int, factor: float) -> int:
    """How many frames a ``count``-frame clip becomes at ``factor``."""
    return warped_range(0, count - 1, factor)[1] + 1


def retime_source_time(frame: int, start: int, factor: float) -> float:
    """The source time a retimed output frame samples.

    Retiming is a resample: the new frame grid lands between the old keys,
    so the source has to be evaluated at a fractional time. That is the
    whole point of doing it this way rather than scaling key times — see
    ``mp_maya.augment.retime``.
    """
    if factor <= 0:
        raise ValueError("factor must be > 0, got {}".format(factor))
    return start + (frame - start) / factor


__all__ = [
    "is_mirrorable",
    "lateral_index",
    "mirror_diagonal",
    "mirror_map",
    "opposite_name",
    "retime_source_time",
    "short_name",
    "warped_frame_count",
    "warped_range",
]
