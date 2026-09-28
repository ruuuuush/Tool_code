"""mp_maya

Maya-side adapters for the Motion Pipeline.

Samples world-space bone data out of the open scene and hands it to
``mp_core``. Depends on ``mp_core``; ``mp_core`` never depends on this.
"""

from .augment import (
    export_fbx,
    keyed_attributes,
    mirror_animation,
    retime,
)
from .pose_sampler import (
    FOOT_PATTERNS,
    animation_range,
    check_environment,
    classify_foot_bone,
    classify_role,
    classify_side,
    ensure_maya_ready,
    estimate_scale_ref,
    find_feet,
    find_foot_bones,
    find_root_joint,
    import_fbx,
    list_joints,
    open_new_scene,
    sample_clip,
    scene_fps,
    scene_up_index,
    set_scene_fps,
    timeline,
    world_position,
)

__all__ = [
    "FOOT_PATTERNS",
    "animation_range",
    "check_environment",
    "classify_foot_bone",
    "classify_role",
    "classify_side",
    "ensure_maya_ready",
    "estimate_scale_ref",
    "export_fbx",
    "find_feet",
    "find_foot_bones",
    "find_root_joint",
    "import_fbx",
    "keyed_attributes",
    "list_joints",
    "mirror_animation",
    "open_new_scene",
    "retime",
    "sample_clip",
    "scene_fps",
    "scene_up_index",
    "set_scene_fps",
    "timeline",
    "world_position",
]
