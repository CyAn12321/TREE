"""Editable-scene helpers for generated L-System trees.

The generator can rebuild procedural layers while preserving a separate
user-owned override group under the tree root.
"""

from __future__ import division, print_function

import json

from . import core
from . import foliage
from . import maya_foliage
from . import maya_mesh
from . import maya_weather
from . import weather


TREE_MARKER = "lsystemEditableTree"
BRANCH_MARKER = "lsystemBranchesManaged"
TIP_MARKER = "lsystemTipsManaged"
FOLIAGE_MARKER = "lsystemFoliageManaged"
USER_GROUP_MARKER = "lsystemUserOverrides"

TREE_CONFIG_ATTR = "treeConfigJson"
FOLIAGE_CONFIG_ATTR = "foliageConfigJson"
WEATHER_CONFIG_ATTR = "weatherConfigJson"
RADIAL_SIDES_ATTR = "radialSides"
TIP_LOCATORS_ATTR = "createTipLocators"


def _config_payload(config):
    if hasattr(config, "as_dict"):
        return dict(config.as_dict())
    return dict(config.__dict__)


def config_to_json(config):
    return json.dumps(_config_payload(config), sort_keys=True)


def tree_config_from_json(text):
    return core.TreeConfig(**json.loads(text))


def foliage_config_from_json(text):
    return foliage.FoliageConfig(**json.loads(text))


def weather_config_from_json(text):
    return weather.WeatherConfig(**json.loads(text))


def _maya_cmds():
    try:
        import maya.cmds as cmds
    except ImportError as error:
        raise RuntimeError("Editable tree operations must run inside Maya") from error
    return cmds


def _set_string_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, dataType="string")
    cmds.setAttr(node + "." + attr, value, type="string")


def _get_string_attr(cmds, node, attr):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        return None
    return cmds.getAttr(node + "." + attr)


def _set_bool_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="bool")
    cmds.setAttr(node + "." + attr, bool(value))


def _set_long_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="long")
    cmds.setAttr(node + "." + attr, int(value))


def mark_transform(cmds, node, attr):
    _set_bool_attr(cmds, node, attr, True)


def _direct_children(cmds, root):
    return cmds.listRelatives(
        root,
        children=True,
        type="transform",
        fullPath=True,
    ) or []


def _children_with_marker(cmds, root, marker):
    return [
        child
        for child in _direct_children(cmds, root)
        if cmds.attributeQuery(marker, node=child, exists=True)
    ]


def ensure_user_overrides_group(root):
    cmds = _maya_cmds()
    existing = _children_with_marker(cmds, root, USER_GROUP_MARKER)
    if existing:
        return existing[0]
    root_name = root.split("|")[-1]
    group = cmds.group(empty=True, name=root_name + "_User_Overrides", parent=root)
    mark_transform(cmds, group, USER_GROUP_MARKER)
    return group


def store_tree_settings(root, tree_config, radial_sides=8, create_tip_locators=False):
    cmds = _maya_cmds()
    _set_bool_attr(cmds, root, TREE_MARKER, True)
    _set_string_attr(cmds, root, TREE_CONFIG_ATTR, config_to_json(tree_config))
    _set_long_attr(cmds, root, RADIAL_SIDES_ATTR, radial_sides)
    _set_bool_attr(cmds, root, TIP_LOCATORS_ATTR, create_tip_locators)
    ensure_user_overrides_group(root)


def store_foliage_settings(root, foliage_config):
    cmds = _maya_cmds()
    _set_string_attr(cmds, root, FOLIAGE_CONFIG_ATTR, config_to_json(foliage_config))


def store_weather_settings(root, weather_config):
    cmds = _maya_cmds()
    _set_string_attr(cmds, root, WEATHER_CONFIG_ATTR, config_to_json(weather_config))


def get_tree_config(root):
    cmds = _maya_cmds()
    text = _get_string_attr(cmds, root, TREE_CONFIG_ATTR)
    if not text:
        raise RuntimeError("The selected object is not an editable L-System tree; tree parameters are missing.")
    return tree_config_from_json(text)


def get_foliage_config(root):
    cmds = _maya_cmds()
    text = _get_string_attr(cmds, root, FOLIAGE_CONFIG_ATTR)
    return foliage_config_from_json(text) if text else None


def get_weather_config(root):
    cmds = _maya_cmds()
    text = _get_string_attr(cmds, root, WEATHER_CONFIG_ATTR)
    return weather_config_from_json(text) if text else None


def get_radial_sides(root, default=8):
    cmds = _maya_cmds()
    if cmds.attributeQuery(RADIAL_SIDES_ATTR, node=root, exists=True):
        return int(cmds.getAttr(root + "." + RADIAL_SIDES_ATTR))
    return int(default)


def get_tip_locator_flag(root):
    cmds = _maya_cmds()
    if cmds.attributeQuery(TIP_LOCATORS_ATTR, node=root, exists=True):
        return bool(cmds.getAttr(root + "." + TIP_LOCATORS_ATTR))
    return False


