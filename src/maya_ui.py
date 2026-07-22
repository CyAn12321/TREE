"""Maya parameter panel for tree, leaf, flower, and season generation."""

from __future__ import print_function

import random

from . import core
from . import foliage
from . import maya_foliage
from . import maya_editing
from . import maya_mesh
from . import maya_weather
from . import weather


WINDOW_NAME = "LSystemTreeGeneratorWindow"
_CONTROLS = {}
_LAST_ROOT = None


PRESET_UI = {
    "broadleaf_round": (
        "Round Broadleaf",
        "Wide branching and dense rounded canopy, suitable for common deciduous trees.",
    ),
    "conifer_pyramidal": (
        "Pyramidal Conifer",
        "Clear central axis with radial side branches, forming a tapered conifer-like silhouette.",
    ),
    "willow_weeping": (
        "Weeping Willow",
        "Long drooping side branches with a downward tropism, suitable for willow-like trees.",
    ),
    "columnar_poplar": (
        "Columnar Poplar",
        "Narrow upward branches that form a slim vertical canopy.",
    ),
}


SEASON_UI = {
    "spring": (
        "Spring",
        "Fresh young leaves, many open flowers, and bright seasonal colors.",
    ),
    "summer": (
        "Summer",
        "Dense mature foliage with deeper greens and only a few remaining flowers.",
    ),
    "autumn": (
        "Autumn",
        "Reduced foliage density, warm leaf colors, and wilted flowers.",
    ),
    "winter": (
        "Winter",
        "Almost bare branches with very sparse dry leaves and no flowers.",
    ),
}


def _maya_cmds():
    try:
        import maya.cmds as cmds
    except ImportError as error:
        raise RuntimeError("The UI must run inside Maya") from error
    return cmds


def _selected_preset_key(cmds):
    selected_label = cmds.optionMenu(_CONTROLS["preset"], query=True, value=True)
    for preset in core.list_presets():
        if PRESET_UI.get(preset.key, (preset.label, ""))[0] == selected_label:
            return preset.key
    raise RuntimeError("Cannot resolve selected tree preset")


def _selected_season_key(cmds):
    selected_label = cmds.optionMenu(_CONTROLS["season"], query=True, value=True)
    for season in foliage.list_seasons():
        if SEASON_UI.get(season.key, (season.label, ""))[0] == selected_label:
            return season.key
    raise RuntimeError("Cannot resolve selected season")


def _preset_label(preset_key):
    return PRESET_UI.get(preset_key, (None, ""))[0]


def _season_label(season_key):
    return SEASON_UI.get(season_key, (None, ""))[0]


def _selected_editable_root(cmds):
    return maya_editing.find_tree_root_from_selection(_LAST_ROOT)


def _apply_preset(*unused):
    cmds = _maya_cmds()
    preset = core.get_preset(_selected_preset_key(cmds))
    defaults = preset.defaults
    cmds.floatSliderGrp(
        _CONTROLS["trunk_radius"], edit=True, value=defaults["trunk_radius"]
    )
    cmds.intSliderGrp(
        _CONTROLS["branch_levels"], edit=True, value=defaults["branch_levels"]
    )
    cmds.intSliderGrp(
        _CONTROLS["branches_per_node"],
        edit=True,
        value=defaults["branches_per_node"],
    )
    cmds.floatSliderGrp(
        _CONTROLS["branch_angle"], edit=True, value=defaults["branch_angle"]
    )
    description = PRESET_UI.get(preset.key, (preset.label, preset.description))[1]
    cmds.text(_CONTROLS["description"], edit=True, label=description)


def _apply_season(*unused):
    cmds = _maya_cmds()
    season = foliage.get_season(_selected_season_key(cmds))
    description = SEASON_UI.get(season.key, (season.label, season.description))[1]
    cmds.text(_CONTROLS["season_description"], edit=True, label=description)


def _read_tree_config(cmds):
    return core.TreeConfig.from_preset(
        _selected_preset_key(cmds),
        trunk_radius=cmds.floatSliderGrp(
            _CONTROLS["trunk_radius"], query=True, value=True
        ),
        branch_levels=cmds.intSliderGrp(
            _CONTROLS["branch_levels"], query=True, value=True
        ),
        branches_per_node=cmds.intSliderGrp(
            _CONTROLS["branches_per_node"], query=True, value=True
        ),
        branch_angle=cmds.floatSliderGrp(
            _CONTROLS["branch_angle"], query=True, value=True
        ),
        seed=cmds.intFieldGrp(_CONTROLS["seed"], query=True, value1=True),
    )


