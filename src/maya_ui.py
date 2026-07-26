# -*- coding: utf-8 -*-
"""Maya parameter panel for tree, leaf, flower, and season generation."""

from __future__ import print_function

import os
import random

from . import core
from . import foliage
from . import maya_foliage
from . import maya_editing
from . import maya_mesh
from . import maya_weather
from . import weather


WINDOW_NAME = "LSystemTreeGeneratorWindow"
BASE_WINDOW_WIDTH = 580
BASE_WINDOW_HEIGHT = 1080


# Tree species catalog: each entry binds a concrete species name to the
# underlying morphological preset (branch shape) and the procedural woody
# flower/leaf species used by the foliage generator.  ``woody_species=None``
# keeps the legacy generic flower/leaf for non-flowering trees.
#
# Botanical references for the four Rosaceae blossoms:
#   Prunus persica   (peach)   -  pink oval petals, orange-red center
#   Prunus serrulata (cherry)  -  pink petals with signature V-notch tip
#   Pyrus spp.       (pear)    -  pure white round petals, dark-purple center
#   Prunus mume      (plum)    -  white/pink/red round petals, yellow center
TREE_SPECIES = {
    "peach_tree": {
        "label": "Peach Tree",
        "description": (
            "Peach blossom (Prunus persica). Pink oval petals with an "
            "orange-red center and long lanceolate leaves."
        ),
        "preset_key": "broadleaf_round",
        "woody_species": "peach",
    },
    "cherry_tree": {
        "label": "Cherry Tree",
        "description": (
            "Cherry blossom (Prunus serrulata). Pale-pink petals with the "
            "signature V-shaped tip notch and ovate leaves."
        ),
        "preset_key": "broadleaf_round",
        "woody_species": "cherry",
    },
    "pear_tree": {
        "label": "Pear Tree",
        "description": (
            "Pear blossom (Pyrus spp.). Pure-white round petals, dark-purple "
            "center, and rounded elliptic leaves."
        ),
        "preset_key": "broadleaf_round",
        "woody_species": "pear",
    },
    "plum_tree": {
        "label": "Plum Tree",
        "description": (
            "Plum blossom (Prunus mume). White-to-red round petals, yellow "
            "center, and ovate leaves."
        ),
        "preset_key": "broadleaf_round",
        "woody_species": "plum",
    },
    # --- Temporarily removed (2026-07): focus development on the four
    # Rosaceae species above.  When non-flowering tree silhouettes are
    # re-introduced, uncomment these entries and restore the corresponding
    # foliage preset tables (LEAF_WIDTH_BY_TREE_PRESET etc.) in foliage.py.
    #
    "weeping_willow": {
        "label": "Weeping Willow",
        "description": (
            "Weeping willow (Salix babylonica). Long drooping branches "
            "with narrow lanceolate leaves; catkins in spring."
        ),
        "preset_key": "willow_weeping",
        "woody_species": "willow",
    },
    # "pyramidal_conifer": {
    #     "label": "Japanese Cedar",
    #     "description": (
    #         "Japanese cedar (Cryptomeria japonica). Evergreen pyramidal "
    #         "conifer with spirally-arranged awl-shaped needle leaves."
    #     ),
    #     "preset_key": "conifer_pyramidal",
    #     "woody_species": None,
    # },
}


SEASON_UI = {
    "spring": (
        "Spring",
        "Fresh young leaves, peak blossoms for all Rosaceae species (peach, "
        "cherry, pear, plum), and bright seasonal colors.",
    ),
    "summer": (
        "Summer",
        "Dense mature foliage with deeper greens; no flowers remain (peach, "
        "cherry, pear, plum all finish blooming by late spring).",
    ),
    "autumn": (
        "Autumn",
        "Reduced foliage density with warm yellow, orange and red leaf "
        "colors; no flowers for any Rosaceae species.",
    ),
    "winter": (
        "Winter",
        "Almost bare branches with very sparse dry leaves; plum (Prunus mume) "
        "alone produces its signature fresh winter blossoms, other species "
        "have none.",
    ),
}


def _species_for(preset_key, woody_species=None):
    """Reverse-lookup the species key from a preset + woody_species pair.

    Used when reloading parameters from an existing tree node so the
    dropdown highlights the right species.  When several species share the
    same preset (the four Rosaceae blossoms all use broadleaf_round), the
    ``woody_species`` disambiguates them.

    Parameters:
        preset_key (str): Tree preset identifier stored on the root.
        woody_species (str|None): Stored woody_species value.
    """
    for species_key, info in TREE_SPECIES.items():
        if info["preset_key"] == preset_key and info["woody_species"] == woody_species:
            return species_key
    # Fall back to the first species matching the preset alone so old
    # scenes without a woody_species still resolve to a valid entry.
    for species_key, info in TREE_SPECIES.items():
        if info["preset_key"] == preset_key:
            return species_key
    return None


def _species_label(species_key):
    """Return the user-facing label for ``species_key`` or None."""
    info = TREE_SPECIES.get(species_key)
    return info["label"] if info else None


def _season_label(season_key):
    """Return the user-facing label for ``season_key`` or None."""
    return SEASON_UI.get(season_key, (None, ""))[0]


def _maya_cmds():
    """Internal helper for maya cmds.
    """
    try:
        import maya.cmds as cmds
    except ImportError:
        # ``raise X from Y`` is Python 3+ syntax  -  Maya's Python 2.7
        # raises SyntaxError at import ("parse error").  Plain raise is
        # the 2.7-compatible form.
        raise RuntimeError("The UI must run inside Maya")
    return cmds


