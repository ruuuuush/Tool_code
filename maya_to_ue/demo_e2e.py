"""End-to-end integration demo.

Simulates the full pipeline WITHOUT Maya or UE installed, proving the
bridge layer correctly carries information from the Maya-side export
artifacts to the UE-side import decisions.

The flow:
    1. Build a manifest exactly like the Maya exporter would write it
       (including a validation summary and clip list).
    2. Write it + a Markdown report to a temp dir (skipping the actual
       FBX, since that needs Maya).
    3. Read it back the way the UE importer would.
    4. Compute the exact UE asset paths and per-clip slice ranges the
       importer would use.

Run with:  python demo_e2e.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bridge import (
    Manifest, Source, Convention, Clip, UEDestination,
    ValidationSummary, CheckResultEntry, ImportResult,
    write_manifest, read_manifest,
)
from mtu_maya.export.manifest_writer import write_markdown_report, manifest_path_for
# Load UE-side pure helpers via file path (avoids the `unreal` name clash).
import importlib.util
_ue_init = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unreal", "__init__.py")
_spec = importlib.util.spec_from_file_location("mtu_unreal", _ue_init)
ue = importlib.util.module_from_spec(_spec)
sys.modules["mtu_unreal"] = ue
_spec.loader.exec_module(ue)  # type: ignore[union-attr]


def build_maya_side_manifest(fbx_path: str) -> Manifest:
    """Pretend we are the Maya exporter: assemble a valid manifest."""
    entries = [
        CheckResultEntry(check="scene.unit", level="error", passed=True, message="unit = cm"),
        CheckResultEntry(check="scene.up_axis", level="info", passed=True, message="scene up axis preserved"),
        CheckResultEntry(check="scene.fps", level="error", passed=True, message="fps = 30"),
        CheckResultEntry(check="skeleton.scale", level="warning", passed=False,
                         message="joint 'spine_03' scale = 1.02"),
        CheckResultEntry(check="anim.clip_ranges_valid", level="error", passed=True,
                         message="2 clip(s) with valid ranges"),
    ]
    return Manifest.new(
        tool_version="0.1.0",
        source=Source(maya_scene="hero_anim.ma", maya_version="2024",
                      preset="ue_mannequin", skeleton_root="root"),
        convention=Convention(up_axis="z", unit="cm", frame_rate=30, axis_conversion=False),
        clips=[
            Clip(name="idle", start=1, end=30, root_motion=False),
            Clip(name="walk", start=31, end=90, root_motion=True),
            Clip(name="run", start=91, end=150, root_motion=True),
        ],
        fbx_path=os.path.abspath(fbx_path),
        ue_destination=UEDestination(
            content_root="/Game/Animations/Hero",
            skeleton_path="/Game/Animations/Hero/Hero_Skeleton",
            overwrite_policy="rename",
        ),
        validation=ValidationSummary.from_entries(entries),
        result=ImportResult(status="pending"),
    )


def ue_side_plan(manifest: Manifest, manifest_path: str) -> None:
    """Pretend we are the UE importer: print what we would do."""
    print("\n--- UE-side import plan (computed from manifest) ---")
    print(f"Skeleton asset: {ue.skeleton_asset_path(manifest.ue_destination, manifest.source.maya_scene)}")
    print(f"FBX to import:  {manifest.fbx_path}")
    print(f"Overwrite policy: {manifest.ue_destination.overwrite_policy}")
    print(f"Frame rate: {manifest.convention.frame_rate}")
    print()
    print(f"{'Clip':<10} {'Frames':<12} {'Seconds':<20} {'Asset path':<40} {'Root motion'}")
    print("-" * 95)
    for clip in manifest.clips:
        start_s, end_s = ue.frame_range_to_seconds(
            clip.start, clip.end, manifest.convention.frame_rate
        )
        path = ue.clip_asset_path(manifest.ue_destination, clip)
        print(f"{clip.name:<10} {clip.start}-{clip.end:<8} "
              f"{start_s:.3f}s -> {end_s:.3f}s   {path:<40} {'on' if clip.root_motion else 'off'}")

    print("\nExpected asset paths (verifiable from UE without importing):")
    for p in ue.list_expected_asset_paths(manifest_path):
        print(f"  {p}")


def main():
    with tempfile.TemporaryDirectory(prefix="maya_to_ue_e2e_") as tmp:
        fbx_path = os.path.join(tmp, "exports", "hero.fbx")
        os.makedirs(os.path.dirname(fbx_path), exist_ok=True)
        # Touch a placeholder FBX so path checks would pass.
        with open(fbx_path, "wb") as fp:
            fp.write(b"placeholder")

        # --- Maya side ---
        print("=== Maya-side export (simulated) ===")
        manifest = build_maya_side_manifest(fbx_path)
        mpath = write_manifest(manifest, manifest_path_for(fbx_path))
        print(f"Wrote manifest: {mpath}")
        report_path = write_markdown_report(_fake_export_result(manifest))
        print(f"Wrote report:   {report_path}")
        print(f"Validation: {manifest.validation.status} "
              f"({manifest.validation.errors}E/{manifest.validation.warnings}W)")
        print(f"Clips: {[c.name for c in manifest.clips]}")

        # --- Bridge (independent of either app) ---
        print("\n=== Bridge round-trip ===")
        reloaded = read_manifest(mpath)
        assert reloaded.clips[1].root_motion is True, "walk clip should have root motion"
        assert reloaded.validation.status == "passed_with_warnings"
        print(f"Manifest reloads cleanly: {len(reloaded.clips)} clips, "
              f"preset={reloaded.source.preset}")

        # --- UE side ---
        ue_side_plan(reloaded, mpath)

        print("\n=== Result ===")
        print("End-to-end pipeline carries information correctly between")
        print("Maya export artifacts and UE import decisions, with NO Maya")
        print("or UE installed. FBX I/O is the only remaining gap, and it is")
        print("verified at runtime inside each application.")


class _FakeExportResult:
    """Minimal stand-in for maya.export.ExportResult so write_markdown_report works."""
    def __init__(self, manifest):
        from mtu_maya.checks import RunReport, CheckResult
        self.manifest = manifest
        self.report = RunReport(results=[
            CheckResult(check_id=e.check, category=e.check.split(".")[0],
                        level=e.level, passed=e.passed, message=e.message,
                        auto_fixable=e.auto_fixable)
            for e in manifest.validation.results
        ])
        self.fbx_written = True
        self.fbx_path = manifest.fbx_path
        self.export_range = (
            min(c.start for c in manifest.clips),
            max(c.end for c in manifest.clips),
        )
        self.errors = []


def _fake_export_result(manifest):
    return _FakeExportResult(manifest)


if __name__ == "__main__":
    main()
