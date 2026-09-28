"""bridge

The decoupling layer between the Maya exporter and the UE importer.

The manifest is the single source of truth for the export/import convention.
Nothing about frame rate, axis, clip ranges or destination paths should be
hard-coded into either end of the pipeline — it all lives in the manifest.

Public API:
    Manifest            - top-level manifest data class
    read_manifest       - load a manifest from disk
    write_manifest      - serialize a manifest to disk
    load_or_create      - convenience: load if exists, else new
    SCHEMA_VERSION      - the manifest schema version string
"""

from .schema import (
    SCHEMA_VERSION,
    Manifest,
    Source,
    Convention,
    UEDestination,
    Clip,
    CheckResultEntry,
    ValidationSummary,
    ImportResult,
)
from .manifest import read_manifest, write_manifest, load_or_create

__all__ = [
    "SCHEMA_VERSION",
    "Manifest",
    "Source",
    "Convention",
    "UEDestination",
    "Clip",
    "CheckResultEntry",
    "ValidationSummary",
    "ImportResult",
    "read_manifest",
    "write_manifest",
    "load_or_create",
]
