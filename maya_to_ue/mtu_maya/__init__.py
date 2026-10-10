"""maya

Maya-side of the Maya->UE animation pipeline.

Subpackages:
    core   - shared utilities (config, maya.cmds wrappers, preset loader)
    checks - the validator registry and the per-category validators
    export - FBX export + manifest writing + Markdown report
    ui     - PySide6/PySide2 main window and widgets
"""

from tool_version import VERSION as __version__
