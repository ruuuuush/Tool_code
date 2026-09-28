"""unreal.importer

FBX import on the UE side, driven entirely by the manifest.

The pipeline strategy:
    - Maya exports one FBX covering the union of all clip ranges.
    - UE imports that FBX once per manifest clip using the clip's native FBX
      frame range, producing correctly bounded AnimSequence assets.

The ``unreal`` module only exists inside a UE editor session, so it is
imported lazily inside the functions that need it. Everything else
(path arithmetic, clip-range math, name policy) is pure Python and
fully unit-testable without UE.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from bridge.manifest import read_manifest
from bridge.schema import Clip, Manifest, UEDestination


# ---------------------------------------------------------------------------
# Pure helpers (testable without UE)
# ---------------------------------------------------------------------------

def unreal_path_join(*parts: str) -> str:
    """Join UE content-browser path segments with '/', normalising duplicates.

    UE package paths look like /Game/Animations/Hero/Hero_Skeleton.
    """
    cleaned = []
    for p in parts:
        if not p:
            continue
        p = p.strip()
        if not p.startswith("/") and cleaned and not cleaned[-1].endswith("/"):
            cleaned.append("/")
        # Collapse any leading slash on subsequent segments.
        if cleaned and p.startswith("/"):
            p = p[1:]
        cleaned.append(p)
    result = "".join(cleaned)
    # Collapse accidental double slashes.
    while "//" in result:
        result = result.replace("//", "/")
    return result


def clip_asset_path(destination: UEDestination, clip: Clip) -> str:
    """Return the UE asset path for a clip's AnimSequence.

    Example: /Game/Animations/Hero + clip 'walk' -> /Game/Animations/Hero/walk
    """
    return unreal_path_join(destination.content_root, clip.name)


def skeleton_asset_path(destination: UEDestination, scene_name: str = "skeleton") -> str:
    """Return configured UE Skeleton path, or a predicted fallback path.

    Animation-only import requires an existing Skeleton; callers must provide
    `destination.skeleton_path` before invoking the actual importer.
    """
    if destination.skeleton_path:
        return destination.skeleton_path
    return unreal_path_join(destination.content_root, f"{scene_name or 'skeleton'}_Skeleton")


def resolve_overwrite_name(
    clip_path: str,
    policy: str,
    exists_predicate,
) -> Tuple[str, Optional[str]]:
    """Decide the actual asset path for a clip given the overwrite policy.

    Args:
        clip_path: the desired asset path (e.g. /Game/.../walk)
        policy: "overwrite" | "skip" | "rename"
        exists_predicate: callable(path) -> bool, asking UE if it exists

    Returns:
        (final_path, action) where action is one of
        "create", "overwrite", "skip", "rename".
    """
    exists = exists_predicate(clip_path)
    if not exists:
        return clip_path, "create"

    if policy == "overwrite":
        return clip_path, "overwrite"
    if policy == "skip":
        return clip_path, "skip"
    if policy != "rename":
        raise ValueError(f"unknown overwrite policy: {policy!r}")
    # rename -> find first free suffix
    n = 1
    while True:
        candidate = f"{clip_path}_{n:02d}"
        if not exists_predicate(candidate):
            return candidate, "rename"
        n += 1
        if n > 999:
            return clip_path, "skip"  # give up safely


def frame_range_to_seconds(start: int, end: int, frame_rate: int) -> Tuple[float, float]:
    """Convert inclusive frame range to seconds at a given rate.

    UE AnimSequence slicing works in seconds. Frames are inclusive on
    both ends: clip [1..30] at 30 fps is 30 frames = 1.0s of animation.
    """
    if isinstance(frame_rate, bool) or not isinstance(frame_rate, int) or frame_rate <= 0:
        raise ValueError(f"frame_rate must be > 0, got {frame_rate}")
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or end < start:
        raise ValueError(f"invalid inclusive frame range: {start}-{end}")
    duration_frames = end - start + 1
    duration_sec = duration_frames / frame_rate
    start_sec = (start - 1) / frame_rate  # frame 1 == 0.0s start
    return start_sec, start_sec + duration_sec


# ---------------------------------------------------------------------------
# Lazy unreal accessor
# ---------------------------------------------------------------------------

def _unreal():
    """Import and return the unreal module (only available inside UE)."""
    try:
        import unreal  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "The 'unreal' module is only available inside an Unreal Editor "
            "Python session. Run this code from the UE Output Log (Python) "
            "or an Editor Utility Blueprint."
        ) from exc
    return unreal


# ---------------------------------------------------------------------------
# Import outcome
# ---------------------------------------------------------------------------

@dataclass
class ClipImportOutcome:
    clip_name: str
    asset_path: str
    action: str                      # create | overwrite | skip | rename | failed
    success: bool
    message: str = ""


@dataclass
class ImportOutcome:
    manifest_path: str
    skeleton_asset_path: str
    long_anim_path: str              # first imported clip asset path (legacy field)
    # Set when this run created the Skeleton instead of reusing an existing one.
    skeletal_mesh_path: str = ""
    skeleton_created: bool = False
    clips: List[ClipImportOutcome] = field(default_factory=list)
    succeeded: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def add(self, outcome: ClipImportOutcome):
        self.clips.append(outcome)
        # skip is its own branch even when success=True (the importer was
        # asked not to overwrite and complied). Only actual creates/overwrites/
        # renames count as "succeeded".
        if outcome.action == "skip":
            self.skipped.append(outcome.clip_name)
        elif outcome.success:
            self.succeeded.append(outcome.clip_name)
        else:
            self.failed.append(outcome.clip_name)

    def to_result_dict(self) -> dict:
        """Convert to the bridge.ImportResult shape for manifest write-back.

        Status logic:
            - failed   : any clip failed, a pipeline error occurred, or nothing was imported
        """
        if self.failed or self.errors:
            status = "failed"
        elif self.succeeded:
            status = "success"
        elif self.skipped:
            status = "partial"
        else:
            status = "failed"
        return {
            "status": status,
            "imported_clips": list(self.succeeded),
            "errors": list(self.errors) + [
                f"{c.clip_name}: {c.message}" for c in self.clips
                if not c.success and c.action != "skip"
            ],
            "skipped_clips": list(self.skipped),
            # Only meaningful on first delivery; "" tells the reader the rig
            # was reused, not created.
            "skeleton_path": self.skeleton_asset_path if self.skeleton_created else "",
            "skeletal_mesh_path": self.skeletal_mesh_path if self.skeleton_created else "",
        }


# ---------------------------------------------------------------------------
# UE-side operations
# ---------------------------------------------------------------------------

def _make_asset_tools():
    return _unreal().AssetToolsHelpers.get_asset_tools()


def _ensure_folder(path: str) -> None:
    """Create a Content Browser folder if missing (UE side)."""
    ed = _unreal().EditorAssetLibrary
    # UE expects the path WITHOUT the leading /Game but WITH the mount.
    if not ed.does_directory_exist(path):
        if not ed.make_directory(path):
            raise RuntimeError(f"could not create UE content folder: {path}")


def _asset_exists(path: str) -> bool:
    ed = _unreal().EditorAssetLibrary
    try:
        return ed.does_asset_exist(path)
    except Exception:
        return False


_INTERCHANGE_FBX_CVAR = "Interchange.FeatureFlags.Import.FBX"


def interchange_fbx_enabled() -> Optional[bool]:
    """Return True/False if the Interchange FBX flag is readable, else None."""
    try:
        u = _unreal()
        value = u.SystemLibrary.get_console_variable_int_value(_INTERCHANGE_FBX_CVAR)
        return bool(value)
    except Exception:
        return None


def disable_interchange_fbx() -> bool:
    """Route FBX imports through the legacy path for this editor session.

    Interchange ignores the FbxImportUI options this importer relies on
    (frame range, target skeleton), so animation clips would come back
    untrimmed and unbound. Returns True if the flag ended up disabled.
    """
    try:
        u = _unreal()
        u.SystemLibrary.execute_console_command(None, f"{_INTERCHANGE_FBX_CVAR} 0")
    except Exception:
        return False
    return interchange_fbx_enabled() is False


def check_environment() -> List[str]:
    """Verify the running UE build exposes every API this importer needs.

    Returns a list of human-readable problems; empty means good to go.

    UE moves fast (Interchange is progressively replacing the legacy FBX
    path), so failing here with a clear message beats a cryptic
    AttributeError halfway through an import.
    """
    problems: List[str] = []
    try:
        u = _unreal()
    except ImportError as exc:
        return [str(exc)]

    required_types = [
        "AssetImportTask",
        "FbxImportUI",
        "FbxAnimSequenceImportData",
        "FbxSkeletalMeshImportData",
        "SkeletalMesh",
        "FBXImportType",
        "FBXAnimationLengthImportType",
        "Int32Interval",
        "EditorAssetLibrary",
        "AssetToolsHelpers",
    ]
    for name in required_types:
        if not hasattr(u, name):
            problems.append(f"unreal.{name} is missing in this UE build")

    if hasattr(u, "FBXAnimationLengthImportType"):
        for member in ("FBXALIT_SET_RANGE", "FBXALIT_EXPORTED_TIME"):
            if not hasattr(u.FBXAnimationLengthImportType, member):
                problems.append(f"unreal.FBXAnimationLengthImportType.{member} is missing")

    if hasattr(u, "FBXImportType"):
        for member in ("FBXIT_ANIMATION", "FBXIT_SKELETAL_MESH"):
            if not hasattr(u.FBXImportType, member):
                problems.append(f"unreal.FBXImportType.{member} is missing")

    # Interchange intercepting FBX would silently ignore every option we set,
    # so try to switch back to the legacy path and only complain if that fails.
    if interchange_fbx_enabled() is True and not disable_interchange_fbx():
        problems.append(
            f"could not disable {_INTERCHANGE_FBX_CVAR}; this importer needs the "
            "legacy FBX path, otherwise frame-range and skeleton options are ignored. "
            f"Run this in the console manually: {_INTERCHANGE_FBX_CVAR} 0"
        )

    return problems


def ue_version() -> str:
    """Return the running engine version, or '' outside UE."""
    try:
        return str(_unreal().SystemLibrary.get_engine_version())
    except Exception:
        return ""


def skeleton_import_settings(skeleton_path: str) -> dict:
    """Read the scene-conversion settings the target Skeleton was created with.

    An AnimSequence must be imported with exactly the same axis/unit
    conversion as the SkeletalMesh that produced its Skeleton. If the two
    disagree, the animation still imports "successfully" but the character
    ends up rotated 90 degrees and/or scaled by 100 - which is impossible to
    diagnose from the import log alone.

    Returns a dict of settings, falling back to UE defaults when the source
    mesh cannot be found (e.g. the Skeleton was authored inside UE).
    """
    defaults = {
        "convert_scene": True,
        "convert_scene_unit": False,
        "force_front_x_axis": False,
        "import_uniform_scale": 1.0,
        "source": "default",
    }
    try:
        u = _unreal()
    except ImportError:
        return defaults

    skeleton = u.load_asset(skeleton_path)
    if skeleton is None:
        return defaults

    # Find a SkeletalMesh that uses this Skeleton; its import data is the
    # ground truth for how this character entered the project.
    try:
        for asset_path in u.EditorAssetLibrary.list_assets(
            skeleton_path.rsplit("/", 1)[0], recursive=False
        ):
            asset = u.load_asset(asset_path.rstrip("/").split(".")[0])
            if not isinstance(asset, u.SkeletalMesh):
                continue
            if asset.get_editor_property("skeleton") != skeleton:
                continue
            data = asset.get_editor_property("asset_import_data")
            if data is None:
                continue
            result = dict(defaults)
            for key in ("convert_scene", "convert_scene_unit", "force_front_x_axis"):
                try:
                    result[key] = bool(data.get_editor_property(key))
                except Exception:
                    pass
            try:
                result["import_uniform_scale"] = float(
                    data.get_editor_property("import_uniform_scale")
                )
            except Exception:
                pass
            result["source"] = str(asset_path)
            return result
    except Exception:
        pass

    return defaults


def _build_fbx_import_ui(
    fbx_path: str,
    skeleton_path: Optional[str],
    destination_path: str,
    frame_rate: int,
) -> "object":
    """Build an FbxImportUI configured for animation import."""
    u = _unreal()
    if not skeleton_path:
        raise ValueError("manifest.ue_destination.skeleton_path is required for animation-only import")

    skeleton = u.load_asset(skeleton_path)
    if skeleton is None:
        raise ValueError(f"could not load Skeleton asset: {skeleton_path}")

    task = u.AssetImportTask()
    task.set_editor_property("automated", True)
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", destination_path)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)

    fbx_ui = u.FbxImportUI()
    fbx_ui.set_editor_property("automated_import_should_detect_type", False)
    fbx_ui.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_ANIMATION)
    fbx_ui.set_editor_property("import_mesh", False)
    fbx_ui.set_editor_property("import_as_skeletal", True)
    fbx_ui.set_editor_property("import_animations", True)
    fbx_ui.set_editor_property("import_materials", False)
    fbx_ui.set_editor_property("import_textures", False)
    fbx_ui.set_editor_property("create_physics_asset", False)
    fbx_ui.set_editor_property("skeleton", skeleton)

    anim_data = u.FbxAnimSequenceImportData()
    anim_data.set_editor_property(
        "animation_length", u.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME
    )
    anim_data.set_editor_property("use_default_sample_rate", False)
    anim_data.set_editor_property("custom_sample_rate", frame_rate)
    anim_data.set_editor_property("import_bone_tracks", True)
    anim_data.set_editor_property("import_meshes_in_bone_hierarchy", False)

    # Match the conversion the target Skeleton was imported with, otherwise the
    # animation lands rotated and/or scaled relative to its own skeleton.
    conv = skeleton_import_settings(skeleton_path)
    anim_data.set_editor_property("convert_scene", conv["convert_scene"])
    anim_data.set_editor_property("convert_scene_unit", conv["convert_scene_unit"])
    anim_data.set_editor_property("force_front_x_axis", conv["force_front_x_axis"])
    try:
        anim_data.set_editor_property(
            "import_uniform_scale", conv["import_uniform_scale"]
        )
    except Exception:
        pass
    anim_data.set_editor_property("import_rotation", u.Rotator(0.0, 0.0, 0.0))
    fbx_ui.set_editor_property("anim_sequence_import_data", anim_data)

    task.set_editor_property("options", fbx_ui)
    return task


def _import_fbx(
    fbx_path: str,
    skeleton_path: Optional[str],
    destination_path: str,
    frame_rate: int,
) -> str:
    """Run a full-range FBX import. Kept for direct callers outside pipeline flow."""
    asset_tools = _make_asset_tools()
    task = _build_fbx_import_ui(fbx_path, skeleton_path, destination_path, frame_rate)
    asset_tools.import_asset_tasks([task])

    u = _unreal()
    imported = task.get_objects()
    for asset in imported:
        if isinstance(asset, u.AnimSequence):
            path = u.EditorAssetLibrary.get_path_name_for_loaded_asset(asset)
            return path.rsplit(".", 1)[0]
    imported_paths = task.get_editor_property("imported_object_paths") or []
    for path in imported_paths:
        package_path = str(path).rsplit(".", 1)[0]
        asset = u.load_asset(package_path)
        if isinstance(asset, u.AnimSequence):
            return package_path
    raise RuntimeError("FBX import completed without creating an AnimSequence")


def _slice_anim_sequence(
    long_path: str,
    clip: Clip,
    frame_rate: int,
    final_path: str,
    overwrite: bool,
) -> str:
    """Duplicate an AnimSequence without changing its frame range."""
    del clip, frame_rate
    u = _unreal()
    ed = u.EditorAssetLibrary
    long_asset = u.load_asset(long_path)
    if long_asset is None:
        raise RuntimeError(f"could not load long AnimSequence at {long_path}")
    if _asset_exists(final_path):
        if not overwrite:
            return final_path
        if not ed.delete_asset(final_path):
            raise RuntimeError(f"could not overwrite existing asset: {final_path}")
    duplicated = ed.duplicate_asset(long_path, final_path)
    if duplicated is None:
        raise RuntimeError(f"could not duplicate AnimSequence to {final_path}")
    if not ed.save_asset(final_path):
        raise RuntimeError(f"could not save duplicated AnimSequence: {final_path}")
    return final_path


def default_mesh_asset_name(fbx_path: str, skeleton_path: str) -> str:
    """Derive a SkeletalMesh name for a first-delivery rig import.

    Prefers the name implied by the requested skeleton path so the pair
    reads as a set (Hero_SkeletalMesh / Hero_Skeleton); falls back to the
    FBX filename.
    """
    if skeleton_path:
        leaf = skeleton_path.rsplit("/", 1)[-1]
        for suffix in ("_Skeleton", "_skeleton", "Skeleton"):
            if leaf.endswith(suffix) and len(leaf) > len(suffix):
                return leaf[: -len(suffix)].rstrip("_")
        if leaf:
            return leaf
    return os.path.splitext(os.path.basename(fbx_path))[0] or "ImportedRig"


def _import_skeletal_mesh(
    fbx_path: str,
    destination_path: str,
    asset_name: str,
    uniform_scale: float,
    overwrite: bool,
) -> Tuple[str, str]:
    """Import a rig FBX as a SkeletalMesh, creating a new Skeleton.

    Returns (skeletal_mesh_path, skeleton_path).

    This is the "first delivery" case: a rig that UE has never seen. The
    uniform scale applied here becomes the reference for every animation
    that binds to the resulting Skeleton, which is why the animation
    importer reads it back instead of asking the user to repeat it.
    """
    u = _unreal()
    _ensure_folder(destination_path)
    mesh_path = f"{destination_path}/{asset_name}"

    if _asset_exists(mesh_path):
        if not overwrite:
            raise RuntimeError(f"SkeletalMesh already exists: {mesh_path}")
        if not u.EditorAssetLibrary.delete_asset(mesh_path):
            raise RuntimeError(f"could not overwrite existing asset: {mesh_path}")

    task = u.AssetImportTask()
    task.set_editor_property("automated", True)
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", destination_path)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", overwrite)

    fbx_ui = u.FbxImportUI()
    fbx_ui.set_editor_property("automated_import_should_detect_type", False)
    fbx_ui.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_SKELETAL_MESH)
    fbx_ui.set_editor_property("import_mesh", True)
    fbx_ui.set_editor_property("import_as_skeletal", True)
    # No existing Skeleton: leaving this empty is what makes UE create one.
    fbx_ui.set_editor_property("skeleton", None)
    fbx_ui.set_editor_property("import_animations", False)
    fbx_ui.set_editor_property("import_materials", False)
    fbx_ui.set_editor_property("import_textures", False)
    fbx_ui.set_editor_property("create_physics_asset", False)

    mesh_data = u.FbxSkeletalMeshImportData()
    mesh_data.set_editor_property("import_uniform_scale", float(uniform_scale))
    mesh_data.set_editor_property("convert_scene", True)
    mesh_data.set_editor_property("convert_scene_unit", False)
    mesh_data.set_editor_property("force_front_x_axis", False)
    mesh_data.set_editor_property("import_morph_targets", True)
    mesh_data.set_editor_property("update_skeleton_reference_pose", False)
    # Prefer the FBX bind pose for the Skeleton's reference pose. Falling back
    # to frame 0 would bake whatever pose the animation happens to start on,
    # which quietly breaks retargeting and physics asset generation later.
    try:
        mesh_data.set_editor_property("use_t0_as_ref_pose", False)
    except Exception:
        pass
    fbx_ui.set_editor_property("skeletal_mesh_import_data", mesh_data)

    task.set_editor_property("options", fbx_ui)
    _make_asset_tools().import_asset_tasks([task])

    mesh_asset = None
    for asset in task.get_objects():
        if isinstance(asset, u.SkeletalMesh):
            mesh_asset = asset
            break
    if mesh_asset is None:
        for path in task.get_editor_property("imported_object_paths") or []:
            candidate = u.load_asset(str(path).rsplit(".", 1)[0])
            if isinstance(candidate, u.SkeletalMesh):
                mesh_asset = candidate
                break
    if mesh_asset is None:
        raise RuntimeError(
            f"rig import did not produce a SkeletalMesh from {fbx_path}; "
            "check that the FBX actually contains a skinned mesh"
        )

    skeleton = mesh_asset.get_editor_property("skeleton")
    if skeleton is None:
        raise RuntimeError("imported SkeletalMesh has no Skeleton")

    mesh_path = u.EditorAssetLibrary.get_path_name_for_loaded_asset(mesh_asset).rsplit(".", 1)[0]
    skeleton_path = u.EditorAssetLibrary.get_path_name_for_loaded_asset(skeleton).rsplit(".", 1)[0]

    for path in (mesh_path, skeleton_path):
        if not u.EditorAssetLibrary.save_asset(path):
            raise RuntimeError(f"could not save imported asset: {path}")

    return mesh_path, skeleton_path


def _import_clip_fbx(
    fbx_path: str,
    skeleton_path: str,
    destination_path: str,
    asset_name: str,
    clip: Clip,
    frame_rate: int,
    overwrite: bool,
) -> str:
    """Import one FBX frame range directly as an AnimSequence."""
    u = _unreal()
    if isinstance(clip.start, bool) or isinstance(clip.end, bool) or not isinstance(clip.start, int) or not isinstance(clip.end, int) or clip.start < 0 or clip.end < clip.start:
        raise ValueError(f"invalid clip range: {clip.start}-{clip.end}")
    _ensure_folder(destination_path)
    final_path = f"{destination_path}/{asset_name}"
    if _asset_exists(final_path):
        if not overwrite:
            return final_path
        if not u.EditorAssetLibrary.delete_asset(final_path):
            raise RuntimeError(f"could not overwrite existing asset: {final_path}")

    task = _build_fbx_import_ui(fbx_path, skeleton_path, destination_path, frame_rate)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("replace_existing", False)
    fbx_ui = task.get_editor_property("options")
    anim_data = fbx_ui.get_editor_property("anim_sequence_import_data")
    anim_data.set_editor_property(
        "animation_length", u.FBXAnimationLengthImportType.FBXALIT_SET_RANGE
    )
    anim_data.set_editor_property("frame_import_range", u.Int32Interval(clip.start, clip.end))

    _make_asset_tools().import_asset_tasks([task])
    imported = task.get_objects()
    for asset in imported:
        if isinstance(asset, u.AnimSequence):
            path = u.EditorAssetLibrary.get_path_name_for_loaded_asset(asset).rsplit(".", 1)[0]
            if path != final_path:
                continue
            if not u.EditorAssetLibrary.save_asset(path):
                raise RuntimeError(f"could not save imported AnimSequence: {path}")
            return path
    imported_paths = task.get_editor_property("imported_object_paths") or []
    for imported_path in imported_paths:
        package_path = str(imported_path).rsplit(".", 1)[0]
        if package_path != final_path:
            continue
        asset = u.load_asset(package_path)
        if isinstance(asset, u.AnimSequence):
            if not u.EditorAssetLibrary.save_asset(package_path):
                raise RuntimeError(f"could not save imported AnimSequence: {package_path}")
            return package_path
    if _asset_exists(final_path):
        return final_path
    raise RuntimeError(f"FBX import did not create AnimSequence: {final_path}")


def _set_root_motion(asset_path: str, enabled: bool) -> None:
    """Enable or disable root motion on an AnimSequence."""
    u = _unreal()
    asset = u.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"could not load imported AnimSequence: {asset_path}")
    asset.set_editor_property("enable_root_motion", enabled)
    if not u.EditorAssetLibrary.save_asset(asset_path):
        raise RuntimeError(f"could not save root-motion setting: {asset_path}")


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------

def import_manifest(manifest_path: str, fbx_path_override: Optional[str] = None) -> ImportOutcome:
    """Drive the full UE import from a manifest file.

    Each manifest clip is imported directly from its FBX frame range. UE 5.3
    exposes range selection on `FbxAnimSequenceImportData`, but does not expose
    reliable Python APIs to trim an already imported AnimSequence.

    Args:
        manifest_path: path to the manifest.json produced by Maya.
        fbx_path_override: use this FBX instead of manifest.fbx_path
            (useful when the FBX moved between machines).

    Returns:
        ImportOutcome with per-clip results; also written back to the
        manifest under the `result` key.
    """
    manifest = read_manifest(manifest_path)
    fbx_path = fbx_path_override or manifest.fbx_path

    outcome = ImportOutcome(
        manifest_path=manifest_path,
        skeleton_asset_path="",
        long_anim_path="",
    )

    # Fail loudly on API/feature-flag mismatches before touching any asset.
    env_problems = check_environment()
    if env_problems:
        outcome.errors.extend(env_problems)
        _write_back_result(manifest, manifest_path, outcome)
        return outcome

    if manifest.validation.status == "failed":
        outcome.errors.append("Manifest validation failed on Maya side; UE import is blocked")
        _write_back_result(manifest, manifest_path, outcome)
        return outcome

    if not os.path.isfile(fbx_path):
        outcome.errors.append(f"FBX file not found: {fbx_path}")
        _write_back_result(manifest, manifest_path, outcome)
        return outcome

    delivery = manifest.ue_destination.skeleton_delivery
    skeleton_path = manifest.ue_destination.skeleton_path

    # 1. Ensure target folders exist.
    try:
        _ensure_folder(manifest.ue_destination.content_root)
    except Exception as exc:
        outcome.errors.append(f"could not create folder {manifest.ue_destination.content_root}: {exc}")
        _write_back_result(manifest, manifest_path, outcome)
        return outcome

    # 2. Create the Skeleton when this is a first delivery for the rig.
    skeleton_missing = not skeleton_path or _unreal().load_asset(skeleton_path) is None
    if skeleton_missing and delivery.create_if_missing:
        mesh_name = delivery.mesh_asset_name or default_mesh_asset_name(
            fbx_path, skeleton_path
        )
        try:
            mesh_path, created_skeleton = _import_skeletal_mesh(
                fbx_path,
                manifest.ue_destination.content_root,
                mesh_name,
                delivery.import_uniform_scale,
                overwrite=(manifest.ue_destination.overwrite_policy == "overwrite"),
            )
        except Exception as exc:
            outcome.errors.append(
                f"could not create Skeleton from rig FBX: {type(exc).__name__}: {exc}"
            )
            _write_back_result(manifest, manifest_path, outcome)
            return outcome

        outcome.skeletal_mesh_path = mesh_path
        outcome.skeleton_created = True
        skeleton_path = created_skeleton
        # Persist the real path so later runs reuse this Skeleton.
        manifest.ue_destination.skeleton_path = created_skeleton
        skeleton_missing = False

    if not skeleton_path:
        outcome.errors.append(
            "manifest.ue_destination.skeleton_path is required, or enable "
            "skeleton_delivery.create_if_missing to build it from the rig FBX"
        )
        _write_back_result(manifest, manifest_path, outcome)
        return outcome

    outcome.skeleton_asset_path = skeleton_path

    if skeleton_missing:
        outcome.errors.append(f"Skeleton asset not found: {skeleton_path}")
        _write_back_result(manifest, manifest_path, outcome)
        return outcome

    # 3. Import each requested range directly from the FBX. This is the
    # UE-supported route for producing correctly trimmed AnimSequence assets.
    for clip in manifest.clips:
        desired_path = clip_asset_path(manifest.ue_destination, clip)
        try:
            final_path, action = resolve_overwrite_name(
                desired_path,
                manifest.ue_destination.overwrite_policy,
                _asset_exists,
            )
        except Exception as exc:
            outcome.add(ClipImportOutcome(clip.name, desired_path, "failed", False,
                                          f"name resolution failed: {exc}"))
            continue

        if action == "skip":
            outcome.add(ClipImportOutcome(clip.name, final_path, "skip", True, "skipped (policy)"))
            continue

        try:
            destination_folder = final_path.rsplit("/", 1)[0]
            asset_name = final_path.rsplit("/", 1)[-1]
            imported_path = _import_clip_fbx(
                fbx_path,
                skeleton_path,
                destination_folder,
                asset_name,
                clip,
                manifest.convention.frame_rate,
                overwrite=(action == "overwrite"),
            )
            _set_root_motion(imported_path, clip.root_motion)
            outcome.add(ClipImportOutcome(clip.name, imported_path, action, True, "ok"))
        except Exception as exc:
            outcome.add(ClipImportOutcome(clip.name, final_path, "failed", False,
                                          f"import failed: {type(exc).__name__}: {exc}"))

    _write_back_result(manifest, manifest_path, outcome)
    return outcome


def _write_back_result(manifest: Manifest, manifest_path: str, outcome: ImportOutcome) -> None:
    """Update manifest.result on disk so the Maya UI can show import status."""
    from bridge.schema import ImportResult
    data = outcome.to_result_dict()
    manifest.result = ImportResult.from_dict(data)
    try:
        from bridge.manifest import write_manifest
        write_manifest(manifest, manifest_path)
    except Exception:
        # Writing back must never mask the actual import outcome.
        pass


def reveal_assets(outcome: ImportOutcome) -> None:
    """Point the Content Browser at the assets this run produced.

    Pure sugar on top of the import report: any failure (older engine without
    the API, headless run, missing asset) is swallowed so locating assets can
    never spoil the outcome.
    """
    try:
        u = _unreal()
        paths = [
            c.asset_path for c in outcome.clips
            if c.success and c.action != "skip" and c.asset_path
        ]
        if outcome.skeleton_created:
            paths.extend(
                p for p in (outcome.skeletal_mesh_path, outcome.skeleton_asset_path) if p
            )
        if paths:
            u.EditorAssetLibrary.sync_browser_to_assets(paths)
    except Exception:
        pass


__all__ = [
    "ClipImportOutcome",
    "ImportOutcome",
    "unreal_path_join",
    "clip_asset_path",
    "skeleton_asset_path",
    "resolve_overwrite_name",
    "frame_range_to_seconds",
    "import_manifest",
    "reveal_assets",
]
