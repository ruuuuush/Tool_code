# -*- coding: utf-8 -*-
import os
import runpy
import sys
import types


def onMayaDroppedPythonFile(*args):
    folder = os.path.dirname(os.path.abspath(__file__))
    try:
        surface = types.ModuleType('surface_pcg')
        surface.__dict__.update(runpy.run_path(os.path.join(folder, 'surface_pcg.py')))
        sys.modules['surface_pcg'] = surface
        curve = types.ModuleType('curve_pcg')
        curve.__dict__.update(runpy.run_path(os.path.join(folder, 'curve_pcg.py')))
        ui = runpy.run_path(os.path.join(folder, 'pcg_ui.py'))
        import maya.cmds as cmds
        if cmds.window(curve.WINDOW, exists=True):
            cmds.deleteUI(curve.WINDOW)
        ui['show'](curve, surface)
    except Exception:
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    onMayaDroppedPythonFile()