def _read_foliage_config(cmds, tree_seed):
    return foliage.FoliageConfig(
        season=_selected_season_key(cmds),
        leaf_density_multiplier=cmds.floatSliderGrp(
            _CONTROLS["leaf_density"], query=True, value=True
        ),
        leaf_size_multiplier=cmds.floatSliderGrp(
            _CONTROLS["leaf_size"], query=True, value=True
        ),
        canopy_spread_multiplier=cmds.floatSliderGrp(
            _CONTROLS["canopy_spread"], query=True, value=True
        ),
        flower_density_multiplier=cmds.floatSliderGrp(
            _CONTROLS["flower_density"], query=True, value=True
        ),
        flower_size_multiplier=cmds.floatSliderGrp(
            _CONTROLS["flower_size"], query=True, value=True
        ),
        seed=tree_seed + 101,
    )


def _read_weather_config(cmds, tree_seed):
    return weather.WeatherConfig(
        wind_intensity=cmds.floatSliderGrp(
            _CONTROLS["wind_intensity"], query=True, value=True
        ),
        rain_intensity=cmds.floatSliderGrp(
            _CONTROLS["rain_intensity"], query=True, value=True
        ),
        snow_intensity=cmds.floatSliderGrp(
            _CONTROLS["snow_intensity"], query=True, value=True
        ),
        leaf_fall_intensity=cmds.floatSliderGrp(
            _CONTROLS["leaf_fall_intensity"], query=True, value=True
        ),
        flower_fall_intensity=cmds.floatSliderGrp(
            _CONTROLS["flower_fall_intensity"], query=True, value=True
        ),
        wind_direction_degrees=cmds.floatSliderGrp(
            _CONTROLS["wind_direction"], query=True, value=True
        ),
        start_frame=cmds.intFieldGrp(
            _CONTROLS["weather_start"], query=True, value1=True
        ),
        end_frame=cmds.intFieldGrp(
            _CONTROLS["weather_end"], query=True, value1=True
        ),
        seed=tree_seed + 211,
    )


def _generate(*unused):
    global _LAST_ROOT
    cmds = _maya_cmds()
    result = None
    try:
        tree_config = _read_tree_config(cmds)
        foliage_config = _read_foliage_config(cmds, tree_config.seed)
        weather_config = _read_weather_config(cmds, tree_config.seed)
        result = maya_mesh.create_tree_in_maya(
            config=tree_config,
            name=cmds.textFieldGrp(_CONTROLS["name"], query=True, text=True),
            radial_sides=cmds.intSliderGrp(
                _CONTROLS["radial_sides"], query=True, value=True
            ),
            create_tip_locators=cmds.checkBox(
                _CONTROLS["tips"], query=True, value=True
            ),
        )

        foliage_result = None
        if cmds.checkBox(_CONTROLS["foliage"], query=True, value=True):
            foliage_result = maya_foliage.create_foliage_in_maya(
                tree_model=result["model"],
                config=foliage_config,
                parent_root=result["root"],
                name=result["root"].split("|")[-1],
            )
            maya_editing.store_foliage_settings(result["root"], foliage_config)

        weather_result = None
        if cmds.checkBox(_CONTROLS["weather"], query=True, value=True):
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
            cmds.intSliderGrp(_CONTROLS["radial_sides"], query=True, value=True),
            cmds.checkBox(_CONTROLS["tips"], query=True, value=True),
        )
        _LAST_ROOT = result["root"]
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
        cmds.text(_CONTROLS["status"], edit=True, label=message)
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


