"""maya.core.config

Centralised access to all configuration: skeleton presets, FBX export
preset, and default pipeline settings. Keeping config access in one
module means the rest of the tool never hard-codes paths or values.

All loaders here are pure-Python (no Maya imports), so they can be
unit-tested in a plain interpreter.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .preset_loader import (
    PresetRegistry,
    default_config_dir,
    get_default_registry,
    load_presets,
)


# ---------------------------------------------------------------------------
# Default pipeline settings (default_settings.json)
# ---------------------------------------------------------------------------

@dataclass
class PipelineSettings:
    """User-tunable defaults surfaced in the UI.

    These are *defaults* — the UI can override them per export and the
    final values land in the manifest.
    """

    frame_rate: int = 30
    fbx_export_dir: str = "./exports"
    ue_content_root: str = "/Game/Animations"
    overwrite_policy: str = "rename"  # overwrite | skip | rename
    default_preset_id: str = "ue_mannequin"
    write_markdown_report: bool = True
    log_file_name: str = "pipeline.log"
    auto_push_after_export: bool = True
    # 关键帧抽稀档位：off（默认）/ low / medium / high。
    key_thinning: str = "off"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineSettings":
        if not isinstance(data, dict):
            raise ValueError("Pipeline settings must be a mapping")
        raw_frame_rate = data.get("frame_rate", 30)
        if isinstance(raw_frame_rate, bool) or (isinstance(raw_frame_rate, float) and not raw_frame_rate.is_integer()):
            raise ValueError("frame_rate must be a positive integer")
        if isinstance(raw_frame_rate, str) and not raw_frame_rate.strip().isdigit():
            raise ValueError("frame_rate must be a positive integer")
        frame_rate = int(raw_frame_rate)
        if frame_rate <= 0:
            raise ValueError("frame_rate must be > 0")
        overwrite_policy = data.get("overwrite_policy", "rename")
        if overwrite_policy not in ("overwrite", "skip", "rename"):
            raise ValueError("overwrite_policy must be 'overwrite', 'skip', or 'rename'")
        key_thinning = data.get("key_thinning", "off")
        if key_thinning not in ("off", "low", "medium", "high"):
            raise ValueError("key_thinning must be 'off', 'low', 'medium', or 'high'")
        ue_content_root = data.get("ue_content_root", "/Game/Animations")
        if not isinstance(ue_content_root, str) or not ue_content_root.startswith("/Game"):
            raise ValueError("ue_content_root must start with '/Game'")
        return cls(
            frame_rate=frame_rate,
            fbx_export_dir=data.get("fbx_export_dir", "./exports"),
            ue_content_root=ue_content_root,
            overwrite_policy=overwrite_policy,
            default_preset_id=data.get("default_preset_id", "ue_mannequin"),
            write_markdown_report=bool(data.get("write_markdown_report", True)),
            log_file_name=data.get("log_file_name", "pipeline.log"),
            auto_push_after_export=bool(data.get("auto_push_after_export", True)),
            key_thinning=key_thinning,
        )

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


# ---------------------------------------------------------------------------
# FBX export preset (fbx_export_preset.json)
# ---------------------------------------------------------------------------

@dataclass
class FBXExportPreset:
    """Parameters handed to Maya's FBX export plugin.

    Values follow industry-standard practice for animation delivery to UE.
    Tweaks go in the config file, not in code.
    """

    # Animation baking
    bake_animation: bool = True
    bake_resample_all: bool = True
    bake_step: float = 1.0  # one sample per frame

    # Scene conversion — source axis/unit are preserved and recorded in manifest.
    convert_axis: bool = False
    convert_unit: bool = False
    up_axis: str = "y"

    # What to include.
    # NOTE: animation_only is kept for config compatibility but is NOT pushed to
    # the FBX plugin — see apply_to_maya(). Scope is controlled by selection.
    animation_only: bool = True
    include_constraints: bool = True
    include_deformers: bool = False
    include_mesh: bool = False
    include_materials: bool = False

    # Misc
    triangulate: bool = False          # animation export does not need triangulation
    smooth_normals: bool = False
    remove_unused_normals: bool = False
    fbx_version: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FBXExportPreset":
        if not isinstance(data, dict):
            raise ValueError("FBX export preset must be a mapping")
        if bool(data.get("convert_axis", False)) or bool(data.get("convert_unit", False)):
            raise ValueError("convert_axis and convert_unit are locked to false")
        up_axis = str(data.get("up_axis", "y")).lower()
        if up_axis not in ("y", "z"):
            raise ValueError("up_axis must be 'y' or 'z'")
        raw_bake_step = data.get("bake_step", 1.0)
        if isinstance(raw_bake_step, bool):
            raise ValueError("bake_step must be > 0")
        bake_step = float(raw_bake_step)
        if bake_step <= 0:
            raise ValueError("bake_step must be > 0")
        if not bake_step.is_integer():
            raise ValueError("bake_step must be a whole number")
        fbx_version = data.get("fbx_version", "")
        if fbx_version is None:
            fbx_version = ""
        if not isinstance(fbx_version, str):
            raise ValueError("fbx_version must be a string")
        return cls(
            bake_animation=bool(data.get("bake_animation", True)),
            bake_resample_all=bool(data.get("bake_resample_all", True)),
            bake_step=bake_step,
            convert_axis=False,
            convert_unit=False,
            up_axis=up_axis,
            animation_only=bool(data.get("animation_only", True)),
            include_constraints=bool(data.get("include_constraints", True)),
            include_deformers=bool(data.get("include_deformers", False)),
            include_mesh=bool(data.get("include_mesh", False)),
            include_materials=bool(data.get("include_materials", False)),
            triangulate=bool(data.get("triangulate", False)),
            smooth_normals=bool(data.get("smooth_normals", False)),
            remove_unused_normals=bool(data.get("remove_unused_normals", False)),
            fbx_version=fbx_version,
        )

    def apply_to_maya(self) -> None:
        """Push these values into Maya's FBX plugin properties."""
        import maya.mel as mel

        def set_option(command: str, value: str) -> None:
            try:
                mel.eval(f'{command} -v {value}')
            except Exception as exc:
                raise RuntimeError(
                    f"could not set FBX export option {command} to {value!r}: {exc}"
                ) from exc

        # Start from a known state. The FBX plugin keeps its settings for the
        # whole Maya session, so without this an option left over from a manual
        # export (or a previous run) silently changes the result.
        try:
            mel.eval("FBXResetExport")
        except Exception as exc:
            raise RuntimeError(f"could not reset FBX export settings: {exc}") from exc

        # NOTE: FBXExportAnimationOnly is deliberately NOT set here.
        # Turning it on strips the joint hierarchy from the file, producing an
        # FBX that UE reports as "no mesh or animation track found". Animation
        # is instead limited by baking over the clip range and exporting only
        # the selected skeleton hierarchy.
        set_option("FBXExportBakeComplexAnimation", "true" if self.bake_animation else "false")
        set_option("FBXExportBakeResampleAnimation", "true" if self.bake_resample_all else "false")
        set_option("FBXExportBakeComplexStep", str(max(1, int(self.bake_step))))
        set_option("FBXExportConstraints", "true" if self.include_constraints else "false")
        set_option("FBXExportSkins", "true" if self.include_deformers else "false")
        set_option("FBXExportShapes", "true" if self.include_deformers else "false")
        set_option("FBXExportTriangulate", "true" if self.triangulate else "false")
        set_option("FBXExportSmoothMesh", "true" if self.smooth_normals else "false")
        if self.fbx_version:
            set_option("FBXExportFileVersion", self.fbx_version)


