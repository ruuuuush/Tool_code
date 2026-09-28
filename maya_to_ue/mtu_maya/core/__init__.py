"""maya.core

Core utilities shared by the Maya-side validators and exporter:

    maya_utils   - lazy maya.cmds wrappers (scene/selection/joint/fbx helpers)
    preset_loader - skeleton preset data classes and loader
    config       - unified config access (presets + settings + FBX preset)

These modules are importable without Maya installed; Maya-only imports
happen inside functions, so the data classes and config loaders can be
unit-tested in a plain interpreter.
"""

from .preset_loader import (
    NamingConvention,
    SkeletonPreset,
    PresetRegistry,
    DEFAULT_PRESET_IDS,
    default_config_dir,
    load_presets,
    get_default_registry,
    reload_default_registry,
)
from .config import (
    PipelineSettings,
    FBXExportPreset,
    ConfigBundle,
    load_pipeline_settings,
    load_fbx_preset,
    load_all_config,
)

__all__ = [
    # preset_loader
    "NamingConvention",
    "SkeletonPreset",
    "PresetRegistry",
    "DEFAULT_PRESET_IDS",
    "default_config_dir",
    "load_presets",
    "get_default_registry",
    "reload_default_registry",
    # config
    "PipelineSettings",
    "FBXExportPreset",
    "ConfigBundle",
    "load_pipeline_settings",
    "load_fbx_preset",
    "load_all_config",
]
