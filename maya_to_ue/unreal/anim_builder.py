"""unreal.anim_builder

Optional post-import helpers for the UE side.

After import_manifest() has produced one AnimSequence per clip, this
module offers convenience operations that are commonly wanted next:

    - Create a Content Browser folder structure
    - Set metadata on imported clips
    - Group clips under a single Animation Set asset (v2)

These are intentionally separate from importer.py so the core import
path stays focused. All UE-only imports are lazy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from bridge.manifest import read_manifest


@dataclass
class BuildReport:
    clips_tagged: List[str]
    errors: List[str]


def tag_clips_from_manifest(manifest_path: str) -> BuildReport:
    """Set AnimSequence metadata (rate, root motion flag) per the manifest.

    This is a re-sync helper: if the FBX import reset something, this
    re-applies the manifest's intent.
    """
    manifest = read_manifest(manifest_path)
    report = BuildReport(clips_tagged=[], errors=[])

    try:
        u = _unreal()
    except ImportError as exc:
        report.errors.append(str(exc))
        return report

    from .importer import clip_asset_path, _set_root_motion

    for clip in manifest.clips:
        path = clip_asset_path(manifest.ue_destination, clip)
        try:
            asset = u.load_asset(path)
            if asset is None:
                report.errors.append(f"not found: {path}")
                continue
            _set_root_motion(path, clip.root_motion)
            if not u.EditorAssetLibrary.save_asset(path):
                raise RuntimeError(f"could not save asset: {path}")
            report.clips_tagged.append(clip.name)
        except Exception as exc:
            report.errors.append(f"{clip.name}: {type(exc).__name__}: {exc}")
    return report


def _unreal():
    try:
        import unreal  # type: ignore
        return unreal
    except ImportError as exc:
        raise ImportError(
            "The 'unreal' module is only available inside an Unreal Editor session."
        ) from exc


def list_expected_asset_paths(manifest_path: str) -> List[str]:
    """Pure helper: list every asset path the importer should produce."""
    manifest = read_manifest(manifest_path)
    from .importer import clip_asset_path, skeleton_asset_path
    paths = [skeleton_asset_path(manifest.ue_destination, manifest.source.maya_scene)]
    paths.extend(clip_asset_path(manifest.ue_destination, c) for c in manifest.clips)
    return paths


__all__ = ["BuildReport", "tag_clips_from_manifest", "list_expected_asset_paths"]
