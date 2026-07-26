"""Open the parameterized L-System tree generator in Maya."""

from __future__ import print_function

import importlib
import os
import sys


if "__file__" in globals():
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
else:
    PROJECT_ROOT = r"C:\Users\21346\Desktop\TREE"

if not os.path.isfile(os.path.join(PROJECT_ROOT, "src", "core.py")):
    raise RuntimeError(
        "Cannot locate the tree generator. Update PROJECT_ROOT in launcher.py."
    )

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import core
from src import foliage
from src import maya_foliage
from src import maya_mesh
from src import maya_weather
from src import maya_editing
from src import maya_ui
from src import weather


importlib.reload(core)
importlib.reload(foliage)
importlib.reload(maya_mesh)
importlib.reload(maya_foliage)
importlib.reload(weather)
importlib.reload(maya_weather)
importlib.reload(maya_editing)
importlib.reload(maya_ui)

# Try to open a Maya command port so external tools (e.g. TRAE, custom
# editors) can drive Maya remotely.  Wrapped in try/except because the
# port may already be in use, blocked by firewall, or Maya may be
# running in batch mode without a UI - none of these should abort the
# launcher.
try:
    import maya.cmds as _cmds
    _COMMAND_PORT = "trae_cmdport"
    if not _cmds.commandPort(_COMMAND_PORT, query=True):
        _cmds.commandPort(name=_COMMAND_PORT, sourceType="python")
        print("[launcher] command port opened: " + _COMMAND_PORT)
except Exception as _exc:
    print("[launcher] command port unavailable: " + str(_exc))

maya_ui.show()