def find_tree_root_from_selection(fallback_root=None):
    cmds = _maya_cmds()
    candidates = cmds.ls(selection=True, long=True) or []
    if fallback_root and cmds.objExists(fallback_root):
        candidates.append(fallback_root)
    for candidate in candidates:
        current = candidate
        while current and cmds.objExists(current):
            if cmds.attributeQuery(TREE_MARKER, node=current, exists=True):
                return current
            parents = cmds.listRelatives(current, parent=True, fullPath=True) or []
            current = parents[0] if parents else None
    raise RuntimeError("Please select a generated L-System tree or any of its child objects first.")


def _delete_children_with_marker(cmds, root, marker):
    for child in _children_with_marker(cmds, root, marker):
        if cmds.objExists(child):
            cmds.delete(child)


def delete_foliage_nodes(root):
    cmds = _maya_cmds()
    _delete_children_with_marker(cmds, root, FOLIAGE_MARKER)


def _managed_branch_mesh(cmds, root):
    marked = _children_with_marker(cmds, root, BRANCH_MARKER)
    if marked:
        return marked[0]
    root_name = root.split("|")[-1]
    for child in _direct_children(cmds, root):
        if child.split("|")[-1] == root_name + "_Branches":
            return child
    return None


def _managed_foliage_group(cmds, root):
    marked = _children_with_marker(cmds, root, FOLIAGE_MARKER)
    if marked:
        return marked[0]
    return None


def _foliage_meshes(cmds, group):
    if not group or not cmds.objExists(group):
        return [], []
    descendants = cmds.listRelatives(
        group,
        allDescendents=True,
        type="transform",
        fullPath=True,
    ) or []
    leaf_meshes = [
        node
        for node in descendants
        if "_Leaves_" in node and cmds.listRelatives(node, shapes=True)
    ]
    flower_meshes = [
        node
        for node in descendants
        if "_Flowers_" in node and cmds.listRelatives(node, shapes=True)
    ]
    return leaf_meshes, flower_meshes


def _tree_result_from_root(root, tree_config=None):
    cmds = _maya_cmds()
    config = tree_config or get_tree_config(root)
    model = core.generate_tree(config)
    mesh = _managed_branch_mesh(cmds, root)
    return {
        "root": root,
        "mesh": mesh,
        "tip_group": None,
        "model": model,
        "attachment_points": model.attachment_points,
    }


def _foliage_result_from_root(root, tree_model):
    cmds = _maya_cmds()
    config = get_foliage_config(root)
    group = _managed_foliage_group(cmds, root)
    if not config or not group:
        return None
    model = foliage.generate_foliage(tree_model, config)
    leaf_meshes, flower_meshes = _foliage_meshes(cmds, group)
    return {
        "group": group,
        "meshes": leaf_meshes + flower_meshes,
        "leaf_meshes": leaf_meshes,
        "flower_meshes": flower_meshes,
        "flower_center_mesh": None,
        "model": model,
    }


def regenerate_branches(root, tree_config, radial_sides=None, create_tip_locators=None):
    cmds = _maya_cmds()
    radial_sides = get_radial_sides(root) if radial_sides is None else radial_sides
    if create_tip_locators is None:
        create_tip_locators = get_tip_locator_flag(root)
    root_name = root.split("|")[-1]
    _delete_children_with_marker(cmds, root, BRANCH_MARKER)
    _delete_children_with_marker(cmds, root, TIP_MARKER)
    delete_foliage_nodes(root)
    maya_weather.delete_weather_nodes(root)

    temporary = maya_mesh.create_tree_in_maya(
        config=tree_config,
        name=root_name + "_Rebuild",
        radial_sides=radial_sides,
        create_tip_locators=create_tip_locators,
    )
    mesh = temporary["mesh"]
    tip_group = temporary["tip_group"]
    new_mesh = cmds.parent(mesh, root)[0]
    new_mesh = cmds.rename(new_mesh, root_name + "_Branches")
    mark_transform(cmds, new_mesh, BRANCH_MARKER)
    if tip_group and cmds.objExists(tip_group):
        new_tips = cmds.parent(tip_group, root)[0]
        new_tips = cmds.rename(new_tips, root_name + "_Tips")
        mark_transform(cmds, new_tips, TIP_MARKER)
    if cmds.objExists(temporary["root"]):
        cmds.delete(temporary["root"])
    store_tree_settings(root, tree_config, radial_sides, create_tip_locators)
    return _tree_result_from_root(root, tree_config)


def refresh_foliage(root, foliage_config):
    tree_result = _tree_result_from_root(root)
    maya_weather.delete_weather_nodes(root)
    delete_foliage_nodes(root)
    result = maya_foliage.create_foliage_in_maya(
        tree_model=tree_result["model"],
        config=foliage_config,
        parent_root=root,
        name=root.split("|")[-1],
    )
    store_foliage_settings(root, foliage_config)
    return result


def refresh_weather(root, weather_config):
    tree_result = _tree_result_from_root(root)
    foliage_result = _foliage_result_from_root(root, tree_result["model"])
    result = maya_weather.create_weather_in_maya(
        tree_result=tree_result,
        foliage_result=foliage_result,
        config=weather_config,
        name=root.split("|")[-1],
    )
    store_weather_settings(root, weather_config)
    return result
