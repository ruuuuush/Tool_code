"""maya.checks

The validator framework plus the five categories of shipped checks.

Adding a new check:
    1. Write a class subclassing BaseValidator.
    2. Set id/category/level/auto_fixable/description.
    3. Implement check(ctx) -> CheckResult (and fix(ctx) if auto_fixable).
    4. Decorate with @register_validator.

The UI picks it up automatically via default_registry(); no UI edits
needed. This is the core extensibility story (design.md section 4.2).
"""

from .registry import (
    BaseValidator,
    CheckContext,
    CheckResult,
    RunReport,
    ValidatorRegistry,
    default_registry,
    register_validator,
    run_all_checks,
    fix_check,
    fix_all_warnings,
)
from . import check_info

# Importing the check modules registers their validators as a side effect.
from . import (  # noqa: F401  (registration side effect)
    scene_checks,
    skeleton_checks,
    mesh_checks,
    anim_checks,
    export_checks,
)

__all__ = [
    "BaseValidator",
    "CheckContext",
    "CheckResult",
    "RunReport",
    "ValidatorRegistry",
    "default_registry",
    "register_validator",
    "run_all_checks",
    "fix_check",
    "fix_all_warnings",
    "check_info",
]
