"""maya_tools

A collection of Maya utility tools.

This package provides helper modules for common Maya scripting tasks.
Importing this package does not import Maya-only modules at the top level,
so it can be safely imported in environments where Maya is not available
(for example, during linting or documentation builds).

Submodules:
    core        - Common helpers (selection, naming, scene queries).
    rigging     - Rigging utilities (joints, controls, constraints).
    modeling    - Modeling helpers (mesh cleanup, transforms).
    animation   - Animation helpers (keyframes, playback).

Example:
    >>> from maya_tools import core
    >>> core.selected()
"""

__version__ = "0.1.0"
__author__ = "maya_tools contributors"

__all__ = ["core", "rigging", "modeling", "animation"]


def version():
    """Return the current package version string."""
    return __version__


def version_info():
    """Return the version as a tuple of integers, e.g. (0, 1, 0)."""
    return tuple(int(part) for part in __version__.split(".") if part.isdigit())
