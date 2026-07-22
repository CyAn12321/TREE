"""Maya parameter panel for tree, leaf, flower, and season generation."""

from __future__ import print_function

import random

from . import core
from . import foliage
from . import maya_foliage
from . import maya_mesh
from . import maya_weather
from . import weather


WINDOW_NAME = "LSystemTreeGeneratorWindow"
_CONTROLS = {}
_LAST_ROOT = None


def _maya_cmds():
    try:
        import maya.cmds as cmds
    except ImportError as error:
        raise RuntimeError("The UI must run inside Maya") from error
    return cmds


def _selected_preset_key(cmds):
    selected_label = cmds.optionMenu(_CONTROLS["preset"], query=True, value=True)
    for preset in core.list_presets():
        if preset.label == selected_label:
            return preset.key
    raise RuntimeError("Cannot resolve selected tree preset")


def _selected_season_key(cmds):
    selected_label = cmds.optionMenu(_CONTROLS["season"], query=True, value=True)
    for season in foliage.list_seasons():
        if season.label == selected_label:
            return season.key
    raise RuntimeError("Cannot resolve selected season")


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
    cmds.text(_CONTROLS["description"], edit=True, label=preset.description)


def _apply_season(*unused):
    cmds = _maya_cmds()
    season = foliage.get_season(_selected_season_key(cmds))
    cmds.text(
        _CONTROLS["season_description"],
        edit=True,
        label=season.description,
    )


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
                config=_read_foliage_config(cmds, tree_config.seed),
                parent_root=result["root"],
                name=result["root"].split("|")[-1],
            )

        weather_result = None
        if cmds.checkBox(_CONTROLS["weather"], query=True, value=True):
            weather_result = maya_weather.create_weather_in_maya(
                tree_result=result,
                foliage_result=foliage_result,
                config=_read_weather_config(cmds, tree_config.seed),
                name=result["root"].split("|")[-1],
            )

        _LAST_ROOT = result["root"]
        leaf_count = len(foliage_result["model"].leaves) if foliage_result else 0
        flower_count = (
            len(foliage_result["model"].flowers) if foliage_result else 0
        )
        message = "已生成：{} 枝段 / {} 叶片 / {} 花朵".format(
            len(result["model"].segments),
            leaf_count,
            flower_count,
        )
        if weather_result and weather_result["group"]:
            message += " / 天气动画"
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
            title="L-System 生成失败",
            message=str(error),
            button=["确定"],
            icon="critical",
        )
        raise


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
        cmds.text(_CONTROLS["status"], edit=True, label="已删除上一次生成结果")
    _LAST_ROOT = None


