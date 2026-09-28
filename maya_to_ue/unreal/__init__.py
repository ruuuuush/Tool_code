"""unreal

UE-side of the Maya->UE animation pipeline.

Reads the manifest written by the Maya exporter and imports one
AnimSequence per clip, using each clip's native FBX frame range.

Usage from UE's Output Log (Python) or an Editor Utility:
    from unreal import import_manifest
    outcome = import_manifest("D:/exports/hero_manifest.json")
    print(outcome.to_result_dict())

The 'unreal' module is imported lazily inside the functions that need
it, so all path/range/policy logic here can be unit-tested in plain
Python without UE installed.
"""

from .importer import (
    ClipImportOutcome,
    ImportOutcome,
    unreal_path_join,
    clip_asset_path,
    skeleton_asset_path,
    resolve_overwrite_name,
    frame_range_to_seconds,
    import_manifest,
    check_environment,
    ue_version,
    interchange_fbx_enabled,
    disable_interchange_fbx,
    skeleton_import_settings,
    default_mesh_asset_name,
    reveal_assets,
)
from .anim_builder import (
    BuildReport,
    tag_clips_from_manifest,
    list_expected_asset_paths,
)

__all__ = [
    # importer
    "ClipImportOutcome",
    "ImportOutcome",
    "unreal_path_join",
    "clip_asset_path",
    "skeleton_asset_path",
    "resolve_overwrite_name",
    "frame_range_to_seconds",
    "import_manifest",
    "check_environment",
    "ue_version",
    "interchange_fbx_enabled",
    "disable_interchange_fbx",
    "skeleton_import_settings",
    "default_mesh_asset_name",
    "reveal_assets",
    # anim_builder
    "BuildReport",
    "tag_clips_from_manifest",
    "list_expected_asset_paths",
]
