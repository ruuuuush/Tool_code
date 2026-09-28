"""maya.core.preset_loader

Loader for skeleton presets.

A "preset" describes the conventions for a particular skeleton type
(UE Mannequin, Mixamo, custom, ...). Validators use presets instead of
hard-coded bone names, which is what makes the tool work for both
humanoid and custom rigs (design.md sections 0 and 7).

Presets live in ``config/skeleton_presets.json`` (zero-dependency) or
``config/skeleton_presets.yaml`` (auto-detected if PyYAML is installed).
Users can add their own preset by adding a key under ``presets``.

This module must be importable without Maya installed, because the
preset data classes are also used by the validator registry and the
manifest builder. Maya-only imports happen inside functions where needed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data classes mirroring the preset file structure
# ---------------------------------------------------------------------------


@dataclass
class NamingConvention:
    """How bones in a skeleton are named."""

    left_suffix: str = ""
    right_suffix: str = ""
    naming_regex: str = ""  # empty string == no regex check

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NamingConvention":
        return cls(
            left_suffix=data.get("left_suffix", ""),
            right_suffix=data.get("right_suffix", ""),
            naming_regex=data.get("naming_regex", ""),
        )

    def compiled_regex(self) -> Optional[re.Pattern]:
        """Return a compiled regex, or None if no regex is configured."""
        if not self.naming_regex:
            return None
        try:
            return re.compile(self.naming_regex)
        except re.error:
            # A bad regex in config should not crash the tool; treat as None
            # and let the validator report it as a warning.
            return None

    def matches(self, name: str) -> bool:
        """True if *name* satisfies the configured regex. Empty regex = pass."""
        rx = self.compiled_regex()
        if rx is None:
            return True
        return bool(rx.fullmatch(name))


@dataclass
class SkeletonPreset:
    """A full skeleton preset."""

    id: str
    display_name: str
    skeleton_type: str  # "humanoid" | "custom"
    root_bone: str = ""
    naming: NamingConvention = field(default_factory=NamingConvention)
    bone_map: Dict[str, str] = field(default_factory=dict)
    required_bones: List[str] = field(default_factory=list)

    @property
    def is_humanoid(self) -> bool:
        return self.skeleton_type == "humanoid"

    @classmethod
    def from_dict(cls, preset_id: str, data: Dict[str, Any]) -> "SkeletonPreset":
        return cls(
            id=preset_id,
            display_name=data.get("display_name", preset_id),
            skeleton_type=data.get("skeleton_type", "custom"),
            root_bone=data.get("root_bone", ""),
            naming=NamingConvention.from_dict(data.get("naming", {})),
            bone_map=dict(data.get("bone_map", {})),
            required_bones=list(data.get("required_bones", [])),
        )


# ---------------------------------------------------------------------------
# Preset registry / loader
# ---------------------------------------------------------------------------

# Default preset ids shipped with the tool, in display order.
DEFAULT_PRESET_IDS = ("ue_mannequin", "mixamo", "custom")

# Filenames searched in order. YAML is preferred when present (more readable
# for hand-edited config) but JSON is always supported with no dependency.
_PRESET_FILES = (
    "skeleton_presets.yaml",
    "skeleton_presets.yml",
    "skeleton_presets.json",
)


def default_config_dir() -> str:
    """Return the default config directory (next to the mtu_maya/ package).

    Resolves to ``<repo>/config`` regardless of CWD, so validators work
    whether launched from Maya's Script Editor or a shell.
    """
    # mtu_maya/core/preset_loader.py -> mtu_maya/core -> maya -> repo root
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(here))
    return os.path.join(repo_root, "config")


def _parse_file(path: str) -> Dict[str, Any]:
    """Parse a JSON or YAML config file into a dict."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                f"Found YAML preset file {path!r} but PyYAML is not installed. "
                "Install PyYAML or use the .json preset file instead."
            ) from exc
        with open(path, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp)
    else:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError(f"Preset file {path!r} must contain a mapping at the top level")
    return data


