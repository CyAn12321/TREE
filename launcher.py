"""Open the parameterized L-System tree generator in Maya."""

from __future__ import print_function

import importlib
import os
import sys


def _is_project_root(path):
    """Return whether ``path`` contains the expected TREE source layout.

    Parameters:
        path (str): Candidate project directory to inspect.
    """
    return bool(path) and os.path.isfile(
        os.path.join(path, "src", "core.py")
    )


def _find_project_root():
    """Find the repository without depending on a developer's drive letter.

    Normally Maya executes this file with ``__file__`` available.  For code
    pasted into the Script Editor, also accept the optional
    ``TREE_PROJECT_ROOT`` environment variable, the current directory, and
    entries already present on ``sys.path``.
    """
    candidates = []
    script_path = globals().get("__file__")
    if script_path:
        candidates.append(os.path.dirname(os.path.abspath(script_path)))
    configured_root = os.environ.get("TREE_PROJECT_ROOT")
    if configured_root:
        candidates.append(os.path.abspath(configured_root))
    candidates.append(os.getcwd())
    candidates.extend(sys.path)
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        candidate = os.path.abspath(candidate)
        if candidate in seen:
            continue
        seen.add(candidate)
        if _is_project_root(candidate):
            return candidate
    raise RuntimeError(
        "Cannot locate the TREE project. Run launcher.py from the repository "
        "or set the TREE_PROJECT_ROOT environment variable."
    )


PROJECT_ROOT = _find_project_root()

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# A previous launcher execution may have imported ``src`` from the old
# duplicate checkout.  Remove the package from Maya's module cache before
# importing so the repository selected above is authoritative.
for _module_name in list(sys.modules):
    if _module_name == "src" or _module_name.startswith("src."):
        del sys.modules[_module_name]

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
