from __future__ import annotations

import math


def verify_animation(u, asset_path, skeleton_path, clip, frame_rate, required_bones):
    expected = {
        "skeleton": skeleton_path.rsplit(".", 1)[0],
        "frames": clip.end - clip.start,
        "keys": clip.end - clip.start + 1,
        "frame_rate": frame_rate,
        "duration": (clip.end - clip.start) / float(frame_rate),
        "root_motion": clip.root_motion,
        "required_bones": list(required_bones),
    }
    actual = {}
    errors = []
    try:
        asset = u.load_asset(asset_path)
        if not isinstance(asset, u.AnimSequence):
            raise ValueError("目标不是 AnimSequence")
        skeleton = asset.get_editor_property("skeleton")
        if not isinstance(skeleton, u.Skeleton):
            raise ValueError("动画未关联有效 Skeleton")
        actual["skeleton"] = u.EditorAssetLibrary.get_path_name_for_loaded_asset(skeleton).rsplit(".", 1)[0]
        library = u.AnimationLibrary
        actual["frames"] = library.get_num_frames(asset)
        actual["keys"] = library.get_num_keys(asset)
        actual["duration"] = library.get_sequence_length(asset)
        rate = asset.get_data_model().get_frame_rate()
        actual["frame_rate"] = rate.numerator / float(rate.denominator)
        actual["root_motion"] = bool(asset.get_editor_property("enable_root_motion"))
        actual["tracks"] = sorted(str(name) for name in library.get_animation_track_names(asset))
        for key in ("skeleton", "frames", "keys", "root_motion"):
            if actual[key] != expected[key]:
                errors.append(f"{key}: expected {expected[key]!r}, actual {actual[key]!r}")
        for key in ("frame_rate", "duration"):
            if not math.isfinite(actual[key]) or not math.isclose(actual[key], expected[key], rel_tol=1e-5, abs_tol=1e-5):
                errors.append(f"{key}: expected {expected[key]}, actual {actual[key]}")
        missing = sorted(set(required_bones) - set(actual["tracks"]))
        if missing:
            errors.append("missing bone tracks: " + ", ".join(missing))
    except Exception as exc:
        errors.append(f"验收失败或 API 不可用：{type(exc).__name__}: {exc}")
    return {"asset_path": asset_path, "expected": expected, "actual": actual, "errors": errors, "passed": not errors}
