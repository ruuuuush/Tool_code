"""maya.export.manifest_writer

Persist the export outcome to disk:

    - manifest.json next to the FBX
    - pipeline.log with a timestamped run log
    - <scene>_export_report.md with a human-readable report

These three artifacts together form the "export package" that the UE
importer consumes (manifest) and that goes into a portfolio (report).
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass
from typing import Optional

from bridge.manifest import write_manifest
from mtu_maya.export.fbx_exporter import ExportResult


# ---------------------------------------------------------------------------
# Write outcome
# ---------------------------------------------------------------------------

@dataclass
class ArtifactWriteResult:
    """Which delivery artifacts made it to disk, and why the others did not.

    A failed manifest write used to live only in pipeline.log while the UI
    reported success — the FBX shipped without the contract that makes it
    importable. Failures belong in the return value.
    """

    manifest: Optional[str] = None
    report: Optional[str] = None
    log: str = ""
    manifest_error: str = ""
    report_error: str = ""

    def errors(self) -> list:
        return [e for e in (self.manifest_error, self.report_error) if e]

    # Kept so callers can still read this like the old dict.
    def __getitem__(self, key: str):
        return getattr(self, key)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def manifest_path_for(fbx_path: str) -> str:
    """manifest.json lives next to the FBX, same basename."""
    return os.path.splitext(fbx_path)[0] + "_manifest.json"


def log_path_for(fbx_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(fbx_path)), "pipeline.log")


def report_path_for(fbx_path: str) -> str:
    return os.path.splitext(fbx_path)[0] + "_export_report.md"


def thinning_svg_path_for(fbx_path: str) -> str:
    """Curve-comparison SVG lives next to the report, same basename."""
    return os.path.splitext(fbx_path)[0] + "_thinning.svg"


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_export_manifest(result: ExportResult) -> str:
    """Serialize result.manifest to disk next to the FBX. Returns the path."""
    path = manifest_path_for(result.fbx_path)
    return write_manifest(result.manifest, path)


def append_log(fbx_path: str, message: str) -> str:
    """Append a timestamped line to pipeline.log next to the FBX."""
    path = log_path_for(fbx_path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as fp:
        fp.write(f"[{ts}] {message}\n")
    return path


def write_markdown_report(result: ExportResult) -> str:
    """Write a Markdown export report next to the FBX. Returns the path."""
    path = report_path_for(result.fbx_path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    m = result.manifest
    lines = []
    lines.append(f"# Export Report — {m.source.maya_scene or 'untitled'}")
    lines.append("")
    lines.append(f"- **Export time:** {m.export_time}")
    lines.append(f"- **Tool version:** {m.tool_version or '0.1.0'}")
    lines.append(f"- **Preset:** `{m.source.preset}`")
    lines.append(f"- **Skeleton root:** `{m.source.skeleton_root}`")
    lines.append("")
    lines.append("## Convention")
    lines.append("")
    lines.append(f"- Up axis: `{m.convention.up_axis}`")
    lines.append(f"- Unit: `{m.convention.unit}`")
    lines.append(f"- Frame rate: `{m.convention.frame_rate}`")
    lines.append(f"- Axis conversion: `{m.convention.axis_conversion}` (locked off)")
    lines.append("")

    lines.append("## Validation")
    lines.append("")
    v = m.validation
    status_badge = {
        "passed": "✅ passed",
        "passed_with_warnings": "⚠️ passed with warnings",
        "failed": "❌ failed",
    }.get(v.status, v.status)
    lines.append(f"**Status:** {status_badge}")
    lines.append("")
    lines.append(f"| Level | Count |")
    lines.append(f"|-------|-------|")
    lines.append(f"| Error | {v.errors} |")
    lines.append(f"| Warning | {v.warnings} |")
    lines.append(f"| Info | {v.infos} |")
    lines.append("")

    if v.results:
        lines.append("### Check details")
        lines.append("")
        lines.append("| Check | Level | Passed | Message |")
        lines.append("|-------|-------|--------|---------|")
        for r in v.results:
            if r.skipped:
                mark = "⏭️"
            else:
                mark = "✅" if r.passed else {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[r.level]
            msg = (r.message or "").replace("|", "\\|")
            lines.append(f"| `{r.check}` | {r.level} | {mark} | {msg} |")
        lines.append("")

    if v.skipped:
        # 跳过了什么必须白纸黑字：error 级排最前，最该被看见的先看见。
        lines.append("### Skipped checks")
        lines.append("")
        lines.append("_These checks were switched off before export — they never ran._")
        lines.append("")
        lines.append("| Check | Level |")
        lines.append("|-------|-------|")
        order = {"error": 0, "warning": 1, "info": 2}
        for s in sorted(v.skipped, key=lambda s: (order.get(s.level, 3), s.check)):
            lines.append(f"| `{s.check}` | {s.level} |")
        lines.append("")

    lines.append("## Clips")
    lines.append("")
    if m.clips:
        lines.append("| Name | Start | End | Root motion |")
        lines.append("|------|-------|-----|-------------|")
        for clip in m.clips:
            rm = "✅" if clip.root_motion else "—"
            lines.append(f"| `{clip.name}` | {clip.start} | {clip.end} | {rm} |")
    else:
        lines.append("_No clips defined._")
    lines.append("")

    lines.append("## Output")
    lines.append("")
    lines.append(f"- **FBX:** `{result.fbx_path}`")
    lines.append(f"- **FBX written:** {'yes' if result.fbx_written else 'no'}")
    if result.export_range:
        lines.append(f"- **Export range:** frames {result.export_range[0]}–{result.export_range[1]}")
    lines.append(f"- **UE destination:** `{m.ue_destination.content_root}`")
    lines.append(f"- **Overwrite policy:** `{m.ue_destination.overwrite_policy}`")
    lines.append("")

    if result.errors:
        lines.append("## Errors")
        lines.append("")
        for e in result.errors:
            lines.append(f"- {e}")
        lines.append("")

    # Thinning is a scene mutation performed on request — it leaves a paper
    # trail here and in the manifest, and one Ctrl+Z in Maya undoes it all.
    if result.thinning is not None:
        t = result.thinning
        lines.append("## 关键帧抽稀")
        lines.append("")
        lines.append(f"- **档位：** `{t.level}`")
        lines.append(f"- **Key 数：** {t.keys_before} → {t.keys_after}"
                     f"（抽掉 {t.removed}，-{t.removed_pct:.1f}%）")
        lines.append(f"- **触及曲线：** {t.curves_touched}")
        lines.append(f"- **最大误差：** {t.max_error:.4g}")
        lines.append("")
        svg = _write_thinning_svg(result)
        if svg:
            lines.append(f"![curve comparison]({os.path.basename(svg)})")
            lines.append("")

    lines.append("## UE import")
    lines.append("")
    lines.append("Run the UE-side importer against the manifest:")
    lines.append("```")
    lines.append(f"manifest = {manifest_path_for(result.fbx_path)}")
    lines.append("```")

    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
    return path


def _write_thinning_svg(result: ExportResult) -> str:
    """Write the curve-comparison SVG next to the report. Returns "" on skip."""
    panels = result.thinning.panels if result.thinning else []
    if not panels:
        return ""
    from mtu_maya.export.curve_svg import render_curve_panels
    svg = render_curve_panels(panels)
    if not svg:
        return ""
    path = thinning_svg_path_for(result.fbx_path)
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(svg)
    return path


def write_all_artifacts(result: ExportResult, write_report: bool = True) -> ArtifactWriteResult:
    """Write manifest + log + (optional) report.

    Failures are recorded on the returned object AND pushed back onto
    `result` so the caller cannot mistake a half-written delivery for a
    complete one.
    """
    written = ArtifactWriteResult(log=log_path_for(result.fbx_path))

    # Manifest — always, even on failure (so the report can be inspected).
    try:
        written.manifest = write_export_manifest(result)
        append_log(result.fbx_path, f"manifest written: {written.manifest}")
    except Exception as exc:
        written.manifest_error = f"manifest 写入失败（{type(exc).__name__}）：{exc}"
        append_log(result.fbx_path, f"FAILED to write manifest: {exc}")

    # FBX outcome log line.
    if result.fbx_written:
        append_log(result.fbx_path, f"FBX exported: {result.fbx_path}")
    else:
        append_log(result.fbx_path, f"FBX NOT written. Reasons: {result.errors or 'blocked by validation'}")

    # Markdown report.
    if write_report or result.manifest.publication:
        try:
            written.report = write_markdown_report(result)
            append_log(result.fbx_path, f"report written: {written.report}")
        except Exception as exc:
            written.report_error = f"导出报告写入失败（{type(exc).__name__}）：{exc}"
            append_log(result.fbx_path, f"FAILED to write report: {exc}")

    result.manifest_path = written.manifest or ""
    result.report_path = written.report or ""
    result.errors.extend(written.errors())
    if result.manifest.publication and result.fbx_written and written.manifest and written.report and not result.errors:
        try:
            from bridge.manifest import atomic_write_json
            from bridge.publication import file_hash, ready_path
            path = ready_path(written.manifest)
            atomic_write_json({
                "publish_id": result.manifest.publication["publish_id"],
                "manifest_sha256": file_hash(written.manifest),
                "report": os.path.basename(written.report), "report_sha256": file_hash(written.report),
            }, path)
            result.ready_path = path
        except Exception as exc:
            result.errors.append(f"发布就绪标识写入失败：{exc}")
    return written


__all__ = [
    "ArtifactWriteResult",
    "manifest_path_for",
    "log_path_for",
    "report_path_for",
    "thinning_svg_path_for",
    "write_export_manifest",
    "append_log",
    "write_markdown_report",
    "write_all_artifacts",
]
