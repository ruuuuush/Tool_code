"""bridge.manifest

Read/write API for the pipeline manifest.

Keeps all JSON I/O in one place so neither the Maya exporter nor the UE
importer has to know about file encoding or schema details.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .schema import (
    SCHEMA_VERSION,
    Manifest,
)

# Default pretty-print settings for the on-disk JSON.
# Indent for human-readability (the manifest is a portfolio artifact, it
# should be openable in a text editor and look clean).
_JSON_INDENT = 2
_JSON_ENSURE_ASCII = False


def write_manifest(manifest: Manifest, path: str) -> str:
    """Serialize *manifest* to *path* as UTF-8 JSON.

    Validates before writing so we never produce an invalid manifest on disk.

    Returns:
        The absolute path written.
    """
    manifest.validate()

    abs_path = os.path.abspath(path)
    parent = os.path.dirname(abs_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    data = manifest.to_dict()
    with open(abs_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=_JSON_INDENT, ensure_ascii=_JSON_ENSURE_ASCII)
        fp.write("\n")

    return abs_path


def read_manifest(path: str) -> Manifest:
    """Read and parse a manifest JSON file.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the JSON is malformed or the schema is invalid.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Manifest not found: {path}")

    with open(path, "r", encoding="utf-8") as fp:
        try:
            data: Dict[str, Any] = json.load(fp)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Manifest root in {path} must be a JSON object")
    try:
        manifest = Manifest.from_dict(data)
        manifest.validate()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid manifest in {path}: {exc}") from exc
    return manifest


def load_or_create(path: str) -> Manifest:
    """Return the manifest at *path*, or a fresh empty one if missing."""
    if os.path.isfile(path):
        return read_manifest(path)
    return Manifest.new()


__all__ = [
    "SCHEMA_VERSION",
    "Manifest",
    "read_manifest",
    "write_manifest",
    "load_or_create",
]
