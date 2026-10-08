"""tests.test_export

Tests for the export layer.

The FBX exporter's top-level export_animation() requires a live Maya
session (it reads the scene), so we test it indirectly by exercising
the pure-logic pieces and by building a fake ExportResult to drive the
manifest/report writers end-to-end.

Coverage:
    - compute_export_range (pure logic)
    - manifest_writer paths (pure logic)
    - manifest_writer round-trip with a fake ExportResult
    - markdown report contents
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge.schema import (
    Clip,
    Manifest,
    Source,
    Convention,
    UEDestination,
    ValidationSummary,
    CheckResultEntry,
    ImportResult,
)
from mtu_maya.checks import CheckResult, RunReport
from mtu_maya.export.fbx_exporter import (
    ExportRequest,
    ExportResult,
    compute_export_range,
)
from mtu_maya.export.manifest_writer import (
    manifest_path_for,
    log_path_for,
    report_path_for,
    write_all_artifacts,
    write_export_manifest,
    write_markdown_report,
    append_log,
)


def _fake_result(tmp: str, fbx_written: bool = False, with_errors: bool = False) -> ExportResult:
    """Build an ExportResult that looks like a real export outcome."""
    fbx_path = os.path.join(tmp, "exports", "hero.fbx")

    entries = [
        CheckResultEntry(check="scene.unit", level="error", passed=True, message="unit = cm"),
        CheckResultEntry(check="scene.up_axis", level="info", passed=True, message="scene up axis preserved"),
        CheckResultEntry(check="skeleton.scale", level="warning", passed=False,
                         message="joint 'spine_03' scale = 1.02"),
    ]
    summary = ValidationSummary.from_entries(entries)
    if with_errors:
        entries.append(CheckResultEntry(check="scene.fps", level="error", passed=False,
                                        message="fps is 24, must be 30"))
        summary = ValidationSummary.from_entries(entries)

    report = RunReport(results=[
        CheckResult(check_id=e.check, category=e.check.split(".")[0],
                    level=e.level, passed=e.passed, message=e.message,
                    auto_fixable=e.auto_fixable)
        for e in entries
    ])

    manifest = Manifest.new(
        tool_version="0.1.0",
        source=Source(maya_scene="hero_anim.ma", maya_version="2024",
                      preset="ue_mannequin", skeleton_root="|root"),
        convention=Convention(up_axis="z", unit="cm", frame_rate=30, axis_conversion=False),
        clips=[
            Clip(name="idle", start=1, end=30, root_motion=False),
            Clip(name="walk", start=31, end=90, root_motion=True),
        ],
        fbx_path=os.path.abspath(fbx_path),
        ue_destination=UEDestination(content_root="/Game/Animations/Hero",
                                     skeleton_path="/Game/Animations/Hero/Hero_Skeleton",
                                     overwrite_policy="rename"),
        validation=summary,
        result=ImportResult(status="pending"),
    )

    return ExportResult(
        manifest=manifest,
        report=report,
        fbx_written=fbx_written,
        fbx_path=os.path.abspath(fbx_path),
        export_range=(1, 90),
        errors=["blocked by validation"] if with_errors else [],
    )


class TestExportSkipping(unittest.TestCase):
    def _request(self):
        from mtu_maya.core.preset_loader import SkeletonPreset

        return ExportRequest(
            fbx_path="hero.fbx",
            clips=[Clip("idle", 1, 30)],
            preset=SkeletonPreset(id="custom", display_name="Custom", skeleton_type="custom"),
            skeleton_root="|root",
        )

    def test_default_sets_are_independent(self):
        first, second = self._request(), self._request()
        first.skipped_checks.add("scene.fps")
        self.assertEqual(second.skipped_checks, set())

    def test_export_rechecks_live_context_and_records_skips(self):
        from unittest.mock import patch
        from mtu_maya.checks import CheckContext, default_registry, run_all_checks
        from mtu_maya.export import fbx_exporter as exporter

        request = self._request()
        request.skipped_checks = {v.id for v in default_registry().all()}
        ctx = CheckContext()
        with patch.object(exporter, "build_context", return_value=ctx) as build, \
                patch.object(exporter, "run_all_checks", wraps=run_all_checks) as checks, \
                patch.object(exporter.maya_utils, "ensure_fbx_plugin", return_value=False), \
                patch.object(exporter, "_maya_version_str", return_value="2022"):
            result = exporter.export_animation(request)

        build.assert_called_once()
        checks.assert_called_once_with(ctx, skipped=request.skipped_checks)
        self.assertEqual(
            {entry.check for entry in result.manifest.validation.skipped},
            request.skipped_checks,
        )
        self.assertEqual(result.report.errors, [])
        self.assertEqual(result.report.passed_count, 0)

    def test_unskipped_errors_still_block_fbx(self):
        from unittest.mock import patch
        from mtu_maya.checks import CheckContext
        from mtu_maya.export import fbx_exporter as exporter

        report = RunReport(results=[CheckResult(
            check_id="scene.fps", category="scene", level="error",
            passed=False, message="fps mismatch",
        )])
        with patch.object(exporter, "build_context", return_value=CheckContext()), \
                patch.object(exporter, "run_all_checks", return_value=report) as checks, \
                patch.object(exporter, "_export_fbx") as write, \
                patch.object(exporter, "_maya_version_str", return_value="2022"):
            result = exporter.export_animation(self._request())

        self.assertEqual(checks.call_args[1]["skipped"], set())
        write.assert_not_called()
        self.assertFalse(result.fbx_written)
        self.assertEqual(result.manifest.validation.errors, 1)


class TestExportRequestFirstDelivery(unittest.TestCase):
    def test_request_carries_first_delivery_options_when_settings_are_normalized(self):
        from dataclasses import replace
        from mtu_maya.core.config import PipelineSettings
        from mtu_maya.core.preset_loader import SkeletonPreset

        request = ExportRequest(
            fbx_path="hero.fbx",
            clips=[Clip("idle", 1, 30)],
            preset=SkeletonPreset(id="custom", display_name="Custom", skeleton_type="custom"),
            skeleton_root="|root",
            include_rig=True,
            create_skeleton_if_missing=True,
            ue_import_scale=100.0,
        )
        normalized = replace(request, settings=PipelineSettings())
        self.assertTrue(normalized.include_rig)
        self.assertTrue(normalized.create_skeleton_if_missing)
        self.assertEqual(normalized.ue_import_scale, 100.0)
        self.assertIsNotNone(normalized.settings)


# ---------------------------------------------------------------------------
# compute_export_range
# ---------------------------------------------------------------------------

class TestComputeRange(unittest.TestCase):
    def test_empty_clips_returns_none(self):
        self.assertIsNone(compute_export_range([]))

    def test_single_clip(self):
        self.assertEqual(compute_export_range([Clip("a", 1, 10)]), (1, 10))

    def test_multiple_clips_takes_min_max(self):
        clips = [Clip("a", 5, 20), Clip("b", 1, 10), Clip("c", 30, 60)]
        self.assertEqual(compute_export_range(clips), (1, 60))

    def test_disjoint_clips(self):
        clips = [Clip("a", 1, 30), Clip("b", 100, 120)]
        self.assertEqual(compute_export_range(clips), (1, 120))


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

class TestPathHelpers(unittest.TestCase):
    def test_manifest_path_same_basename(self):
        # manifest_path_for is pure string ops (no abspath), so stable.
        self.assertTrue(manifest_path_for("hero.fbx").endswith("hero_manifest.json"))

    def test_log_path_uses_dir(self):
        # log_path_for abspaths to be safe on disk; check it lands in the same dir
        # and is named pipeline.log, cross-platform.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fbx = os.path.join(tmp, "sub", "hero.fbx")
            self.assertEqual(log_path_for(fbx), os.path.join(tmp, "sub", "pipeline.log"))

    def test_report_path_same_basename(self):
        self.assertTrue(report_path_for("hero.fbx").endswith("hero_export_report.md"))


# ---------------------------------------------------------------------------
# End-to-end artifact writing
# ---------------------------------------------------------------------------

class TestWriteArtifacts(unittest.TestCase):
    def test_write_all_artifacts_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            paths = write_all_artifacts(result, write_report=True)

            self.assertTrue(os.path.isfile(paths["manifest"]))
            self.assertTrue(os.path.isfile(paths["report"]))
            self.assertTrue(os.path.isfile(paths["log"]))
            self.assertEqual(
                paths["manifest"],
                os.path.join(tmp, "exports", "hero_manifest.json"),
            )

    def test_manifest_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            mpath = write_export_manifest(result)
            with open(mpath, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            self.assertEqual(data["source"]["maya_scene"], "hero_anim.ma")
            self.assertEqual(len(data["clips"]), 2)
            self.assertEqual(data["clips"][1]["name"], "walk")
            self.assertTrue(data["clips"]["walk"]["root_motion"] if isinstance(data["clips"], dict) else
                             data["clips"][1]["root_motion"])
            self.assertEqual(data["validation"]["status"], "passed_with_warnings")
            self.assertEqual(data["validation"]["warnings"], 1)

    def test_failed_export_still_writes_manifest_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=False, with_errors=True)
            paths = write_all_artifacts(result)

            # Manifest and report must exist even when export was blocked.
            self.assertTrue(os.path.isfile(paths["manifest"]))
            self.assertTrue(os.path.isfile(paths["report"]))
            self.assertEqual(result.manifest.validation.status, "failed")
            self.assertIn("blocked by validation", result.errors)

    def test_creates_missing_export_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            # The fake result's fbx_path points into tmp/exports which doesn't exist yet.
            result = _fake_result(tmp, fbx_written=True)
            self.assertFalse(os.path.isdir(os.path.join(tmp, "exports")))
            write_all_artifacts(result)
            self.assertTrue(os.path.isdir(os.path.join(tmp, "exports")))

    def test_log_appends_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            fbx_path = os.path.join(tmp, "hero.fbx")
            append_log(fbx_path, "first")
            append_log(fbx_path, "second")
            with open(log_path_for(fbx_path), "r", encoding="utf-8") as fp:
                content = fp.read()
            self.assertIn("first", content)
            self.assertIn("second", content)
            self.assertEqual(content.count("\n"), 2)


class TestArtifactWriteReporting(unittest.TestCase):
    """A half-written delivery must never look like a complete one."""

    def test_success_fills_paths_on_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            written = write_all_artifacts(result, write_report=True)

            self.assertEqual(result.manifest_path, written.manifest)
            self.assertEqual(result.report_path, written.report)
            self.assertEqual(written.errors(), [])
            self.assertEqual(result.errors, [])
            self.assertTrue(result.is_complete())

    def test_manifest_failure_is_reported_not_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            # An empty skeleton path is exactly the case that used to fail
            # silently: the FBX ships, the manifest refuses to serialise.
            result.manifest.ue_destination.skeleton_path = ""
            written = write_all_artifacts(result, write_report=True)

            self.assertIsNone(written.manifest)
            self.assertIn("manifest", written.manifest_error)
            self.assertEqual(result.manifest_path, "")
            self.assertTrue(any("manifest" in e for e in result.errors))
            self.assertFalse(result.is_complete())

    def test_report_failure_does_not_hide_manifest_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            import mtu_maya.export.manifest_writer as mw

            original = mw.write_markdown_report

            def _boom(_result):
                raise OSError("disk full")

            mw.write_markdown_report = _boom
            try:
                written = mw.write_all_artifacts(result, write_report=True)
            finally:
                mw.write_markdown_report = original

            self.assertTrue(os.path.isfile(written.manifest))
            self.assertIsNone(written.report)
            self.assertIn("disk full", written.report_error)
            self.assertTrue(result.is_complete())

    def test_result_keys_still_readable_like_a_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            written = write_all_artifacts(_fake_result(tmp, fbx_written=True))
            self.assertTrue(os.path.isfile(written["manifest"]))
            self.assertTrue(os.path.isfile(written["log"]))


# ---------------------------------------------------------------------------
# Markdown report contents
# ---------------------------------------------------------------------------

class TestMarkdownReport(unittest.TestCase):
    def test_report_contains_key_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            rpath = write_markdown_report(result)
            with open(rpath, "r", encoding="utf-8") as fp:
                content = fp.read()

        self.assertIn("# Export Report", content)
        self.assertIn("## Convention", content)
        self.assertIn("## Validation", content)
        self.assertIn("## Clips", content)
        self.assertIn("## Output", content)
        # Status badge for warnings
        self.assertIn("passed with warnings", content)
        # Clip names appear
        self.assertIn("`idle`", content)
        self.assertIn("`walk`", content)
        # Validation entries appear
        self.assertIn("scene.unit", content)
        self.assertIn("skeleton.scale", content)

    def test_report_shows_failed_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=False, with_errors=True)
            rpath = write_markdown_report(result)
            with open(rpath, "r", encoding="utf-8") as fp:
                content = fp.read()
        self.assertIn("failed", content)
        self.assertIn("## Errors", content)
        self.assertIn("blocked by validation", content)

    def test_report_shows_export_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            with open(write_markdown_report(result), "r", encoding="utf-8") as fp:
                content = fp.read()
        self.assertIn("frames 1–90", content)


class TestReportSkippedSection(unittest.TestCase):
    """跳过了什么，报告里得写着——否则下游只看到一个"通过"。"""

    def _report_with_skips(self, tmp, skips):
        result = _fake_result(tmp, fbx_written=True)
        entries = list(result.manifest.validation.results)
        entries.extend(
            CheckResultEntry(check=cid, level=level, passed=False, skipped=True)
            for cid, level in skips
        )
        result.manifest.validation = ValidationSummary.from_entries(entries)
        with open(write_markdown_report(result), "r", encoding="utf-8") as fp:
            return fp.read()

    def test_section_lists_the_skipped_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = self._report_with_skips(tmp, [("skeleton.naming", "error")])
        self.assertIn("### Skipped checks", content)
        self.assertIn("`skeleton.naming`", content)

    def test_errors_come_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = self._report_with_skips(
                tmp, [("mesh.count", "info"), ("skeleton.naming", "error")]
            )
        section = content.split("### Skipped checks", 1)[1]
        self.assertLess(section.index("skeleton.naming"), section.index("mesh.count"))

    def test_no_section_when_nothing_was_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            with open(write_markdown_report(result), "r", encoding="utf-8") as fp:
                content = fp.read()
        self.assertNotIn("### Skipped checks", content)

    def test_detail_row_marks_it_as_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = self._report_with_skips(tmp, [("skeleton.naming", "error")])
        row = next(l for l in content.splitlines() if "`skeleton.naming`" in l and "|" in l)
        self.assertNotIn("❌", row)


# ---------------------------------------------------------------------------
# Curve thinning artifacts
# ---------------------------------------------------------------------------

def _thinned_result(tmp):
    from mtu_maya.core.curve_thinning import CurvePanel, ThinningResult

    result = _fake_result(tmp, fbx_written=True)
    times = list(range(90))
    before = [(float(t), float(t % 7)) for t in times]
    after = [(0.0, 0.0), (45.0, 3.0), (89.0, 5.0)]
    result.thinning = ThinningResult(
        level="medium",
        curves_touched=3,
        keys_before=270,
        keys_after=30,
        max_error=0.04,
        panels=[CurvePanel(title="root.translateZ", before=before, after=after,
                           keys_before=90, keys_after=3)],
    )
    result.manifest.thinning = {
        "level": "medium", "keys_before": 270, "keys_after": 30,
    }
    return result


class TestThinningArtifacts(unittest.TestCase):
    def test_manifest_round_trip_keeps_thinning_summary(self):
        from bridge.manifest import read_manifest, write_manifest as _wm
        with tempfile.TemporaryDirectory() as tmp:
            result = _thinned_result(tmp)
            path = _wm(result.manifest, os.path.join(tmp, "m.json"))
            loaded = read_manifest(path)
        self.assertEqual(loaded.thinning["level"], "medium")
        self.assertEqual(loaded.thinning["keys_after"], 30)

    def test_manifest_without_thinning_reads_none(self):
        from bridge.manifest import read_manifest, write_manifest as _wm
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            path = _wm(result.manifest, os.path.join(tmp, "m.json"))
            loaded = read_manifest(path)
        self.assertIsNone(loaded.thinning)

    def test_report_has_thinning_section_and_svg_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _thinned_result(tmp)
            rpath = write_markdown_report(result)
            with open(rpath, "r", encoding="utf-8") as fp:
                content = fp.read()
            svg_path = os.path.join(tmp, "exports", "hero_thinning.svg")
            self.assertIn("关键帧抽稀", content)
            self.assertIn("270 → 30", content)
            self.assertIn("-88.9%", content)
            self.assertIn("hero_thinning.svg", content)
            # SVG 与报告同目录，且是合法 XML、含红蓝两条折线。
            self.assertTrue(os.path.isfile(svg_path))
            import xml.etree.ElementTree as ET
            root = ET.parse(svg_path).getroot()
            polylines = [e for e in root.iter() if e.tag.endswith("polyline")]
            self.assertEqual(len(polylines), 2)

    def test_report_without_thinning_has_no_section_and_no_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _fake_result(tmp, fbx_written=True)
            rpath = write_markdown_report(result)
            with open(rpath, "r", encoding="utf-8") as fp:
                content = fp.read()
            self.assertNotIn("关键帧抽稀", content)
            self.assertFalse(os.path.exists(
                os.path.join(tmp, "exports", "hero_thinning.svg")))

    def test_export_request_default_level_is_off(self):
        from mtu_maya.core.preset_loader import SkeletonPreset
        req = ExportRequest(
            fbx_path="hero.fbx",
            clips=[Clip("idle", 1, 30)],
            preset=SkeletonPreset(id="custom", display_name="Custom",
                                  skeleton_type="custom"),
            skeleton_root="|root",
        )
        self.assertEqual(req.thinning_level, "off")
        self.assertIsNone(_fake_result(tempfile.gettempdir()).thinning)


if __name__ == "__main__":
    unittest.main()
