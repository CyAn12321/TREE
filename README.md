# TREE

Procedural tree generation for Maya with parameterized modeling, seasons,
weather animation, and a unified user interface.

## Project modules

- `src/core.py` — trunk and branch generation (Member A)
- `src/foliage.py` — leaves, flowers, and seasonal logic (Member B)
- `src/weather.py` — wind, rain, snow, falling leaves, and petals (Member C)
- `ui/main_ui.py` — Maya UI, module integration, and presentation support (Member D)
- `assets/` — reference images, materials, textures, and Maya assets
- `docs/` — presentations, ethics review, methodology diagrams, and references

## Maya development setup

Clone the repository, then add its folders to Maya's Python path:

```python
import sys
import importlib

PROJECT_ROOT = "D:/MyProject/TREE"
for folder in (f"{PROJECT_ROOT}/src", f"{PROJECT_ROOT}/ui"):
    if folder not in sys.path:
        sys.path.append(folder)

import main_ui
importlib.reload(main_ui)
main_ui.show_window()
```

## Team workflow

Keep `main` stable. Develop in feature branches such as
`feature/core-generation`, `feature/foliage-season`, `feature/weather-anim`,
and `feature/ui-integration`, then open a pull request for review.