class PresetRegistry:
    """In-memory collection of loaded presets."""

    def __init__(self) -> None:
        self._presets: Dict[str, SkeletonPreset] = {}

    # -- mutation -----------------------------------------------------------

    def register(self, preset: SkeletonPreset) -> None:
        if not preset.id:
            raise ValueError("Preset id cannot be empty")
        self._presets[preset.id] = preset

    def clear(self) -> None:
        self._presets.clear()

    # -- access -------------------------------------------------------------

    def get(self, preset_id: str) -> Optional[SkeletonPreset]:
        return self._presets.get(preset_id)

    def require(self, preset_id: str) -> SkeletonPreset:
        """Like get(), but raises KeyError with a helpful message."""
        preset = self._presets.get(preset_id)
        if preset is None:
            available = ", ".join(sorted(self._presets)) or "<none>"
            raise KeyError(
                f"Unknown skeleton preset: {preset_id!r}. Available: {available}"
            )
        return preset

    def all(self) -> List[SkeletonPreset]:
        """All presets, ordered so defaults come first in their declared order."""
        ordered: List[SkeletonPreset] = []
        # Defaults first, in the canonical order.
        for pid in DEFAULT_PRESET_IDS:
            p = self._presets.get(pid)
            if p is not None:
                ordered.append(p)
        # Then any extras, sorted by id for stable order.
        for pid in sorted(self._presets):
            if pid not in DEFAULT_PRESET_IDS:
                ordered.append(self._presets[pid])
        return ordered

    def ids(self) -> List[str]:
        return [p.id for p in self.all()]

    def display_names(self) -> Dict[str, str]:
        return {p.id: p.display_name for p in self.all()}

    def __len__(self) -> int:
        return len(self._presets)

    def __contains__(self, preset_id: object) -> bool:
        return preset_id in self._presets


# ---------------------------------------------------------------------------
# Module-level loader
# ---------------------------------------------------------------------------

def load_presets(config_dir: Optional[str] = None) -> PresetRegistry:
    """Load presets from *config_dir* (or the default config dir).

    Searches for skeleton_presets.{yaml,yml,json} in that order. If none
    exists, returns an empty registry rather than raising — callers may
    want to operate purely with the in-memory "custom" preset.
    """
    cfg_dir = config_dir or default_config_dir()
    registry = PresetRegistry()

    path: Optional[str] = None
    for name in _PRESET_FILES:
        candidate = os.path.join(cfg_dir, name)
        if os.path.isfile(candidate):
            path = candidate
            break

    if path is None:
        return registry

    data = _parse_file(path)
    presets_data = data.get("presets", {})
    if not isinstance(presets_data, dict):
        raise ValueError(
            f"'presets' in {path!r} must be a mapping of id -> preset"
        )

    for preset_id, preset_data in presets_data.items():
        if not isinstance(preset_data, dict):
            raise ValueError(f"Preset {preset_id!r} must be a mapping")
        registry.register(SkeletonPreset.from_dict(preset_id, preset_data))

    return registry


# Cached default registry, populated on first access. Callers should use
# get_default_registry() rather than holding their own copy so config
# changes can be picked up by calling reload_default_registry().
_default_registry: Optional[PresetRegistry] = None


def get_default_registry() -> PresetRegistry:
    """Return the cached default registry, loading it on first call."""
    global _default_registry
    if _default_registry is None:
        _default_registry = load_presets()
    return _default_registry


def reload_default_registry() -> PresetRegistry:
    """Force a reload of the default registry from disk."""
    global _default_registry
    _default_registry = load_presets()
    return _default_registry


__all__ = [
    "NamingConvention",
    "SkeletonPreset",
    "PresetRegistry",
    "DEFAULT_PRESET_IDS",
    "default_config_dir",
    "load_presets",
    "get_default_registry",
    "reload_default_registry",
]