def _logo_path():
    """Return the workspace logo path when the bundled image is available."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = (
        os.path.join(project_root, "GUI_image.png"),
        os.path.join(os.path.dirname(project_root), "GUI_image.png"),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


class TreeGeneratorUI(object):
    """Stateful L-System tree generator UI panel.

    Encapsulates the per-window UI control handles (previously the
    module-level ``_CONTROLS`` dict) and the last-generated root pointer
    (previously ``_LAST_ROOT``) so that two simultaneously-open windows
    would not corrupt each other's state, and so callbacks can be unit
    tested by constructing a UI instance without polluting module
    globals.

    Public entry point is :func:`show` which constructs one
    ``TreeGeneratorUI``, builds the window, and remembers it in
    :attr:`_ACTIVE_UI` only so that ``show()`` can be called again to
    rebuild after the user closes the window.
    """

    def __init__(self):
        """Initialize this object from the supplied configuration or input data.
        """
        self.controls = {}
        self.last_root = None

    # --- Selection helpers -------------------------------------------------

    def _selected_species_key(self, cmds):
        """Return the selected TREE_SPECIES key from the dropdown."""
        selected_label = cmds.optionMenu(self.controls["preset"], query=True, value=True)
        for species_key, info in TREE_SPECIES.items():
            if info["label"] == selected_label:
                return species_key
        raise RuntimeError("Cannot resolve selected tree species")

    def _selected_species_info(self, cmds):
        """Return the full species dict for the dropdown selection."""
        return TREE_SPECIES[self._selected_species_key(cmds)]

    def _selected_season_key(self, cmds):
        """Return the selected season key from the dropdown."""
        selected_label = cmds.optionMenu(self.controls["season"], query=True, value=True)
        for season in foliage.list_seasons():
            if SEASON_UI.get(season.key, (season.label, ""))[0] == selected_label:
                return season.key
        raise RuntimeError("Cannot resolve selected season")

    def _selected_editable_root(self, cmds):
        """Find an editable tree root from the selection or ``last_root``."""
        return maya_editing.find_tree_root_from_selection(self.last_root)

    # --- Change-command callbacks -----------------------------------------

    def _apply_ui_scale(self, *unused):
        """Resize the tool window using a common UI scale factor."""
        cmds = _maya_cmds()
        scale = cmds.floatSliderGrp(
            self.controls["ui_scale"], query=True, value=True
        )
        cmds.window(
            WINDOW_NAME,
            edit=True,
            widthHeight=(
                int(round(BASE_WINDOW_WIDTH * scale)),
                int(round(BASE_WINDOW_HEIGHT * scale)),
            ),
        )

    def apply_preset(self, *unused):
        """Update the trunk parameter sliders from the selected species."""
        cmds = _maya_cmds()
        info = self._selected_species_info(cmds)
        preset = core.get_preset(info["preset_key"])
        defaults = preset.defaults
        cmds.floatSliderGrp(
            self.controls["trunk_radius"], edit=True, value=defaults["trunk_radius"]
        )
        cmds.intSliderGrp(
            self.controls["branch_levels"], edit=True, value=defaults["branch_levels"]
        )
        cmds.intSliderGrp(
            self.controls["branches_per_node"],
            edit=True,
            value=defaults["branches_per_node"],
        )
        cmds.floatSliderGrp(
            self.controls["branch_angle"], edit=True, value=defaults["branch_angle"]
        )
        cmds.floatSliderGrp(
            self.controls["internode_branch_density"],
            edit=True,
            value=defaults["internode_branch_density"],
        )
        cmds.text(self.controls["description"], edit=True, label=info["description"])

    def apply_season(self, *unused):
        """Update the season description label from the selected season."""
        cmds = _maya_cmds()
        season = foliage.get_season(self._selected_season_key(cmds))
        description = SEASON_UI.get(season.key, (season.label, season.description))[1]
        cmds.text(self.controls["season_description"], edit=True, label=description)

    # --- Config readers ----------------------------------------------------

    def _read_tree_config(self, cmds):
        """Internal helper for read tree config.

        Parameters:
            cmds: Input value used by this function.
        """
        info = self._selected_species_info(cmds)
        return core.TreeConfig.from_preset(
            info["preset_key"],
            trunk_radius=cmds.floatSliderGrp(
                self.controls["trunk_radius"], query=True, value=True
            ),
            branch_levels=cmds.intSliderGrp(
                self.controls["branch_levels"], query=True, value=True
            ),
            branches_per_node=cmds.intSliderGrp(
                self.controls["branches_per_node"], query=True, value=True
            ),
            branch_angle=cmds.floatSliderGrp(
                self.controls["branch_angle"], query=True, value=True
            ),
            internode_branch_density=cmds.floatSliderGrp(
                self.controls["internode_branch_density"], query=True, value=True
            ),
            seed=cmds.intFieldGrp(self.controls["seed"], query=True, value1=True),
        )

    def _read_foliage_config(self, cmds, tree_seed):
        """Internal helper for read foliage config.

        Parameters:
            cmds: Input value used by this function.
            tree_seed: Input value used by this function.
        """
        info = self._selected_species_info(cmds)
        return foliage.FoliageConfig(
            season=self._selected_season_key(cmds),
            leaf_density_multiplier=cmds.floatSliderGrp(
                self.controls["leaf_density"], query=True, value=True
            ),
            leaf_size_multiplier=cmds.floatSliderGrp(
                self.controls["leaf_size"], query=True, value=True
            ),
            canopy_spread_multiplier=cmds.floatSliderGrp(
                self.controls["canopy_spread"], query=True, value=True
            ),
            flower_density_multiplier=cmds.floatSliderGrp(
                self.controls["flower_density"], query=True, value=True
            ),
            flower_size_multiplier=cmds.floatSliderGrp(
                self.controls["flower_size"], query=True, value=True
            ),
            seed=tree_seed + 101,
            woody_species=info["woody_species"],
            twig_enabled=cmds.checkBox(
                self.controls["twig_enabled"], query=True, value=True
            ),
            twig_radius_ratio=cmds.floatSliderGrp(
                self.controls["twig_radius_ratio"], query=True, value=True
            ),
            twig_length_ratio=cmds.floatSliderGrp(
                self.controls["twig_length_ratio"], query=True, value=True
            ),
            twig_curvature=cmds.floatSliderGrp(
                self.controls["twig_curvature"], query=True, value=True
            ),
            twig_leaf_ratio=cmds.floatSliderGrp(
                self.controls["twig_leaf_ratio"], query=True, value=True
            ),
        )

    def _read_weather_config(self, cmds, tree_seed):
        """Internal helper for read weather config.

        Parameters:
            cmds: Input value used by this function.
            tree_seed: Input value used by this function.
        """
        return weather.WeatherConfig(
            wind_intensity=cmds.floatSliderGrp(
                self.controls["wind_intensity"], query=True, value=True
            ),
            wind_direction_degrees=cmds.floatSliderGrp(
                self.controls["wind_direction"], query=True, value=True
            ),
            leaf_fall_intensity=cmds.floatSliderGrp(
                self.controls["leaf_fall_intensity"], query=True, value=True
            ),
            flower_fall_intensity=cmds.floatSliderGrp(
                self.controls["flower_fall_intensity"], query=True, value=True
            ),
            start_frame=cmds.intFieldGrp(
                self.controls["weather_start"], query=True, value1=True
            ),
            end_frame=cmds.intFieldGrp(
                self.controls["weather_end"], query=True, value1=True
            ),
            seed=tree_seed + 211,
        )

    def _read_seasonal_cycle_settings(self, cmds):
        """Internal helper for read seasonal cycle settings.

        Parameters:
            cmds: Input value used by this function.
        """
        return (
            cmds.intFieldGrp(
                self.controls["cycle_start"], query=True, value1=True
            ),
            cmds.intFieldGrp(
                self.controls["season_duration"], query=True, value1=True
            ),
            cmds.intFieldGrp(
                self.controls["cycle_transition"], query=True, value1=True
            ),
        )

    # --- Action callbacks --------------------------------------------------

    def generate(self, *unused):
        """Generate a fresh tree (branches + foliage + wind) in Maya.

        Deletes the previous tree first so that stale wind expressions,
        orphaned shading nodes and leftover deformers from the old tree
        do not collide with the new one (parse errors, missing colors).
        """
        cmds = _maya_cmds()
        # Clean up the previous tree BEFORE building the new one.
        # Without this, the old tree's wind expression, deformers,
        # and shading nodes accumulate in the scene and collide with
        # the new tree's nodes  -  causing "parse error / 解析错误"
        # (stale expression referencing deleted deformer) and "no
        # color" (leftover condition node with default black colors
        # blocking the new lambert's color connection).
        self.delete_last()
        # Global orphan sweep: ``delete_last`` only runs when
        # ``self.last_root`` is set (same Maya session with a previous
        # build).  On a FRESH session  -  or after a previous build
        # failed and ``last_root`` was never assigned  -  ``delete_last``
        # does nothing and orphaned wind expressions / condition nodes /
        # materials from earlier sessions survive in the scene.  Each
        # ``connectAttr`` / ``setAttr`` during foliage setup then
        # triggers DG evaluation, the orphaned wind expression tries to
        # parse against a deleted deformer, Maya reports "parse error",
        # and the RuntimeError is swallowed by ``_material_two_sided_leaf``'s
        # ``except RuntimeError: pass``  -  skipping ``colorIfTrue`` /
        # ``colorIfFalse`` setAttr and leaving leaves at default black.
        maya_editing.cleanup_orphaned_lsystem_nodes(verbose=True)
        result = None
        try:
            tree_config = self._read_tree_config(cmds)
            foliage_config = self._read_foliage_config(cmds, tree_config.seed)
            weather_config = self._read_weather_config(cmds, tree_config.seed)
            result = maya_mesh.create_tree_in_maya(
                config=tree_config,
                name=cmds.textFieldGrp(self.controls["name"], query=True, text=True),
                radial_sides=cmds.intSliderGrp(
                    self.controls["radial_sides"], query=True, value=True
                ),
                create_tip_locators=cmds.checkBox(
                    self.controls["tips"], query=True, value=True
                ),
            )

            foliage_result = None
            if cmds.checkBox(self.controls["foliage"], query=True, value=True):
                foliage_result = maya_foliage.create_foliage_in_maya(
                    tree_model=result["model"],
                    config=foliage_config,
                    parent_root=result["root"],
                    name=result["root"].split("|")[-1],
                )
                maya_editing.store_foliage_settings(result["root"], foliage_config)

            weather_result = None
            if cmds.checkBox(self.controls["weather"], query=True, value=True):
                weather_result = maya_weather.create_weather_in_maya(
                    tree_result=result,
                    foliage_result=foliage_result,
                    config=weather_config,
                    name=result["root"].split("|")[-1],
                )
                maya_editing.store_weather_settings(result["root"], weather_config)

            maya_editing.store_tree_settings(
                result["root"],
                tree_config,
                cmds.intSliderGrp(self.controls["radial_sides"], query=True, value=True),
                cmds.checkBox(self.controls["tips"], query=True, value=True),
            )
            self.last_root = result["root"]
            leaf_count = len(foliage_result["model"].leaves) if foliage_result else 0
            flower_count = (
                len(foliage_result["model"].flowers) if foliage_result else 0
            )
            message = "Generated: {} branch segments / {} leaves / {} flowers".format(
                len(result["model"].segments),
                leaf_count,
                flower_count,
            )
            if weather_result and weather_result["group"]:
                message += " / weather animation"
            cmds.text(self.controls["status"], edit=True, label=message)
            cmds.inViewMessage(
                assistMessage=message,
                position="midCenterTop",
                fade=True,
            )
        except Exception as error:
            if result and cmds.objExists(result["root"]):
                maya_weather.delete_weather_nodes(result["root"])
                cmds.delete(result["root"])
            cmds.confirmDialog(
                title="L-System Generation Failed",
                message=str(error),
                button=["OK"],
                icon="critical",
            )
            raise

    def load_selected_tree_parameters(self, *unused):
        """Read parameters from the selected tree and populate the UI."""
        cmds = _maya_cmds()
        root = self._selected_editable_root(cmds)
        tree_config = maya_editing.get_tree_config(root)
        # Resolve the species from the stored preset + woody_species so the
        # dropdown highlights the right entry.  Old scenes without a
        # woody_species fall back to the first species matching the preset.
        foliage_config = maya_editing.get_foliage_config(root)
        stored_woody = getattr(foliage_config, "woody_species", None) if foliage_config else None
        species_key = _species_for(tree_config.preset_key, stored_woody)
        species_label = _species_label(species_key)
        if species_label:
            cmds.optionMenu(self.controls["preset"], edit=True, value=species_label)
        cmds.floatSliderGrp(
            self.controls["trunk_radius"], edit=True, value=tree_config.trunk_radius
        )
        cmds.intSliderGrp(
            self.controls["branch_levels"], edit=True, value=tree_config.branch_levels
        )
        cmds.intSliderGrp(
            self.controls["branches_per_node"],
            edit=True,
            value=tree_config.branches_per_node,
        )
        cmds.floatSliderGrp(
            self.controls["branch_angle"], edit=True, value=tree_config.branch_angle
        )
        cmds.floatSliderGrp(
            self.controls["internode_branch_density"],
            edit=True,
            value=tree_config.internode_branch_density,
        )
        cmds.intFieldGrp(self.controls["seed"], edit=True, value1=tree_config.seed)
        cmds.intSliderGrp(
            self.controls["radial_sides"],
            edit=True,
            value=maya_editing.get_radial_sides(root),
        )
        cmds.checkBox(
            self.controls["tips"],
            edit=True,
            value=maya_editing.get_tip_locator_flag(root),
        )

        foliage_config = maya_editing.get_foliage_config(root)
        if foliage_config:
            season_label = _season_label(foliage_config.season)
            if season_label:
                cmds.optionMenu(self.controls["season"], edit=True, value=season_label)
            cmds.floatSliderGrp(
                self.controls["leaf_density"],
                edit=True,
                value=foliage_config.leaf_density_multiplier,
            )
            cmds.floatSliderGrp(
                self.controls["leaf_size"],
                edit=True,
                value=foliage_config.leaf_size_multiplier,
            )
            cmds.floatSliderGrp(
                self.controls["canopy_spread"],
                edit=True,
                value=foliage_config.canopy_spread_multiplier,
            )
            cmds.floatSliderGrp(
                self.controls["flower_density"],
                edit=True,
                value=foliage_config.flower_density_multiplier,
            )
            cmds.floatSliderGrp(
                self.controls["flower_size"],
                edit=True,
                value=foliage_config.flower_size_multiplier,
            )
            # Twig parameter back-fill (2026-07): restore the saved
            # twig settings so reloading a selected tree shows the
            # actual generation parameters.
            cmds.checkBox(
                self.controls["twig_enabled"],
                edit=True,
                value=getattr(foliage_config, "twig_enabled", True),
            )
            cmds.floatSliderGrp(
                self.controls["twig_radius_ratio"],
                edit=True,
                value=getattr(foliage_config, "twig_radius_ratio", 0.035),
            )
            cmds.floatSliderGrp(
                self.controls["twig_length_ratio"],
                edit=True,
                value=getattr(foliage_config, "twig_length_ratio", 2.5),
            )
            cmds.floatSliderGrp(
                self.controls["twig_curvature"],
                edit=True,
                value=getattr(foliage_config, "twig_curvature", 0.35),
            )
            cmds.floatSliderGrp(
                self.controls["twig_leaf_ratio"],
                edit=True,
                value=getattr(foliage_config, "twig_leaf_ratio", 0.7),
            )

        weather_config = maya_editing.get_weather_config(root)
        if weather_config:
            cmds.floatSliderGrp(
                self.controls["wind_intensity"],
                edit=True,
                value=weather_config.wind_intensity,
            )
            cmds.floatSliderGrp(
                self.controls["wind_direction"],
                edit=True,
                value=weather_config.wind_direction_degrees,
            )
            cmds.floatSliderGrp(
                self.controls["leaf_fall_intensity"],
                edit=True,
                value=weather_config.leaf_fall_intensity,
            )
            cmds.floatSliderGrp(
                self.controls["flower_fall_intensity"],
                edit=True,
                value=weather_config.flower_fall_intensity,
            )
            cmds.intFieldGrp(
                self.controls["weather_start"],
                edit=True,
                value1=weather_config.start_frame,
            )
            cmds.intFieldGrp(
                self.controls["weather_end"],
                edit=True,
                value1=weather_config.end_frame,
            )

        # Description text reflects the resolved species, not just the preset.
        if species_key:
            cmds.text(
                self.controls["description"],
                edit=True,
                label=TREE_SPECIES[species_key]["description"],
            )
        self.apply_season()
        cmds.text(self.controls["status"], edit=True, label="Loaded selected tree parameters")

    def refresh_selected_branches(self, *unused):
        """Rebuild branches for the selected tree, then refresh foliage/weather."""
        cmds = _maya_cmds()
        root = self._selected_editable_root(cmds)
        previous_weather = maya_editing.get_weather_config(root)
        animation_was_enabled = bool(
            previous_weather and previous_weather.any_effect_enabled()
        )
        tree_config = self._read_tree_config(cmds)
        tree_result = maya_editing.regenerate_branches(
            root,
            tree_config,
            radial_sides=cmds.intSliderGrp(
                self.controls["radial_sides"], query=True, value=True
            ),
            create_tip_locators=cmds.checkBox(
                self.controls["tips"], query=True, value=True
            ),
        )
        foliage_result = None
        if cmds.checkBox(self.controls["foliage"], query=True, value=True):
            foliage_result = maya_editing.refresh_foliage(
                root,
                self._read_foliage_config(cmds, tree_config.seed),
            )
        if animation_was_enabled:
            maya_editing.refresh_weather(
                root,
                self._read_weather_config(cmds, tree_config.seed),
            )
        self.last_root = root
        leaf_count = len(foliage_result["model"].leaves) if foliage_result else 0
        cmds.select(root, replace=True)
        cmds.text(
            self.controls["status"],
            edit=True,
            label="Refreshed selected branches: {} segments / {} leaves".format(
                len(tree_result["model"].segments),
                leaf_count,
            ),
        )

    def refresh_selected_foliage(self, *unused):
        """Rebuild foliage for the selected tree using current UI values."""
        cmds = _maya_cmds()
        root = self._selected_editable_root(cmds)
        previous_weather = maya_editing.get_weather_config(root)
        animation_was_enabled = bool(
            previous_weather and previous_weather.any_effect_enabled()
        )
        tree_config = maya_editing.get_tree_config(root)
        result = maya_editing.refresh_foliage(
            root,
            self._read_foliage_config(cmds, tree_config.seed),
        )
        weather_refreshed = False
        if animation_was_enabled:
            maya_editing.refresh_weather(root, self._read_weather_config(cmds, tree_config.seed))
            weather_refreshed = True
        cmds.select(root, replace=True)
        suffix = " / rebuilt weather animation" if weather_refreshed else " / cleared old weather animation"
        cmds.text(
            self.controls["status"],
            edit=True,
            label="Refreshed selected foliage: {} leaves / {} flowers{}".format(
                len(result["model"].leaves),
                len(result["model"].flowers),
                suffix,
            ),
        )

    def refresh_selected_weather(self, *unused):
        """Add or refresh wind animation for the selected tree."""
        cmds = _maya_cmds()
        root = self._selected_editable_root(cmds)
        tree_config = maya_editing.get_tree_config(root)
        result = maya_editing.refresh_weather(
            root,
            self._read_weather_config(cmds, tree_config.seed),
        )
        cmds.select(root, replace=True)
        if result["group"]:
            plan = result["plan"]
            label = (
                "Refreshed weather animation: {} leaves / {} flowers"
                .format(
                    plan["falling_leaf_count"],
                    plan["falling_flower_count"],
                )
            )
        else:
            label = "All weather animation intensities are 0; animation was cleared"
        cmds.text(self.controls["status"], edit=True, label=label)

    def create_selected_seasonal_cycle(self, *unused):
        """Build the complete spring-to-winter animation for the selection."""
        cmds = _maya_cmds()
        root = self._selected_editable_root(cmds)
        tree_config = maya_editing.get_tree_config(root)
        start_frame, season_duration, transition_frames = (
            self._read_seasonal_cycle_settings(cmds)
        )
        result = maya_editing.create_seasonal_cycle_in_maya(
            root=root,
            foliage_config=self._read_foliage_config(cmds, tree_config.seed),
            weather_config=self._read_weather_config(cmds, tree_config.seed),
            start_frame=start_frame,
            season_duration=season_duration,
            transition_frames=transition_frames,
        )
        self.last_root = root
        cmds.select(root, replace=True)
        cmds.text(
            self.controls["status"],
            edit=True,
            label=(
                "Created seasonal cycle: frames {}-{} / 4 seasonal layers"
                .format(result["cycle_start"], result["cycle_end"])
            ),
        )

    def remove_selected_seasonal_cycle(self, *unused):
        """Remove the seasonal cycle and restore the selected season layer."""
        cmds = _maya_cmds()
        root = self._selected_editable_root(cmds)
        tree_config = maya_editing.get_tree_config(root)
        maya_weather.delete_weather_nodes(root)
        maya_editing.delete_seasonal_cycle(root)
        result = maya_editing.refresh_foliage(
            root,
            self._read_foliage_config(cmds, tree_config.seed),
        )
        disabled_weather = weather.WeatherConfig(
            wind_intensity=0.0,
            wind_direction_degrees=cmds.floatSliderGrp(
                self.controls["wind_direction"], query=True, value=True
            ),
            start_frame=cmds.intFieldGrp(
                self.controls["weather_start"], query=True, value1=True
            ),
            end_frame=cmds.intFieldGrp(
                self.controls["weather_end"], query=True, value1=True
            ),
            seed=tree_config.seed + 211,
        )
        maya_editing.store_weather_settings(root, disabled_weather)
        self.last_root = root
        cmds.select(root, replace=True)
        cmds.text(
            self.controls["status"],
            edit=True,
            label=(
                "Removed seasonal cycle; restored {} leaves / {} flowers"
                .format(len(result["model"].leaves), len(result["model"].flowers))
            ),
        )

    def remove_selected_weather(self, *unused):
        """Remove wind animation and store a disabled wind configuration."""
        cmds = _maya_cmds()
        root = self._selected_editable_root(cmds)
        existing = maya_editing.get_weather_config(root)
        tree_config = maya_editing.get_tree_config(root)
        source = existing or self._read_weather_config(cmds, tree_config.seed)
        cleared = weather.WeatherConfig(
            wind_intensity=0.0,
            wind_direction_degrees=source.wind_direction_degrees,
            leaf_fall_intensity=0.0,
            flower_fall_intensity=0.0,
            start_frame=source.start_frame,
            end_frame=source.end_frame,
            seed=source.seed,
        )
        maya_weather.delete_weather_nodes(root)
        maya_editing.store_weather_settings(root, cleared)
        cmds.select(root, replace=True)
        cmds.text(
            self.controls["status"],
            edit=True,
            label="Removed wind animation from the selected tree",
        )

    def new_seed_and_generate(self, *unused):
        """Pick a fresh random seed and run :meth:`generate`."""
        cmds = _maya_cmds()
        cmds.intFieldGrp(
            self.controls["seed"],
            edit=True,
            value1=random.randint(1, 999999),
        )
        self.generate()

    def delete_last(self, *unused):
        """Delete the most recently generated tree (tracked via ``last_root``)."""
        cmds = _maya_cmds()
        if self.last_root and cmds.objExists(self.last_root):
            maya_weather.delete_weather_nodes(self.last_root)
            maya_editing.delete_seasonal_cycle(self.last_root)
            # Also remove orphaned shading nodes (lambert, condition,
            # samplerInfo, file, bump2d, place2dTexture) that were
            # created by the foliage build.  ``cmds.delete(root)`` only
            # removes DAG children  -  shading nodes are DG objects
            # outside the DAG hierarchy, so they survive the root
            # deletion and accumulate in the scene, causing the next
            # tree generation to reuse stale materials with wrong
            # colors or missing connections.
            maya_editing.delete_foliage_nodes(self.last_root)
            cmds.delete(self.last_root)
        cmds.text(self.controls["status"], edit=True, label="Deleted the last generated tree")
        self.last_root = None

    # --- Window construction ----------------------------------------------

    def build(self):
        """Build the window UI and wire callbacks to this instance."""
        cmds = _maya_cmds()
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        window = cmds.window(
            WINDOW_NAME,
            title="L-System Tree Generator",
            sizeable=True,
            resizeToFitChildren=False,
            minimizeButton=True,
            maximizeButton=True,
            widthHeight=(BASE_WINDOW_WIDTH, BASE_WINDOW_HEIGHT),
        )
        cmds.scrollLayout(childResizable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=8)

        logo_path = _logo_path()
        if logo_path:
            cmds.image(image=logo_path, width=560, height=165)
        cmds.text(label="L-System Tree Generator", font="boldLabelFont", height=28)
        self.controls["ui_scale"] = cmds.floatSliderGrp(
            label="UI Scale",
            field=True,
            minValue=0.75,
            maxValue=1.50,
            fieldMinValue=0.50,
            fieldMaxValue=2.00,
            value=1.00,
            precision=2,
            changeCommand=self._apply_ui_scale,
            annotation="Resize the generator window while keeping the UI layout intact",
        )

        # Level 1: Tree Generation
        cmds.frameLayout(
            label="TREE GENERATION",
            collapsable=True,
            collapse=False,
            marginWidth=10,
            marginHeight=8,
        )
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

        # Level 2: Trunk Generation
        cmds.frameLayout(
            label="Trunk Generation",
            collapsable=True,
            collapse=False,
            marginWidth=8,
            marginHeight=6,
        )
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)

        self.controls["preset"] = cmds.optionMenu(
            label="Tree Species",
            changeCommand=self.apply_preset,
        )
        for species_info in TREE_SPECIES.values():
            cmds.menuItem(label=species_info["label"])
        cmds.text(label="Description", align="left", font="smallBoldLabelFont")
        self.controls["description"] = cmds.text(
            label="",
            align="left",
            wordWrap=True,
            height=38,
        )
        self.controls["trunk_radius"] = cmds.floatSliderGrp(
            label="Trunk Radius",
            field=True,
            minValue=0.05,
            maxValue=2.0,
            fieldMinValue=0.01,
            fieldMaxValue=10.0,
            precision=3,
        )
        self.controls["branch_levels"] = cmds.intSliderGrp(
            label="Branch Levels (including trunk)",
            field=True,
            minValue=1,
            maxValue=6,
            fieldMinValue=1,
            fieldMaxValue=7,
        )
        self.controls["branches_per_node"] = cmds.intSliderGrp(
            label="Branches per Node",
            field=True,
            minValue=1,
            maxValue=6,
            fieldMinValue=1,
            fieldMaxValue=6,
            value=4,
        )
        self.controls["branch_angle"] = cmds.floatSliderGrp(
            label="Branch Angle",
            field=True,
            minValue=5.0,
            maxValue=60.0,
            fieldMinValue=1.0,
            fieldMaxValue=80.0,
            precision=1,
        )
        self.controls["internode_branch_density"] = cmds.floatSliderGrp(
            label="Internode Branch Density",
            field=True,
            minValue=0.0,
            maxValue=1.0,
            fieldMinValue=0.0,
            fieldMaxValue=1.0,
            value=0.42,
            precision=2,
            annotation="Probability of recursive lateral buds along F segments",
        )
        self.controls["seed"] = cmds.intFieldGrp(label="Seed", value1=17)
        self.controls["radial_sides"] = cmds.intSliderGrp(
            label="Radial Sides",
            field=True,
            minValue=4,
            maxValue=16,
            value=8,
        )
        cmds.setParent("..")
        cmds.setParent("..")

        # Level 2: Foliage Generation
        cmds.frameLayout(
            label="Leaf and Flower Generation",
            collapsable=True,
            collapse=False,
            marginWidth=8,
            marginHeight=6,
        )
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        self.controls["leaf_density"] = cmds.floatSliderGrp(
            label="Leaf Density",
            field=True,
            minValue=0.0,
            maxValue=3.0,
            fieldMinValue=0.0,
            fieldMaxValue=10.0,
            value=1.0,
            precision=2,
        )
        self.controls["leaf_size"] = cmds.floatSliderGrp(
            label="Leaf Size",
            field=True,
            minValue=0.2,
            maxValue=2.0,
            fieldMinValue=0.01,
            fieldMaxValue=5.0,
            value=1.0,
            precision=2,
        )
        self.controls["canopy_spread"] = cmds.floatSliderGrp(
            label="Canopy Spread",
            field=True,
            minValue=0.0,
            maxValue=2.5,
            fieldMinValue=0.0,
            fieldMaxValue=5.0,
            value=1.0,
            precision=2,
        )
        self.controls["flower_density"] = cmds.floatSliderGrp(
            label="Flower Density",
            field=True,
            minValue=0.0,
            maxValue=3.0,
            fieldMinValue=0.0,
            fieldMaxValue=10.0,
            value=1.0,
            precision=2,
        )
        self.controls["flower_size"] = cmds.floatSliderGrp(
            label="Flower Size",
            field=True,
            minValue=0.2,
            maxValue=2.0,
            fieldMinValue=0.01,
            fieldMaxValue=5.0,
            value=1.0,
            precision=2,
        )
        # --- Twig (fine shoot) controls (2026-07) ---
        # Visible curved twigs grow from each GrowthTip and carry leaves
        # at their tips.  Disabled restores the legacy "leaves on bark"
        # attachment.  Ratios are explained in FoliageConfig comments.
        cmds.separator(height=6, style="in")
        self.controls["twig_enabled"] = cmds.checkBox(
            label="Generate Twigs (fine shoots carrying leaves)",
            value=True,
        )
        self.controls["twig_radius_ratio"] = cmds.floatSliderGrp(
            label="Twig Radius Ratio",
            field=True,
            minValue=0.005,
            maxValue=0.08,
            fieldMinValue=0.001,
            fieldMaxValue=0.15,
            value=0.035,
            precision=3,
        )
        self.controls["twig_length_ratio"] = cmds.floatSliderGrp(
            label="Twig Length Ratio",
            field=True,
            minValue=0.5,
            maxValue=5.0,
            fieldMinValue=0.1,
            fieldMaxValue=10.0,
            value=2.5,
            precision=2,
        )
        self.controls["twig_curvature"] = cmds.floatSliderGrp(
            label="Twig Curvature",
            field=True,
            minValue=0.0,
            maxValue=1.0,
            fieldMinValue=0.0,
            fieldMaxValue=1.0,
            value=0.35,
            precision=2,
        )
        self.controls["twig_leaf_ratio"] = cmds.floatSliderGrp(
            label="Twig Leaf Ratio",
            field=True,
            minValue=0.0,
            maxValue=1.0,
            fieldMinValue=0.0,
            fieldMaxValue=1.0,
            value=0.7,
            precision=2,
        )
        cmds.setParent("..")
        cmds.setParent("..")

        # Level 2: Confirmation Generation
        cmds.frameLayout(
            label="Confirm Generation",
            collapsable=True,
            collapse=False,
            marginWidth=8,
            marginHeight=6,
        )
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self.controls["name"] = cmds.textFieldGrp(label="Model Name", text="LSystemTree")
        cmds.button(
            label="Generate Tree Model",
            height=36,
            backgroundColor=(0.22, 0.42, 0.20),
            command=self.generate,
        )
        cmds.button(
            label="Delete Tree Model",
            height=30,
            backgroundColor=(0.42, 0.22, 0.20),
            command=self.delete_last,
        )
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

        # Level 1: Season System
        cmds.frameLayout(
            label="SEASON SYSTEM",
            collapsable=True,
            collapse=False,
            marginWidth=10,
            marginHeight=8,
        )
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self.controls["season"] = cmds.optionMenu(label="Season", changeCommand=self.apply_season)
        for season in foliage.list_seasons():
            cmds.menuItem(label=SEASON_UI.get(season.key, (season.label, ""))[0])
        cmds.text(label="Season Description", align="left", font="smallBoldLabelFont")
        self.controls["season_description"] = cmds.text(
            label="",
            align="left",
            wordWrap=True,
            height=38,
        )
        cmds.button(
            label="Apply Season",
            height=30,
            backgroundColor=(0.28, 0.40, 0.24),
            command=self.refresh_selected_foliage,
        )
        cmds.setParent("..")
        cmds.setParent("..")

        # Level 1: Seasonal Cycle Animation
        cmds.frameLayout(
            label="SEASONAL CYCLE ANIMATION",
            collapsable=True,
            collapse=False,
            marginWidth=10,
            marginHeight=8,
        )
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        self.controls["cycle_start"] = cmds.intFieldGrp(
            label="Cycle Start",
            value1=1,
        )
        self.controls["season_duration"] = cmds.intFieldGrp(
            label="Frames per Season",
            value1=240,
        )
        self.controls["cycle_transition"] = cmds.intFieldGrp(
            label="Transition Frames",
            value1=60,
        )
        cmds.text(
            label="Creates Spring, Summer, Autumn and Winter foliage layers.",
            align="left",
            font="smallPlainLabelFont",
        )
        cmds.button(
            label="Create Seasonal Cycle Animation",
            height=32,
            backgroundColor=(0.24, 0.38, 0.28),
            command=self.create_selected_seasonal_cycle,
        )
        cmds.button(
            label="Remove Seasonal Cycle",
            height=30,
            backgroundColor=(0.42, 0.28, 0.24),
            command=self.remove_selected_seasonal_cycle,
        )
        cmds.setParent("..")
        cmds.setParent("..")

        # Level 1: Wind Animation
        cmds.frameLayout(
            label="WIND ANIMATION",
            collapsable=True,
            collapse=False,
            marginWidth=10,
            marginHeight=8,
        )
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        self.controls["weather_start"] = cmds.intFieldGrp(
            label="Animation Start",
            value1=1,
        )
        self.controls["weather_end"] = cmds.intFieldGrp(
            label="Animation End",
            value1=240,
        )
        self.controls["wind_intensity"] = cmds.floatSliderGrp(
            label="Wind Intensity",
            field=True,
            minValue=0.0,
            maxValue=1.0,
            value=0.35,
            precision=2,
        )
        self.controls["wind_direction"] = cmds.floatSliderGrp(
            label="Wind Direction",
            field=True,
            minValue=0.0,
            maxValue=360.0,
            value=25.0,
            precision=1,
        )
        self.controls["leaf_fall_intensity"] = cmds.floatSliderGrp(
            label="Falling Leaf Intensity",
            field=True,
            minValue=0.0,
            maxValue=1.0,
            value=0.12,
            precision=2,
        )
        self.controls["flower_fall_intensity"] = cmds.floatSliderGrp(
            label="Falling Flower Intensity",
            field=True,
            minValue=0.0,
            maxValue=1.0,
            value=0.08,
            precision=2,
        )
        cmds.button(
            label="Add / Refresh Weather Animation",
            height=30,
            backgroundColor=(0.24, 0.34, 0.44),
            command=self.refresh_selected_weather,
        )
        cmds.button(
            label="Remove Weather Animation",
            height=30,
            backgroundColor=(0.42, 0.24, 0.24),
            command=self.remove_selected_weather,
        )
        cmds.setParent("..")
        cmds.setParent("..")

        # Internal defaults preserve the existing generation workflow without adding
        # controls outside the requested three top-level sections.
        self.controls["foliage"] = cmds.checkBox(visible=False, value=True)
        self.controls["weather"] = cmds.checkBox(visible=False, value=False)
        self.controls["tips"] = cmds.checkBox(visible=False, value=False)
        self.controls["status"] = cmds.text(label="Ready to generate", align="left", height=24)

        self.apply_preset()
        self.apply_season()
        cmds.showWindow(window)
        # Maya can restore a previous fixed-size window state after showWindow.
        # Re-apply these flags after showing so the native resize border is active.
        cmds.window(
            WINDOW_NAME,
            edit=True,
            sizeable=True,
            resizeToFitChildren=False,
            widthHeight=(BASE_WINDOW_WIDTH, BASE_WINDOW_HEIGHT),
        )
        self.window = window
        return window


# Singleton handle so ``show()`` can be called repeatedly and external
# scripts can still reach the active panel (e.g. to read ``last_root``).
# This is NOT shared mutable state across windows  -  each ``show()`` call
# rebuilds a fresh instance, and the previous instance's controls are
# discarded by ``cmds.deleteUI``.
_ACTIVE_UI = None


def get_active_ui():
    """Return the currently active UI instance, or None if the window is closed."""
    return _ACTIVE_UI


def show():
    """Build and show the L-System Tree Generator window.

    Creates a fresh :class:`TreeGeneratorUI` instance so the controls dict
    and ``last_root`` pointer are never shared across window rebuilds.
    """
    global _ACTIVE_UI
    ui = TreeGeneratorUI()
    ui.build()
    _ACTIVE_UI = ui
    return ui.window
