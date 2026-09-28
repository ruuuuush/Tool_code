"""Diagnostic: why does mirror + retime measure ~2x the slide of retime alone?

Builds the same variant three ways and prints per-bone numbers:

    A  retime only              (the healthy control, 0.0435)
    B  mirror, then retime      (the suspect, 0.0877)
    C  retime, then mirror      (order swapped)

If B is bad and C matches A (sides swapped), the problem is retiming the
*re-keyed* mirrored curves. If B and C are both bad, mirroring retimed
data is the problem. Run under mayapy; not part of the test suite.
"""

import sys

sys.path.insert(0, "D:/tool_code/motion_pipeline")

import mp_core  # noqa: E402
import mp_maya  # noqa: E402

SOURCE = "D:/tool_code/Standard Walk.fbx"
FACTOR = 0.85


def build(label, order):
    mp_maya.ensure_maya_ready()
    mp_maya.open_new_scene()
    mp_maya.import_fbx(SOURCE, source_fps=30)
    span = mp_maya.animation_range()
    joints = mp_maya.list_joints()

    for step in order:
        if step == "mirror":
            current = mp_maya.animation_range() or span
            mp_maya.mirror_animation(joints, start=current[0], end=current[1])
        elif step == "retime":
            current = mp_maya.animation_range() or span
            mp_maya.retime(joints, current[0], current[1], FACTOR)

    samples = mp_maya.sample_clip(
        label, mp_maya.find_root_joint(), mp_maya.find_foot_bones()
    )
    scan = mp_core.analyse_clips([samples])
    print("--- {} ---".format(label))
    for foot in scan.clips[0].feet:
        print(
            "{:<28} {:<8} speed={:.4f}  max={:.4f}  contact={:.1%}".format(
                foot.foot.rsplit("|", 1)[-1].rsplit(":", 1)[-1],
                foot.role,
                foot.slide_speed_norm,
                foot.slide_max_norm,
                foot.contact_ratio,
            )
        )


if __name__ == "__main__":
    build("A_retime_only", ["retime"])
    build("B_mirror_then_retime", ["mirror", "retime"])
    build("C_retime_then_mirror", ["retime", "mirror"])