def _load_selected_tree_parameters(*unused):
    cmds = _maya_cmds()
    root = _selected_editable_root(cmds)
    tree_config = maya_editing.get_tree_config(root)
    preset_label = _preset_label(tree_config.preset_key)
    if preset_label:
        cmds.optionMenu(_CONTROLS["preset"], edit=True, value=preset_label)
    cmds.floatSliderGrp(
        _CONTROLS["trunk_radius"], edit=True, value=tree_config.trunk_radius
    )
    cmds.intSliderGrp(
        _CONTROLS["branch_levels"], edit=True, value=tree_config.branch_levels
    )
    cmds.intSliderGrp(
        _CONTROLS["branches_per_node"],
        edit=True,
        value=tree_config.branches_per_node,
    )
    cmds.floatSliderGrp(
        _CONTROLS["branch_angle"], edit=True, value=tree_config.branch_angle
    )
    cmds.intFieldGrp(_CONTROLS["seed"], edit=True, value1=tree_config.seed)
    cmds.intSliderGrp(
        _CONTROLS["radial_sides"],
        edit=True,
        value=maya_editing.get_radial_sides(root),
    )
    cmds.checkBox(
        _CONTROLS["tips"],
        edit=True,
        value=maya_editing.get_tip_locator_flag(root),
    )

    foliage_config = maya_editing.get_foliage_config(root)
    if foliage_config:
        season_label = _season_label(foliage_config.season)
        if season_label:
            cmds.optionMenu(_CONTROLS["season"], edit=True, value=season_label)
        cmds.floatSliderGrp(
            _CONTROLS["leaf_density"],
            edit=True,
            value=foliage_config.leaf_density_multiplier,
        )
        cmds.floatSliderGrp(
            _CONTROLS["leaf_size"],
            edit=True,
            value=foliage_config.leaf_size_multiplier,
        )
        cmds.floatSliderGrp(
            _CONTROLS["canopy_spread"],
            edit=True,
            value=foliage_config.canopy_spread_multiplier,
        )
        cmds.floatSliderGrp(
            _CONTROLS["flower_density"],
            edit=True,
            value=foliage_config.flower_density_multiplier,
        )
        cmds.floatSliderGrp(
            _CONTROLS["flower_size"],
            edit=True,
            value=foliage_config.flower_size_multiplier,
        )

    weather_config = maya_editing.get_weather_config(root)
    if weather_config:
        cmds.floatSliderGrp(
            _CONTROLS["wind_intensity"],
            edit=True,
            value=weather_config.wind_intensity,
        )
        cmds.floatSliderGrp(
            _CONTROLS["rain_intensity"],
            edit=True,
            value=weather_config.rain_intensity,
        )
        cmds.floatSliderGrp(
            _CONTROLS["snow_intensity"],
            edit=True,
            value=weather_config.snow_intensity,
        )
        cmds.floatSliderGrp(
            _CONTROLS["leaf_fall_intensity"],
            edit=True,
            value=weather_config.leaf_fall_intensity,
        )
        cmds.floatSliderGrp(
            _CONTROLS["flower_fall_intensity"],
            edit=True,
            value=weather_config.flower_fall_intensity,
        )
        cmds.floatSliderGrp(
            _CONTROLS["wind_direction"],
            edit=True,
            value=weather_config.wind_direction_degrees,
        )
        cmds.intFieldGrp(
            _CONTROLS["weather_start"],
            edit=True,
            value1=weather_config.start_frame,
        )
        cmds.intFieldGrp(
            _CONTROLS["weather_end"],
            edit=True,
            value1=weather_config.end_frame,
        )

    preset = core.get_preset(tree_config.preset_key)
    description = PRESET_UI.get(preset.key, (preset.label, preset.description))[1]
    cmds.text(_CONTROLS["description"], edit=True, label=description)
    _apply_season()
    cmds.text(_CONTROLS["status"], edit=True, label="Loaded selected tree parameters")


def _refresh_selected_branches(*unused):
    global _LAST_ROOT
    cmds = _maya_cmds()
    root = _selected_editable_root(cmds)
    tree_config = _read_tree_config(cmds)
    tree_result = maya_editing.regenerate_branches(
        root,
        tree_config,
        radial_sides=cmds.intSliderGrp(
            _CONTROLS["radial_sides"], query=True, value=True
        ),
        create_tip_locators=cmds.checkBox(
            _CONTROLS["tips"], query=True, value=True
        ),
    )
    foliage_result = None
    if cmds.checkBox(_CONTROLS["foliage"], query=True, value=True):
        foliage_result = maya_editing.refresh_foliage(
            root,
            _read_foliage_config(cmds, tree_config.seed),
        )
    if cmds.checkBox(_CONTROLS["weather"], query=True, value=True):
        maya_editing.refresh_weather(root, _read_weather_config(cmds, tree_config.seed))
    _LAST_ROOT = root
    leaf_count = len(foliage_result["model"].leaves) if foliage_result else 0
    cmds.select(root, replace=True)
    cmds.text(
        _CONTROLS["status"],
        edit=True,
        label="Refreshed selected branches: {} segments / {} leaves".format(
            len(tree_result["model"].segments),
            leaf_count,
        ),
    )


