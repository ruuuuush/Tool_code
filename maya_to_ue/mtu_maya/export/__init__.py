"""maya.export

FBX export + manifest/report writing.

Public API:
    ExportRequest       - what the UI hands the exporter
    ExportResult        - what export_animation() returns
    export_animation    - the full pipeline: validate -> bake -> export
    write_all_artifacts - persist manifest + log + report

The exporter is the orchestrator. It builds a CheckContext from the
live scene, runs every registered validator, and only writes the FBX
when validation passes (no Error-level failures). The clip ranges are
NOT cut here — UE slices them later via the manifest (single-FBX-multi-
clip strategy, design.md section 0).
"""

from .fbx_exporter import (
    ExportRequest,
    ExportResult,
    build_context,
    compute_export_range,
    export_animation,
)
from .manifest_writer import (
    manifest_path_for,
    log_path_for,
    report_path_for,
    write_export_manifest,
    append_log,
    write_markdown_report,
    write_all_artifacts,
)

__all__ = [
    "ExportRequest",
    "ExportResult",
    "build_context",
    "compute_export_range",
    "export_animation",
    "manifest_path_for",
    "log_path_for",
    "report_path_for",
    "write_export_manifest",
    "append_log",
    "write_markdown_report",
    "write_all_artifacts",
]
