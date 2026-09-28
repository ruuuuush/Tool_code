"""UE-side launcher for the Maya->UE pipeline importer.

How to use:
    1. Make sure both ``maya_to_ue/`` and the FBX/manifest are reachable
       from the UE machine.
    2. In UE's Output Log, switch to Python and run:

           import launch_ue_importer
           outcome = launch_ue_importer.run(r"D:/exports/hero_manifest.json")
           launch_ue_importer.report(outcome)

    Or bind the same two lines to an Editor Utility Button.

This launcher adds the repo to sys.path and forwards to
``unreal.import_manifest``. All real logic lives in the ``unreal``
package; the launcher never needs updating when import details change.
"""

from __future__ import annotations

import os
import sys
from typing import Optional


def _ensure_repo_on_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    return here


def _load_package():
    """Load our `unreal` package under a distinct name to dodge the clash."""
    _ensure_repo_on_path()
    # The package is named `unreal`, which clashes with UE's own module of
    # the same name. We import the *folder* explicitly to disambiguate.
    import unreal as ue_builtin  # noqa: F401  (sanity check that we are in UE)

    import importlib.util
    # The editor is long-lived: submodules cached from an earlier push would
    # shadow newer code on disk (a fresh __init__ importing a name added since
    # then explodes with ImportError). Evict our package so every run reloads.
    for name in [n for n in sys.modules if n == "mtu_unreal" or n.startswith("mtu_unreal.")]:
        del sys.modules[name]
    here = _ensure_repo_on_path()
    pkg_init = os.path.join(here, "unreal", "__init__.py")
    spec = importlib.util.spec_from_file_location("mtu_unreal", pkg_init)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mtu_unreal"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def check():
    """Verify this UE build exposes everything the importer needs.

    Run this FIRST on a new engine version:

        import launch_ue_importer
        launch_ue_importer.check()
    """
    mod = _load_package()
    version = mod.ue_version()
    print(f"=== Maya->UE environment check ===")
    print(f"Engine: {version or '(unknown)'}")
    problems = mod.check_environment()
    flag = mod.interchange_fbx_enabled()
    if flag is not None:
        print(f"Interchange FBX import: {'ON' if flag else 'OFF (legacy path active)'}")
    if not problems:
        print("OK - all required APIs are available.")
        return []
    for p in problems:
        print(f"  PROBLEM: {p}")
    return problems


def run(manifest_path: str, fbx_path_override: Optional[str] = None):
    """Run the importer against a manifest. Returns the ImportOutcome."""
    mod = _load_package()
    return mod.import_manifest(manifest_path, fbx_path_override)


def report(outcome) -> None:
    """Pretty-print an ImportOutcome to the UE Output Log."""
    print("=== Maya->UE import result ===")
    if getattr(outcome, "skeleton_created", False):
        print(f"Skeleton: {outcome.skeleton_asset_path}  (CREATED)")
        if getattr(outcome, "skeletal_mesh_path", ""):
            print(f"SkeletalMesh: {outcome.skeletal_mesh_path}  (CREATED)")
    else:
        print(f"Skeleton: {outcome.skeleton_asset_path}")
    print("Imported clips:")
    print(f"Succeeded ({len(outcome.succeeded)}): {', '.join(outcome.succeeded) or '-'}")
    print(f"Skipped   ({len(outcome.skipped)}): {', '.join(outcome.skipped) or '-'}")
    print(f"Failed    ({len(outcome.failed)}): {', '.join(outcome.failed) or '-'}")
    for err in outcome.errors:
        print(f"  ERROR: {err}")
    # Content Browser 定位到生成的资产——推送与手动粘贴都走这里，两路一致。
    _load_package().reveal_assets(outcome)


if __name__ == "__main__":
    # Allow: python launch_ue_importer.py <manifest_path>
    if len(sys.argv) >= 2:
        outcome = run(sys.argv[1])
        report(outcome)