def _refresh_selected_foliage(*unused):
    cmds = _maya_cmds()
    root = _selected_editable_root(cmds)
    tree_config = maya_editing.get_tree_config(root)
    result = maya_editing.refresh_foliage(
        root,
        _read_foliage_config(cmds, tree_config.seed),
    )
    weather_refreshed = False
    if cmds.checkBox(_CONTROLS["weather"], query=True, value=True):
        maya_editing.refresh_weather(root, _read_weather_config(cmds, tree_config.seed))
        weather_refreshed = True
    cmds.select(root, replace=True)
    suffix = " / rebuilt weather animation" if weather_refreshed else " / cleared old weather animation"
    cmds.text(
        _CONTROLS["status"],
        edit=True,
        label="Refreshed selected foliage: {} leaves / {} flowers{}".format(
            len(result["model"].leaves),
            len(result["model"].flowers),
            suffix,
        ),
    )


def _refresh_selected_weather(*unused):
    cmds = _maya_cmds()
    root = _selected_editable_root(cmds)
    tree_config = maya_editing.get_tree_config(root)
    result = maya_editing.refresh_weather(
        root,
        _read_weather_config(cmds, tree_config.seed),
    )
    cmds.select(root, replace=True)
    label = "Refreshed weather animation for the selected tree" if result["group"] else "All weather strengths are 0; weather animation was cleared"
    cmds.text(_CONTROLS["status"], edit=True, label=label)


def _new_seed_and_generate(*unused):
    cmds = _maya_cmds()
    cmds.intFieldGrp(
        _CONTROLS["seed"],
        edit=True,
        value1=random.randint(1, 999999),
    )
    _generate()


def _delete_last(*unused):
    global _LAST_ROOT
    cmds = _maya_cmds()
    if _LAST_ROOT and cmds.objExists(_LAST_ROOT):
        maya_weather.delete_weather_nodes(_LAST_ROOT)
        cmds.delete(_LAST_ROOT)
        cmds.text(_CONTROLS["status"], edit=True, label="Deleted the last generated tree")
    cmds.text(_CONTROLS["status"], edit=True, label="Deleted the last generated tree")
    _LAST_ROOT = None