def show():
    cmds = _maya_cmds()
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    window = cmds.window(
        WINDOW_NAME,
        title="L-System 树木、叶片与花朵生成器",
        sizeable=False,
        widthHeight=(500, 860),
    )
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    cmds.text(
        label="L-System 参数化树木与四季器官系统",
        font="boldLabelFont",
        height=28,
    )
    cmds.separator(style="in")

    _CONTROLS["preset"] = cmds.optionMenu(
        label="形态预设",
        changeCommand=_apply_preset,
    )
    for preset in core.list_presets():
        cmds.menuItem(label=preset.label)
    _CONTROLS["description"] = cmds.text(
        label="",
        align="left",
        wordWrap=True,
        height=38,
    )
    _CONTROLS["trunk_radius"] = cmds.floatSliderGrp(
        label="主干半径",
        field=True,
        minValue=0.05,
        maxValue=2.0,
        fieldMinValue=0.01,
        fieldMaxValue=10.0,
        precision=3,
    )
    _CONTROLS["branch_levels"] = cmds.intSliderGrp(
        label="分支层级（含主干）",
        field=True,
        minValue=1,
        maxValue=6,
        fieldMinValue=1,
        fieldMaxValue=7,
    )
    _CONTROLS["branches_per_node"] = cmds.intSliderGrp(
        label="每个节点分叉数",
        field=True,
        minValue=1,
        maxValue=6,
        fieldMinValue=1,
        fieldMaxValue=6,
        value=4,
    )
    _CONTROLS["branch_angle"] = cmds.floatSliderGrp(
        label="分支角度",
        field=True,
        minValue=5.0,
        maxValue=60.0,
        fieldMinValue=1.0,
        fieldMaxValue=80.0,
        precision=1,
    )
    _CONTROLS["seed"] = cmds.intFieldGrp(label="随机种子", value1=17)
    _CONTROLS["radial_sides"] = cmds.intSliderGrp(
        label="枝干截面边数",
        field=True,
        minValue=4,
        maxValue=16,
        value=8,
    )
    _CONTROLS["name"] = cmds.textFieldGrp(
        label="模型名称",
        text="LSystemTree",
    )
    _CONTROLS["tips"] = cmds.checkBox(
        label="生成枝端定位器（后续动画附着点）",
        value=False,
    )

    cmds.separator(style="in")
    cmds.text(label="季节、叶片与花朵", font="boldLabelFont", height=24)
    _CONTROLS["foliage"] = cmds.checkBox(
        label="生成叶片和花朵",
        value=True,
    )
    _CONTROLS["season"] = cmds.optionMenu(
        label="季节",
        changeCommand=_apply_season,
    )
    for season in foliage.list_seasons():
        cmds.menuItem(label=season.label)
    _CONTROLS["season_description"] = cmds.text(
        label="",
        align="left",
        wordWrap=True,
        height=38,
    )
    _CONTROLS["leaf_density"] = cmds.floatSliderGrp(
        label="叶片密度倍率",
        field=True,
        minValue=0.0,
        maxValue=3.0,
        fieldMinValue=0.0,
        fieldMaxValue=10.0,
        value=1.0,
        precision=2,
    )
    _CONTROLS["leaf_size"] = cmds.floatSliderGrp(
        label="叶片尺寸倍率",
        field=True,
        minValue=0.2,
        maxValue=2.0,
        fieldMinValue=0.01,
        fieldMaxValue=5.0,
        value=1.0,
        precision=2,
    )
    _CONTROLS["canopy_spread"] = cmds.floatSliderGrp(
        label="树冠蓬松度",
        field=True,
        minValue=0.0,
        maxValue=2.5,
        fieldMinValue=0.0,
        fieldMaxValue=5.0,
        value=1.0,
        precision=2,
    )
    _CONTROLS["flower_density"] = cmds.floatSliderGrp(
        label="花朵密度倍率",
        field=True,
        minValue=0.0,
        maxValue=3.0,
        fieldMinValue=0.0,
        fieldMaxValue=10.0,
        value=1.0,
        precision=2,
    )
    _CONTROLS["flower_size"] = cmds.floatSliderGrp(
        label="花朵尺寸倍率",
        field=True,
        minValue=0.2,
        maxValue=2.0,
        fieldMinValue=0.01,
        fieldMaxValue=5.0,
        value=1.0,
        precision=2,
    )

    cmds.separator(style="in")
    cmds.text(label="天气与器官飘落动画", font="boldLabelFont", height=24)
    _CONTROLS["weather"] = cmds.checkBox(
        label="生成天气和飘落动画",
        value=False,
    )
    _CONTROLS["weather_start"] = cmds.intFieldGrp(
        label="动画开始帧",
        value1=1,
    )
    _CONTROLS["weather_end"] = cmds.intFieldGrp(
        label="动画结束帧",
        value1=240,
    )
    _CONTROLS["wind_intensity"] = cmds.floatSliderGrp(
        label="风力强度",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.35,
        precision=2,
    )
    _CONTROLS["wind_direction"] = cmds.floatSliderGrp(
        label="风向角度",
        field=True,
        minValue=0.0,
        maxValue=360.0,
        value=25.0,
        precision=1,
    )
    _CONTROLS["rain_intensity"] = cmds.floatSliderGrp(
        label="降雨强度",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.0,
        precision=2,
    )
    _CONTROLS["snow_intensity"] = cmds.floatSliderGrp(
        label="飘雪与积雪强度",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.0,
        precision=2,
    )
    _CONTROLS["leaf_fall_intensity"] = cmds.floatSliderGrp(
        label="落叶强度",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.0,
        precision=2,
    )
    _CONTROLS["flower_fall_intensity"] = cmds.floatSliderGrp(
        label="落花强度",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=0.0,
        precision=2,
    )

    cmds.separator(style="in")
    cmds.button(
        label="生成完整树模型",
        height=36,
        backgroundColor=(0.22, 0.42, 0.20),
        command=_generate,
    )
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    cmds.button(label="换随机种子并生成", command=_new_seed_and_generate)
    cmds.button(label="删除上一次结果", command=_delete_last)
    cmds.setParent("..")
    _CONTROLS["status"] = cmds.text(label="等待生成", align="left", height=24)

    _apply_preset()
    _apply_season()
    cmds.showWindow(window)
    return window
