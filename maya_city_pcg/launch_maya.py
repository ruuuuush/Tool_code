# -*- coding: utf-8 -*-
import os
import runpy
import types
import traceback


def onMayaDroppedPythonFile(*args):
    folder = os.path.dirname(os.path.abspath(__file__))
    try:
        core = types.ModuleType('city_core')
        core.__dict__.update(runpy.run_path(os.path.join(folder, 'city_core.py')))
        ui = runpy.run_path(os.path.join(folder, 'city_ui.py'))
        ui['show'](core)
    except Exception:
        traceback.print_exc()
        raise


if __name__ == '__main__':
    onMayaDroppedPythonFile()