def show():
    cmds = _maya_cmds()
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    window = cmds.window(
        WINDOW_NAME,
        title="L-System Tree, Foliage, and Flower Generator",
        sizeable=False,
        widthHeight=(560, 900),
    )
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    cmds.text(
        label="Parametric L-System Tree and Seasonal Organ System",
        font="boldLabelFont",
        height=28,
    )
    cmds.separator(style="in")

    _CONTROLS["preset"] = cmds.optionMenu(
        label="Tree Preset",
        changeCommand=_apply_preset,
    )
    for preset in core.list_presets():
        cmds.menuItem(label=PRESET_UI.get(preset.key, (preset.label, ""))[0])
    _CONTROLS["description"] = cmds.text(
        label="",
        align="left",
        wordWrap=True,
        height=38,
    )
    _CONTROLS["trunk_radius"] = cmds.floatSliderGrp(
        label="Trunk Radius",
        field=True,
        minValue=0.05,
        maxValue=2.0,
        fieldMinValue=0.01,
        fieldMaxValue=10.0,
        precision=3,
    )
    _CONTROLS["branch_levels"] = cmds.intSliderGrp(
        label="Branch Levels (including trunk)",
        field=True,
        minValue=1,
        maxValue=6,
        fieldMinValue=1,
        fieldMaxValue=7,
    )
    _CONTROLS["branches_per_node"] = cmds.intSliderGrp(
        label="Branches per Node",
        field=True,
        minValue=1,
        maxValue=6,
        fieldMinValue=1,
        fieldMaxValue=6,
        value=4,
    )
    _CONTROLS["branch_angle"] = cmds.floatSliderGrp(
        label="Branch Angle",
        field=True,
        minValue=5.0,
        maxValue=60.0,
        fieldMinValue=1.0,
        fieldMaxValue=80.0,
        precision=1,
    )
    _CONTROLS["seed"] = cmds.intFieldGrp(label="Random Seed", value1=17)
    _CONTROLS["radial_sides"] = cmds.intSliderGrp(
        label="Branch Radial Sides",
        field=True,
        minValue=4,
        maxValue=16,
        value=8,
    )
    _CONTROLS["name"] = cmds.textFieldGrp(
        label="Model Name",
        text="LSystemTree",
    )
    _CONTROLS["tips"] = cmds.checkBox(
        label="Create Tip Locators for Attachments",
        value=False,
    )

    cmds.separator(style="in")
    cmds.text(label="Seasonal Leaves and Flowers", font="boldLabelFont", height=24)
    _CONTROLS["foliage"] = cmds.checkBox(
        label="Generate Leaves and Flowers",
        value=True,
    )
    _CONTROLS["season"] = cmds.optionMenu(
        label="Season",
        changeCommand=_apply_season,
    )
    for season in foliage.list_seasons():
        cmds.menuItem(label=SEASON_UI.get(season.key, (season.label, ""))[0])
    _CONTROLS["season_description"] = cmds.text(
        label="",
        align="left",
        wordWrap=True,
        height=38,
    )
    _CONTROLS["leaf_density"] = cmds.floatSliderGrp(
        label="Leaf Density Multiplier",
        field=True,
        minValue=0.0,
        maxValue=3.0,
        fieldMinValue=0.0,
        fieldMaxValue=10.0,
        value=1.0,
        precision=2,
    )
    _CONTROLS["leaf_size"] = cmds.floatSliderGrp(
        label="Leaf Size Multiplier",
        field=True,
        minValue=0.2,
        maxValue=2.0,
        fieldMinValue=0.01,
        fieldMaxValue=5.0,
        value=1.0,
        precision=2,
    )
    _CONTROLS["canopy_spread"] = cmds.floatSliderGrp(
        label="Canopy Fluffiness",
        field=True,
        minValue=0.0,
        maxValue=2.5,
        fieldMinValue=0.0,
        fieldMaxValue=5.0,
        value=1.0,
        precision=2,
    )
    _CONTROLS["flower_density"] = cmds.floatSliderGrp(
        label="Flower Density Multiplier",
        field=True,
        minValue=0.0,
        maxValue=3.0,
        fieldMinValue=0.0,
        fieldMaxValue=10.0,
        value=1.0,
        precision=2,
    )
    _CONTROLS["flower_size"] = cmds.floatSliderGrp(
        label="Flower Size Multiplier",
        field=True,
        minValue=0.2,
        maxValue=2.0,
        fieldMinValue=0.01,
        fieldMaxValue=5.0,
        value=1.0,
        precision=2,
    )

    cmds.separator(style="in")
    cmds.text(label="Weather and Falling Organ Animation", font="boldLabelFont", height=24)
    _CONTROLS["weather"] = cmds.checkBox(
        label="Generate Weather and Falling Organ Animation",
        value=False,
    )
    _CONTROLS["weather_start"] = cmds.intFieldGrp(
        label="Animation Start Frame",
        value1=1,
    )
    _CONTROLS["weather_end"] = cmds.intFieldGrp(
        label="Animation End Frame",
        value1=240,
    )
    _CONTROLS["wind_intensity"] = cmds.floatSliderGrp(
        label="Wind Intensity",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.35,
        precision=2,
    )
    _CONTROLS["wind_direction"] = cmds.floatSliderGrp(
        label="Wind Direction Angle",
        field=True,
        minValue=0.0,
        maxValue=360.0,
        value=25.0,
        precision=1,
    )
    _CONTROLS["rain_intensity"] = cmds.floatSliderGrp(
        label="Rain Intensity",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.0,
        precision=2,
    )
    _CONTROLS["snow_intensity"] = cmds.floatSliderGrp(
        label="Snowfall and Accumulation Intensity",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.0,
        precision=2,
    )
    _CONTROLS["leaf_fall_intensity"] = cmds.floatSliderGrp(
        label="Falling Leaf Intensity",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.0,
        precision=2,
    )
    _CONTROLS["flower_fall_intensity"] = cmds.floatSliderGrp(
        label="Falling Flower Intensity",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.0,
        precision=2,
    )

    cmds.separator(style="in")
    cmds.button(
        label="Generate Complete Tree Model",
        height=36,
        backgroundColor=(0.22, 0.42, 0.20),
        command=_generate,
    )
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    cmds.button(label="Randomize Seed and Generate", command=_new_seed_and_generate)
    cmds.button(label="Delete Last Result", command=_delete_last)
    cmds.setParent("..")
    cmds.separator(style="in")
    cmds.text(label="Editable Tree: select the root or any child object", font="boldLabelFont", height=24)
    cmds.button(label="Load Selected Tree Parameters", command=_load_selected_tree_parameters)
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1)
    cmds.button(label="Refresh Branches", command=_refresh_selected_branches)
    cmds.button(label="Refresh Foliage", command=_refresh_selected_foliage)
    cmds.button(label="Refresh Weather Animation", command=_refresh_selected_weather)
    cmds.setParent("..")
    _CONTROLS["status"] = cmds.text(label="Ready to generate", align="left", height=24)

    _apply_preset()
    _apply_season()
    cmds.showWindow(window)
    return window
