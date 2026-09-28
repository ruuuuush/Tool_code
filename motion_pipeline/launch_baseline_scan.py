"""Launcher for the Motion Pipeline: scan, calibrate, augment.

Measures how much the planted foot of each source clip slides, turns that
into threshold suggestions for the quality gate
(docs/01_data_augmentation_design.md §3.2), and can then produce gated
augmented variants of those clips.

How to use, from Maya's Script Editor (Python tab):

    import sys
    sys.path.insert(0, r"D:/tool_code/motion_pipeline")
    import launch_baseline_scan

    launch_baseline_scan.check()                          # run this first
    scan = launch_baseline_scan.run(name="mixamo_walk")   # current scene
    launch_baseline_scan.report(scan, out_path=r"D:/tool_code/motion_pipeline/out/baseline.md")

To scan a folder of FBX clips instead of the open scene:

    scan = launch_baseline_scan.run_batch(
        [r"D:/clips/walk.fbx", r"D:/clips/run.fbx"],
        source_fps=30,
        allow_scene_reset=True,      # required: this discards the open scene
    )

To calibrate gate thresholds — scanning the real clips and comparing
against a synthetically degraded batch:

    good, runs, suggestions = launch_baseline_scan.run_calibration(
        [r"D:/clips/walk.fbx"], source_fps=30, allow_scene_reset=True
    )
    launch_baseline_scan.report_calibration(good, runs, suggestions)

To produce gated augmented variants (Step 3):

    scan = launch_baseline_scan.run_batch(
        [r"D:/clips/walk.fbx"], source_fps=30, allow_scene_reset=True
    )
    report, written = launch_baseline_scan.run_augmentation(
        [r"D:/clips/walk.fbx"],
        scan,                                   # each variant is judged
        out_dir=r"D:/clips/augmented",          # against its own source
        source_fps=30,
        allow_scene_reset=True,
    )
    launch_baseline_scan.report_gate(report, written)

Or from the shell in one step:

    mayapy launch_baseline_scan.py --fps 30 --augment --out D:/clips/augmented <fbx> ...

All measurement logic lives in ``mp_core`` / ``mp_maya``; this file only
wires them to Maya and formats output.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence

# Maya keeps imported modules cached for the life of the session, so edits
# to mp_core/mp_maya would otherwise be invisible until a restart. Evicting
# them on every load keeps the tool reading from disk, same as the UE-side
# launcher in maya_to_ue/.
_OWN_MODULES = ("mp_core", "mp_maya")


def _ensure_repo_on_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    return here


def _mods():
    _ensure_repo_on_path()
    for name in [n for n in sys.modules if n in _OWN_MODULES or any(
        n.startswith(prefix + ".") for prefix in _OWN_MODULES
    )]:
        del sys.modules[name]
    import mp_core  # type: ignore
    import mp_maya  # type: ignore

    # Under bare mayapy there is no Maya session yet; this is a no-op
    # inside a running Maya.
    mp_maya.ensure_maya_ready()
    return mp_core, mp_maya


def _write(markdown: str, out_path: Optional[str]) -> None:
    if not out_path:
        return
    directory = os.path.dirname(os.path.abspath(out_path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    print("\nWrote {}".format(out_path))


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def check() -> List[str]:
    """Verify this Maya build exposes everything the sampler needs.

    Run this FIRST — before trusting any number it produces.
    """
    _, mp_maya = _mods()
    print("=== Motion Pipeline baseline scan: environment check ===")
    problems = mp_maya.check_environment()
    if not problems:
        print("OK - sampler can run.")
        print("  fps={}  up_index={}".format(mp_maya.scene_fps(), mp_maya.scene_up_index()))
        return []
    for problem in problems:
        print("  PROBLEM: {}".format(problem))
    return problems


def run(
    name: Optional[str] = None,
    root: Optional[str] = None,
    feet: Optional[Sequence[str]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    step: int = 1,
    config=None,
):
    """Scan the currently open scene. Returns a BaselineScan.

    ``root`` and ``feet`` are auto-detected when omitted — check what was
    found before trusting the numbers, since a wrong joint shifts every
    measurement.
    """
    mp_core, mp_maya = _mods()

    root = root or mp_maya.find_root_joint()
    if not root:
        raise RuntimeError("no root joint found; pass root=<joint path>")

    feet = list(feet) if feet else mp_maya.find_foot_bones()
    if not feet:
        raise RuntimeError(
            "no foot joints matched {}; pass feet=[...]".format(mp_maya.FOOT_PATTERNS)
        )

    samples = mp_maya.sample_clip(
        name=name or "current_scene",
        root_bone=root,
        foot_bones=feet,
        start=start,
        end=end,
        step=step,
    )
    return mp_core.analyse_clips([samples], config or mp_core.ContactConfig())


def collect_batch(
    paths: Sequence[str],
    root: Optional[str] = None,
    feet: Optional[Sequence[str]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    step: int = 1,
    source_fps: Optional[float] = None,
    allow_scene_reset: bool = False,
):
    """Sample one FBX per clip, each in a fresh scene. Returns ClipSamples.

    Opening a new scene per file discards whatever is currently open, so
    ``allow_scene_reset=True`` is required — this is a real loss of
    unsaved work, not a formality.

    ``source_fps`` aligns the scene time unit before each import; pass the
    rate the clips were authored at (Mixamo is 30). Without it, a 30 fps
    clip in Maya's default 24 fps scene reports every per-second figure
    25% off — Maya does not rescale keys across a frame-rate mismatch.
    """
    if not allow_scene_reset:
        raise RuntimeError(
            "collect_batch() opens a new scene per FBX, discarding the current "
            "scene and any unsaved changes. Save first, then pass "
            "allow_scene_reset=True to proceed."
        )

    _, mp_maya = _mods()
    samples_list = []
    for path in paths:
        if not os.path.isfile(path):
            print("  SKIP (not a file): {}".format(path))
            continue
        mp_maya.open_new_scene()
        mp_maya.import_fbx(path, source_fps=source_fps)
        # A mesh-only or pose-only FBX has no keys. Sampling it would fall
        # back to the playback range, read one static pose over and over,
        # and report a flawless clip — the most dangerous kind of wrong.
        if mp_maya.animation_range() is None:
            print("  SKIP (no keyframes — static clip): {}".format(path))
            continue
        clip_root = root or mp_maya.find_root_joint()
        if not clip_root:
            print("  SKIP (no root joint): {}".format(path))
            continue
        clip_feet = list(feet) if feet else mp_maya.find_foot_bones()
        if not clip_feet:
            print("  SKIP (no foot joints): {}".format(path))
            continue
        samples_list.append(
            mp_maya.sample_clip(
                name=os.path.splitext(os.path.basename(path))[0],
                root_bone=clip_root,
                foot_bones=clip_feet,
                start=start,
                end=end,
                step=step,
            )
        )
    return samples_list


def run_batch(
    paths: Sequence[str],
    root: Optional[str] = None,
    feet: Optional[Sequence[str]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    step: int = 1,
    source_fps: Optional[float] = None,
    allow_scene_reset: bool = False,
    config=None,
):
    """Scan one FBX per clip. Returns a BaselineScan."""
    mp_core, _ = _mods()
    samples = collect_batch(
        paths,
        root=root,
        feet=feet,
        start=start,
        end=end,
        step=step,
        source_fps=source_fps,
        allow_scene_reset=allow_scene_reset,
    )
    return mp_core.analyse_clips(samples, config or mp_core.ContactConfig())


def calibrate(good_scan, bad_scan=None, percentile_cut: float = 95.0):
    """Suggest gate thresholds from a known-good batch."""
    mp_core, _ = _mods()
    return mp_core.calibrate(good_scan, bad_scan, percentile_cut=percentile_cut)


def run_calibration(
    paths: Sequence[str],
    amplitudes: Optional[Sequence[float]] = None,
    root: Optional[str] = None,
    feet: Optional[Sequence[str]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    step: int = 1,
    source_fps: Optional[float] = None,
    percentile_cut: float = 95.0,
    allow_scene_reset: bool = False,
    config=None,
):
    """Scan real clips, then calibrate against a synthetically degraded batch.

    Returns ``(good_scan, runs, suggestions)``. The degraded batch exists
    because a pipeline cannot conjure genuinely bad motion: injecting a
    known amplitude gives a bad batch whose magnitude is controlled, which
    is what makes the metric's response checkable rather than a matter of
    opinion. See mp_core.synth.
    """
    mp_core, _ = _mods()
    samples = collect_batch(
        paths,
        root=root,
        feet=feet,
        start=start,
        end=end,
        step=step,
        source_fps=source_fps,
        allow_scene_reset=allow_scene_reset,
    )
    if not samples:
        raise RuntimeError("no clips were sampled — nothing to calibrate on")

    levels = tuple(amplitudes) if amplitudes else mp_core.DEFAULT_AMPLITUDES
    good, runs = mp_core.measure_injection(samples, levels, config=config)
    suggestions = mp_core.calibrate(
        good,
        runs[-1].scan if runs else None,
        percentile_cut=percentile_cut,
    )
    return good, runs, suggestions


def report(scan, suggestions=None, out_path: Optional[str] = None) -> str:
    """Print the Markdown report and optionally write it to ``out_path``."""
    mp_core, _ = _mods()
    markdown = mp_core.format_report(scan, suggestions)
    print(markdown)
    _write(markdown, out_path)
    return markdown


def report_calibration(good, runs, suggestions=None, out_path: Optional[str] = None) -> str:
    """Print the calibration report and optionally write it to ``out_path``."""
    mp_core, _ = _mods()
    markdown = mp_core.format_calibration_report(good, runs, suggestions)
    print(markdown)
    _write(markdown, out_path)
    return markdown


# ---------------------------------------------------------------------------
# Step 3: augmentation, gated
# ---------------------------------------------------------------------------


def _variant_label(factor: float, mirrored: bool) -> str:
    label = "w{:.2f}".format(factor)
    return "{}_mirror".format(label) if mirrored else label


def run_augmentation(
    paths: Sequence[str],
    source_scan,
    tolerance: float = 0.25,
    warp_factors: Sequence[float] = (1.0, 0.85, 1.15),
    mirror: bool = True,
    out_dir: Optional[str] = None,
    source_fps: Optional[float] = None,
    root: Optional[str] = None,
    feet: Optional[Sequence[str]] = None,
    allow_scene_reset: bool = False,
    config=None,
):
    """Produce augmented variants of each source clip and gate them.

    Every variant is built in a fresh scene from the source FBX, sampled,
    and compared against **its own source clip** (``source_scan``) rather
    than a global cut. The sources are acceptable by definition — they are
    what shipped — so a cut derived from them rejects them; measured on a
    2-clip corpus, every source and every variant failed, including the
    unmodified control.

    A variant that is materially worse than its source is reported and
    dropped. That is the entire point: ungated augmentation adds database
    entries worse than the clips they came from.

    Returns ``(gate_report, written_paths)``.
    """
    if not allow_scene_reset:
        raise RuntimeError(
            "run_augmentation() opens a new scene per variant, discarding "
            "the current scene and any unsaved changes. Save first, then "
            "pass allow_scene_reset=True to proceed."
        )
    mp_core, mp_maya = _mods()
    config = config or mp_core.ContactConfig()

    verdicts = []
    written: List[str] = []
    for path in paths:
        if not os.path.isfile(path):
            print("  SKIP (not a file): {}".format(path))
            continue
        source = os.path.splitext(os.path.basename(path))[0]
        skeleton_skipped = False

        for factor in warp_factors:
            if skeleton_skipped:
                break
            for mirrored in ((False, True) if mirror else (False,)):
                label = "{}_{}".format(source, _variant_label(factor, mirrored))

                mp_maya.open_new_scene()
                mp_maya.import_fbx(path, source_fps=source_fps)
                # Sampling past the animation would read a frozen pose (see
                # foot_contact.moving_window), and mirroring past it would
                # stamp keys onto frames the clip never had.
                span = mp_maya.animation_range()
                if span is None:
                    print("  SKIP (no keyframes): {}".format(path))
                    skeleton_skipped = True
                    break

                # Retime FIRST, mirror second — the order is load-bearing.
                #
                # Both operations re-key the curves they touch, and a
                # re-keyed curve carries default tangents instead of the
                # source FBX's. Retiming samples at *fractional* times, so
                # it must only ever read source curves; mirroring samples
                # integer frames only, so it is safe on re-keyed data.
                # Measured the other way round: 2x the slide and a gate
                # rejection (docs/01 §10.2).
                if factor != 1.0:
                    span = mp_maya.retime(
                        mp_maya.list_joints(), span[0], span[1], factor
                    )
                if mirrored:
                    try:
                        mp_maya.mirror_animation(
                            mp_maya.list_joints(), start=span[0], end=span[1]
                        )
                    except ValueError as exc:
                        print("  SKIP (not mirrorable) {}: {}".format(label, exc))
                        continue

                clip_root = root or mp_maya.find_root_joint()
                clip_feet = list(feet) if feet else mp_maya.find_foot_bones()
                if not clip_root or not clip_feet:
                    print("  SKIP (no root or feet): {}".format(label))
                    continue

                samples = mp_maya.sample_clip(
                    name=label, root_bone=clip_root, foot_bones=clip_feet
                )
                verdict = mp_core.evaluate_against_source(
                    mp_core.analyse_clips([samples], config),
                    source_scan,
                    {label: source},
                    tolerance=tolerance,
                ).verdicts[0]
                verdicts.append(verdict)

                if not verdict.accepted:
                    print("  REJECT {}: {}".format(label, "; ".join(verdict.reasons)))
                    continue

                if out_dir:
                    target = os.path.join(out_dir, label + ".fbx")
                    directory = os.path.dirname(os.path.abspath(target))
                    if directory and not os.path.isdir(directory):
                        os.makedirs(directory)
                    mp_maya.export_fbx(target, clip_root)
                    written.append(target)
                print("  ACCEPT {}".format(label))

    # Each check carries its own per-clip cut, so the report's global cut
    # table is intentionally empty.
    return (
        mp_core.GateReport(thresholds=mp_core.Thresholds({}), verdicts=verdicts),
        written,
    )


def report_gate(report, written=None, out_path: Optional[str] = None) -> str:
    """Print the gate report and optionally write it to ``out_path``."""
    mp_core, _ = _mods()
    markdown = mp_core.format_gate_report(report)
    if written:
        markdown += "\n\n## Written\n\n" + "\n".join(
            "- `{}`".format(path) for path in written
        )
    print(markdown)
    _write(markdown, out_path)
    return markdown


def expand_paths(paths: Sequence[str]) -> List[str]:
    """Expand directories into the .fbx files they contain, sorted.

    Lets the whole corpus folder be one argument. Non-recursive: corpus
    layout keeps sources flat (docs/02), and recursing would quietly pick
    up exported variants sitting in subfolders — feeding augmented output
    back in as source is exactly the mistake to make impossible.
    """
    expanded: List[str] = []
    for path in paths:
        if os.path.isdir(path):
            expanded.extend(
                sorted(
                    os.path.join(path, name)
                    for name in os.listdir(path)
                    if name.lower().endswith(".fbx")
                )
            )
        else:
            expanded.append(path)
    return expanded


@dataclass
class _Options:
    """Parsed command line."""

    paths: List[str]
    fps: Optional[float] = None
    calibrate: bool = False
    augment: bool = False
    out_dir: Optional[str] = None
    report: Optional[str] = None


def run_report(
    paths: Sequence[str],
    out_html: str,
    source_fps: Optional[float] = None,
    root: Optional[str] = None,
    feet: Optional[Sequence[str]] = None,
    percentile_cut: float = 95.0,
    allow_scene_reset: bool = False,
    config=None,
) -> str:
    """Scan, calibrate, and render everything into one portable HTML file.

    The file embeds every SVG panel inline — no external assets, no JS —
    so it can be opened from disk, mailed, or dropped into a portfolio
    page unchanged. This is the artefact to show people.
    """
    mp_core, _ = _mods()
    config = config or mp_core.ContactConfig()

    samples = collect_batch(
        paths,
        root=root,
        feet=feet,
        source_fps=source_fps,
        allow_scene_reset=allow_scene_reset,
    )
    if not samples:
        raise RuntimeError("no clips were sampled — nothing to report")

    # Trim once here so the inspection panels show exactly the frames the
    # numbers were computed from (measure_injection trims internally; a
    # panel drawn from untrimmed samples would contradict the table).
    prepared = [mp_core.trim_to_motion(item, config)[0] for item in samples]
    good, runs = mp_core.measure_injection(prepared, config=config)
    suggestions = mp_core.calibrate(
        good, runs[-1].scan if runs else None, percentile_cut=percentile_cut
    )
    html = mp_core.html_report(prepared, good, runs, suggestions, config)
    _write(html, out_html)
    return html


def _parse_argv(argv: Sequence[str]) -> _Options:
    """Split flags out of the FBX path list."""
    options = _Options(paths=[])
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ("--fps", "--out", "--report"):
            if index + 1 >= len(argv):
                raise SystemExit("{} needs a value".format(token))
            value = argv[index + 1]
            if token == "--fps":
                options.fps = float(value)
            elif token == "--out":
                options.out_dir = value
            else:
                options.report = value
            index += 2
            continue
        if token == "--calibrate":
            options.calibrate = True
        elif token == "--augment":
            options.augment = True
        else:
            options.paths.append(token)
        index += 1
    return options


if __name__ == "__main__":
    # mayapy launch_baseline_scan.py [--fps 30] [--calibrate | --augment | --report FILE.html]
    #                                [--out DIR] <fbx-or-dir> [<fbx-or-dir> ...]
    _options = _parse_argv(sys.argv[1:])
    _options.paths = expand_paths(_options.paths)
    if not _options.paths:
        print(__doc__)
    elif _options.report:
        run_report(
            _options.paths,
            _options.report,
            source_fps=_options.fps,
            allow_scene_reset=True,
        )
    elif _options.augment:
        # Scan the sources first: the gate compares each variant against
        # its own source, so it needs the source measurements up front.
        _good, _runs, _suggestions = run_calibration(
            _options.paths, source_fps=_options.fps, allow_scene_reset=True
        )
        _report, _written = run_augmentation(
            _options.paths,
            _good,
            out_dir=_options.out_dir,
            source_fps=_options.fps,
            allow_scene_reset=True,
        )
        report_gate(_report, _written)
    elif _options.calibrate:
        _good, _runs, _suggestions = run_calibration(
            _options.paths, source_fps=_options.fps, allow_scene_reset=True
        )
        report_calibration(_good, _runs, _suggestions)
    else:
        report(
            run_batch(_options.paths, source_fps=_options.fps, allow_scene_reset=True)
        )