# ---------------------------------------------------------------------------
# Unified config loader
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path!r} must contain a mapping")
    return data


def _find_config(name: str, config_dir: Optional[str] = None) -> Optional[str]:
    cfg_dir = config_dir or default_config_dir()
    candidate = os.path.join(cfg_dir, name)
    return candidate if os.path.isfile(candidate) else None


def load_pipeline_settings(config_dir: Optional[str] = None) -> PipelineSettings:
    """Load default_settings.json, or sensible built-in defaults if missing."""
    path = _find_config("default_settings.json", config_dir)
    if path is None:
        return PipelineSettings()
    return PipelineSettings.from_dict(_load_json(path))


def load_fbx_preset(config_dir: Optional[str] = None) -> FBXExportPreset:
    """Load fbx_export_preset.json, or built-in defaults if missing."""
    path = _find_config("fbx_export_preset.json", config_dir)
    if path is None:
        return FBXExportPreset()
    return FBXExportPreset.from_dict(_load_json(path))


def load_all_config(config_dir: Optional[str] = None) -> "ConfigBundle":
    """Load presets + settings + FBX preset in one call."""
    return ConfigBundle(
        presets=load_presets(config_dir),
        settings=load_pipeline_settings(config_dir),
        fbx_preset=load_fbx_preset(config_dir),
    )


@dataclass
class ConfigBundle:
    """All config needed to run the pipeline, bundled together."""

    presets: PresetRegistry
    settings: PipelineSettings
    fbx_preset: FBXExportPreset


__all__ = [
    "PipelineSettings",
    "FBXExportPreset",
    "ConfigBundle",
    "load_pipeline_settings",
    "load_fbx_preset",
    "load_all_config",
    "get_default_registry",
    "load_presets",
]
