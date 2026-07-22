"""Open the parameterized L-System tree generator in Maya."""

from __future__ import print_function

import importlib
import os
import sys


if "__file__" in globals():
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
else:
    PROJECT_ROOT = r"D:\未来创新设计\maya_lsystem_tree_generator"

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
from src import maya_ui
from src import weather


importlib.reload(core)
importlib.reload(foliage)
importlib.reload(maya_mesh)
importlib.reload(maya_foliage)
importlib.reload(weather)
importlib.reload(maya_weather)
importlib.reload(maya_ui)

maya_ui.show()
