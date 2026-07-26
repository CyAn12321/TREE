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
SEASONAL_CYCLE_MARKER = "lsystemSeasonalCycleManaged"
SEASONAL_FALL_MARKER = "lsystemSeasonalFallManaged"
SEASONAL_CYCLE_CONFIG_ATTR = "seasonalCycleConfigJson"
SEASON_KEYS = ("spring", "summer", "autumn", "winter")


def _config_payload(config):
    if hasattr(config, "as_dict"):
        return dict(config.as_dict())
    return dict(config.__dict__)


def config_to_json(config):
    """Serialize a config object to a sorted JSON string.

    Parameters:
        config (TreeConfig|FoliageConfig|WeatherConfig): Object with
            ``as_dict()`` or ``__dict__``.
    """
    return json.dumps(_config_payload(config), sort_keys=True)


def tree_config_from_json(text):
    """Reconstruct a TreeConfig from its JSON serialization.

    Parameters:
        text (str): JSON output of ``config_to_json``.
    """
    return core.TreeConfig(**json.loads(text))


def foliage_config_from_json(text):
    """Reconstruct a FoliageConfig from its JSON serialization.

    Parameters:
        text (str): JSON output of ``config_to_json``.
    """
    return foliage.FoliageConfig(**json.loads(text))


def weather_config_from_json(text):
    """Reconstruct a WeatherConfig from its JSON serialization.

    Parameters:
        text (str): JSON output of ``config_to_json``.
    """
    return weather.WeatherConfig(**json.loads(text))


def _maya_cmds():
    try:
        import maya.cmds as cmds
    except ImportError:
        # ``raise X from Y`` is Python 3+ syntax  -  on Maya's Python 2.7
        # it raises SyntaxError at import time ("parse error"), which is
        # exactly the parse error users see when switching seasons.
        # Use the Python 2.7-compatible plain raise form.
        raise RuntimeError("Editable tree operations must run inside Maya")
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
    """Return the user-owned override group under ``root``, creating it if needed.

    Parameters:
        root (str): Maya transform of the editable tree root.
    """
    cmds = _maya_cmds()
    existing = _children_with_marker(cmds, root, USER_GROUP_MARKER)
    if existing:
        return existing[0]
    root_name = root.split("|")[-1]
    group = cmds.group(empty=True, name=root_name + "_User_Overrides", parent=root)
    mark_transform(cmds, group, USER_GROUP_MARKER)
    return group


def store_tree_settings(root, tree_config, radial_sides=8, create_tip_locators=False):
    """Persist tree generation parameters as attributes on ``root``.

    Parameters:
        root (str): Maya transform of the editable tree root.
        tree_config (TreeConfig): Tree parameters to serialize.
        radial_sides (int): Cross-section vertex count to remember.
        create_tip_locators (bool): Whether tip locators are enabled.
    """
    cmds = _maya_cmds()
    _set_bool_attr(cmds, root, TREE_MARKER, True)
    _set_string_attr(cmds, root, TREE_CONFIG_ATTR, config_to_json(tree_config))
    _set_long_attr(cmds, root, RADIAL_SIDES_ATTR, radial_sides)
    _set_bool_attr(cmds, root, TIP_LOCATORS_ATTR, create_tip_locators)
    ensure_user_overrides_group(root)


def store_foliage_settings(root, foliage_config):
    """Persist foliage parameters as a JSON attribute on ``root``.

    Parameters:
        root (str): Maya transform of the editable tree root.
        foliage_config (FoliageConfig): Foliage parameters to serialize.
    """
    cmds = _maya_cmds()
    _set_string_attr(cmds, root, FOLIAGE_CONFIG_ATTR, config_to_json(foliage_config))


def store_weather_settings(root, weather_config):
    """Persist weather parameters as a JSON attribute on ``root``.

    Parameters:
        root (str): Maya transform of the editable tree root.
        weather_config (WeatherConfig): Weather parameters to serialize.
    """
    cmds = _maya_cmds()
    _set_string_attr(cmds, root, WEATHER_CONFIG_ATTR, config_to_json(weather_config))


def get_tree_config(root):
    """Reconstruct a TreeConfig from the JSON attribute on ``root``.

    Parameters:
        root (str): Maya transform of the editable tree root.
    """
    cmds = _maya_cmds()
    text = _get_string_attr(cmds, root, TREE_CONFIG_ATTR)
    if not text:
        raise RuntimeError("The selected object is not an editable L-System tree; tree parameters are missing.")
    return tree_config_from_json(text)


def get_foliage_config(root):
    """Reconstruct a FoliageConfig from the JSON attribute on ``root``.

    Parameters:
        root (str): Maya transform of the editable tree root.
    """
    cmds = _maya_cmds()
    text = _get_string_attr(cmds, root, FOLIAGE_CONFIG_ATTR)
    return foliage_config_from_json(text) if text else None


def get_weather_config(root):
    """Reconstruct a WeatherConfig from the JSON attribute on ``root``.

    Parameters:
        root (str): Maya transform of the editable tree root.
    """
    cmds = _maya_cmds()
    text = _get_string_attr(cmds, root, WEATHER_CONFIG_ATTR)
    return weather_config_from_json(text) if text else None


def build_seasonal_schedule(start_frame=1, season_duration=240, transition_frames=60):
    """Return a validated four-season frame schedule.

    The schedule is pure Python so it can be tested without Maya.  Visibility
    switches happen at each season boundary; the transition window is used by
    the seasonal falling-organ layer.
    """
    start_frame = int(start_frame)
    season_duration = int(season_duration)
    transition_frames = int(transition_frames)
    if season_duration < 24:
        raise ValueError("season_duration must be at least 24 frames")
    if transition_frames < 0 or transition_frames >= season_duration:
        raise ValueError("transition_frames must be smaller than season_duration")
    schedule = []
    for index, season_key in enumerate(SEASON_KEYS):
        season_start = start_frame + index * season_duration
        schedule.append({
            "season": season_key,
            "start_frame": season_start,
            "end_frame": season_start + season_duration - 1,
            "transition_start": (
                season_start if index == 0
                else season_start - transition_frames
            ),
            "transition_end": season_start + transition_frames,
        })
    return tuple(schedule)


def get_radial_sides(root, default=8):
    """Read the stored radial_sides attribute from ``root``.

    Parameters:
        root (str): Maya transform of the editable tree root.
        default (int): Fallback value when the attribute is missing.
    """
    cmds = _maya_cmds()
    if cmds.attributeQuery(RADIAL_SIDES_ATTR, node=root, exists=True):
        return int(cmds.getAttr(root + "." + RADIAL_SIDES_ATTR))
    return int(default)


def get_tip_locator_flag(root):
    """Read the stored createTipLocators attribute from ``root``.

    Parameters:
        root (str): Maya transform of the editable tree root.
    """
    cmds = _maya_cmds()
    if cmds.attributeQuery(TIP_LOCATORS_ATTR, node=root, exists=True):
        return bool(cmds.getAttr(root + "." + TIP_LOCATORS_ATTR))
    return False


def find_tree_root_from_selection(fallback_root=None):
    """Walk up from the current selection to find an editable tree root.

    Parameters:
        fallback_root (str|None): Node path appended to the candidate
            list when no editable ancestor is found in the selection.
    """
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


def _delete_foliage_shading_nodes(cmds, root):
    """Delete orphaned shading nodes left by previous foliage builds.

    ``create_foliage_in_maya`` creates lambert / file / bump2d /
    condition / samplerInfo / place2dTexture nodes whose names follow
    fixed patterns.  These nodes are NOT parented under the foliage
    group, so ``_delete_children_with_marker`` does not remove them.
    Without this cleanup every season switch accumulates a new set of
    shading nodes  -  after 3-4 switches the dependency graph becomes
    unstable and Maya crashes (typically on the winter->spring
    transition where flower prototype materials are reactivated).
    """
    tree_name = root.split("|")[-1]
    # Patterns cover: leaf materials (per-season), flower materials
    # (per-season), flower-center materials (per-season), and woody
    # flower prototype materials (per-tree, shared across seasons).
    patterns = [
        "LSystemLeaf_*",
        "LSystemFlower_*",
        "LSystemFlowerCenter_*",
        # Prototype materials now include season_key:
        # ``{tree}_{season}_FlowerProto_{color}_*``
        "{}_*_FlowerProto_*".format(tree_name),
    ]
    nodes_to_delete = []
    for pattern in patterns:
        matched = cmds.ls(pattern) or []
        for node in matched:
            if cmds.objExists(node):
                nodes_to_delete.append(node)
    # Also catch the associated utility nodes (condition, samplerInfo,
    # file, bump2d, place2dTexture) whose names derive from the
    # material names above.
    utility_patterns = [
        "LSystemLeaf_*_FaceSwitch",
        "LSystemLeaf_*_Sampler",
        "LSystemLeaf_*VeinFile*",
        "LSystemLeaf_*VeinBump",
        "{}_*_FlowerProto_*VeinFile*".format(tree_name),
        "{}_*_FlowerProto_*VeinBump".format(tree_name),
    ]
    for pattern in utility_patterns:
        matched = cmds.ls(pattern) or []
        for node in matched:
            if cmds.objExists(node):
                nodes_to_delete.append(node)
    # Delete nodes ONE BY ONE instead of batch-deleting.  ``cmds.delete``
    # on a list is NOT atomic  -  if node N fails to delete (locked,
    # still referenced, etc.), nodes N+1..end are never reached and the
    # whole call raises RuntimeError, which the previous ``except: pass``
    # silently swallowed.  The leftover nodes then collided with the
    # next season's freshly-created materials (wrong colors, "attribute
    # already connected", parse errors).  Per-node deletion with
    # individual try/except ensures every node gets attempted even when
    # one fails, and survivors are explicitly logged so the failure is
    # visible in the script editor instead of being hidden.
    unique_nodes = []
    seen = set()
    for node in nodes_to_delete:
        if node not in seen:
            seen.add(node)
            unique_nodes.append(node)
    survivors = []
    for node in unique_nodes:
        try:
            if cmds.objExists(node):
                cmds.delete(node)
        except RuntimeError:
            survivors.append(node)
    # Survivors (nodes that could not be removed) are silently ignored;
    # the next build will retry deletion.


def delete_foliage_nodes(root):
    """Delete the foliage group under ``root`` (managed by ``FOLIAGE_MARKER``).

    Also cleans up the orphaned shading nodes (lambert / file / bump2d
    / condition / samplerInfo / place2dTexture) created for the foliage
    so that repeated season switches do not accumulate dependency-graph
    nodes and destabilise Maya.

    Parameters:
        root (str): Maya transform of the editable tree root.
    """
    cmds = _maya_cmds()
    # Order matters: delete the foliage MESHES first so the shading
    # nodes are no longer referenced by any geometry, THEN delete the
    # shading nodes themselves.  The previous order (shading first,
    # meshes second) left lambert/condition nodes still connected to
    # live meshes, so ``cmds.delete`` refused to remove them, the
    # ``except RuntimeError: pass`` in ``_delete_foliage_shading_nodes``
    # swallowed the error, and the leftover nodes collided with the
    # next season's freshly-created materials (wrong leaf colors,
    # "attribute already connected" errors, parse errors from stale
    # expression references).
    _delete_children_with_marker(cmds, root, FOLIAGE_MARKER)
    _delete_foliage_shading_nodes(cmds, root)


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


def _seasonal_cycle_groups(cmds, root, marker):
    return _children_with_marker(cmds, root, marker)


def delete_seasonal_cycle(root):
    """Delete the generated four-season foliage and transition layer."""
    cmds = _maya_cmds()
    deleted = 0
    for marker in (SEASONAL_FALL_MARKER, SEASONAL_CYCLE_MARKER):
        for group in _seasonal_cycle_groups(cmds, root, marker):
            if cmds.objExists(group):
                try:
                    cmds.delete(group)
                    deleted += 1
                except RuntimeError:
                    pass
    return deleted


def _copy_season_foliage_config(base_config, season_key):
    payload = dict(base_config.__dict__)
    payload["season"] = season_key
    return foliage.FoliageConfig(**payload)


def _copy_cycle_weather_config(base_config, start_frame, end_frame, seed,
                               leaf_fall_intensity=0.0,
                               flower_fall_intensity=0.0):
    return weather.WeatherConfig(
        wind_intensity=base_config.wind_intensity,
        wind_direction_degrees=base_config.wind_direction_degrees,
        start_frame=start_frame,
        end_frame=end_frame,
        seed=seed,
        frames_per_second=base_config.frames_per_second,
        rain_intensity=0.0,
        snow_intensity=0.0,
        leaf_fall_intensity=leaf_fall_intensity,
        flower_fall_intensity=flower_fall_intensity,
        max_falling_leaves=base_config.max_falling_leaves,
        max_falling_flowers=base_config.max_falling_flowers,
    )


def _key_season_visibility(cmds, group, schedule, index):
    start_frame = schedule[index]["start_frame"]
    end_frame = schedule[index]["end_frame"]
    cmds.setAttr(group + ".visibility", False)
    cmds.setKeyframe(group + ".visibility", time=start_frame - 1, value=0)
    cmds.setKeyframe(group + ".visibility", time=start_frame, value=1)
    cmds.setKeyframe(group + ".visibility", time=end_frame, value=1)
    if index < len(schedule) - 1:
        next_start = schedule[index + 1]["start_frame"]
        cmds.setKeyframe(group + ".visibility", time=next_start - 1, value=1)
        cmds.setKeyframe(group + ".visibility", time=next_start, value=0)
    else:
        cmds.setKeyframe(group + ".visibility", time=end_frame + 1, value=0)


def _create_seasonal_fall_layer(
    root,
    cycle_group,
    tree_result,
    season_results,
    schedule,
    weather_config,
    transition_frames,
    name,
):
    cmds = _maya_cmds()
    fall_group = cmds.group(
        empty=True,
        name=name + "_SeasonalFalling",
        parent=cycle_group,
    )
    mark_transform(cmds, fall_group, SEASONAL_FALL_MARKER)
    managed = []
    # Falling organs are emitted from the outgoing season at each boundary.
    # The winter->spring transition is left to the next cycle so the final
    # frame does not abruptly create objects outside the playback range.
    fall_multipliers = (
        (0.20, 1.00),  # spring -> summer: flowers mostly drop
        (0.18, 0.35),  # summer -> autumn: a few remaining flowers/leaves
        (1.00, 0.0),   # autumn -> winter: leaves drop
    )
    for index in range(3):
        season_result = season_results[index]
        season_info = schedule[index]
        transition_end = season_info["end_frame"]
        transition_start = max(
            season_info["start_frame"],
            transition_end - transition_frames + 1,
        )
        leaf_intensity = weather_config.leaf_fall_intensity * fall_multipliers[index][0]
        flower_intensity = weather_config.flower_fall_intensity * fall_multipliers[index][1]
        if leaf_intensity <= 0.0 and flower_intensity <= 0.0:
            continue
        transition_config = _copy_cycle_weather_config(
            weather_config,
            transition_start,
            transition_end,
            weather_config.seed + 31 * (index + 1),
            leaf_fall_intensity=leaf_intensity,
            flower_fall_intensity=flower_intensity,
        )
        plan = weather.build_weather_plan(
            tree_result["model"],
            season_result["model"],
            transition_config,
        )
        managed.extend(maya_weather._create_falling_organs(
            cmds,
            season_result,
            plan,
            fall_group,
            name + "_" + season_info["season"],
            "leaf",
            duration_override=transition_frames,
        ))
        managed.extend(maya_weather._create_falling_organs(
            cmds,
            season_result,
            plan,
            fall_group,
            name + "_" + season_info["season"],
            "flower",
            duration_override=transition_frames,
        ))
    maya_weather._register_managed_nodes(cmds, fall_group, managed)
    return fall_group, managed


def create_seasonal_cycle_in_maya(
    root,
    foliage_config,
    weather_config,
    start_frame=1,
    season_duration=240,
    transition_frames=60,
):
    """Build a spring-to-winter animation without replacing the tree trunk.

    Four foliage groups are generated under one managed cycle group.  Their
    visibility is keyed over the schedule, while one shared wind layer bends
    the branch mesh and every seasonal foliage mesh.  Seasonal falling organs
    are generated only during the first three season boundaries.
    """
    cmds = _maya_cmds()
    schedule = build_seasonal_schedule(
        start_frame, season_duration, transition_frames,
    )
    tree_result = _tree_result_from_root(root)
    root_name = root.split("|")[-1]

    # Remove both the old single-season layer and any previous cycle before
    # creating a fresh, self-contained cycle.
    maya_weather.delete_weather_nodes(root)
    delete_seasonal_cycle(root)
    delete_foliage_nodes(root)

    cycle_group = cmds.group(
        empty=True,
        name=root_name + "_SeasonalCycle",
        parent=root,
    )
    mark_transform(cmds, cycle_group, SEASONAL_CYCLE_MARKER)
    _set_string_attr(
        cmds,
        cycle_group,
        SEASONAL_CYCLE_CONFIG_ATTR,
        json.dumps({
            "start_frame": int(start_frame),
            "season_duration": int(season_duration),
            "transition_frames": int(transition_frames),
            "seasons": list(SEASON_KEYS),
        }, sort_keys=True),
    )

    season_results = []
    all_meshes = []
    all_leaf_meshes = []
    all_flower_meshes = []
    all_twig_meshes = []
    for index, season_key in enumerate(SEASON_KEYS):
        season_config = _copy_season_foliage_config(
            foliage_config, season_key,
        )
        season_result = maya_foliage.create_foliage_in_maya(
            tree_model=tree_result["model"],
            config=season_config,
            parent_root=cycle_group,
            name=root_name + "_" + season_key.title(),
        )
        season_results.append(season_result)
        all_meshes.extend(season_result.get("meshes", ()))
        all_leaf_meshes.extend(season_result.get("leaf_meshes", ()))
        all_flower_meshes.extend(season_result.get("flower_meshes", ()))
        all_twig_meshes.extend(season_result.get("twig_meshes", ()))
        _key_season_visibility(
            cmds,
            season_result["group"],
            schedule,
            index,
        )

    combined_foliage = {
        "meshes": all_meshes,
        "leaf_meshes": all_leaf_meshes,
        "flower_meshes": all_flower_meshes,
        "twig_meshes": all_twig_meshes,
        "model": season_results[0]["model"],
    }
    cycle_start = schedule[0]["start_frame"]
    cycle_end = schedule[-1]["end_frame"]
    cycle_weather = _copy_cycle_weather_config(
        weather_config,
        cycle_start,
        cycle_end,
        weather_config.seed,
        leaf_fall_intensity=0.0,
        flower_fall_intensity=0.0,
    )
    wind_result = maya_weather.create_weather_in_maya(
        tree_result=tree_result,
        foliage_result=combined_foliage,
        config=cycle_weather,
        name=root_name,
    )
    fall_group, fall_nodes = _create_seasonal_fall_layer(
        root,
        cycle_group,
        tree_result,
        season_results,
        schedule,
        weather_config,
        transition_frames,
        root_name,
    )
    store_foliage_settings(root, foliage_config)
    store_weather_settings(root, cycle_weather)
    cmds.playbackOptions(minTime=cycle_start, maxTime=cycle_end)
    cmds.currentTime(cycle_start, edit=True)
    cmds.select(root, replace=True)
    return {
        "cycle_group": cycle_group,
        "fall_group": fall_group,
        "season_groups": [result["group"] for result in season_results],
        "season_results": season_results,
        "schedule": schedule,
        "weather_result": wind_result,
        "fall_nodes": fall_nodes,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
    }


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
        if (
            (
                "_Flowers_" in node
                or "_FlowerCenters" in node
                # Woody flowers are Maya instances named like
                # ``*_FlowerProto_*_Inst_0001`` rather than the legacy
                # merged ``*_Flowers_00`` meshes.  They must also be
                # supplied to the wind deformer after a refresh.
                or ("_FlowerProto_" in node and "_Inst_" in node)
            )
            and cmds.listRelatives(node, shapes=True)
        )
    ]
    twig_meshes = [
        node
        for node in descendants
        if "_Twigs" in node and cmds.listRelatives(node, shapes=True)
    ]
    return leaf_meshes, flower_meshes, twig_meshes


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
    leaf_meshes, flower_meshes, twig_meshes = _foliage_meshes(cmds, group)
    return {
        "group": group,
        "meshes": leaf_meshes + flower_meshes + twig_meshes,
        "leaf_meshes": leaf_meshes,
        "flower_meshes": flower_meshes,
        "twig_meshes": twig_meshes,
        "flower_center_mesh": None,
        "model": model,
    }


def regenerate_branches(root, tree_config, radial_sides=None, create_tip_locators=None):
    """Rebuild the branch mesh (and tips) under ``root`` while keeping user overrides.

    Parameters:
        root (str): Maya transform of the editable tree root.
        tree_config (TreeConfig): New tree configuration to apply.
        radial_sides (int|None): Cross-section vertex count.  None reads
            the previously stored value from ``root``.
        create_tip_locators (bool|None): Tip-locator toggle.  None reads
            the previously stored value from ``root``.
    """
    cmds = _maya_cmds()
    radial_sides = get_radial_sides(root) if radial_sides is None else radial_sides
    if create_tip_locators is None:
        create_tip_locators = get_tip_locator_flag(root)
    root_name = root.split("|")[-1]
    delete_seasonal_cycle(root)
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
    """Rebuild the foliage layer under ``root`` while keeping user overrides.

    Parameters:
        root (str): Maya transform of the editable tree root.
        foliage_config (FoliageConfig): New foliage configuration.
    """
    tree_result = _tree_result_from_root(root)
    maya_weather.delete_weather_nodes(root)
    delete_seasonal_cycle(root)
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
    """Rebuild the weather animation under ``root`` while keeping user overrides.

    Parameters:
        root (str): Maya transform of the editable tree root.
        weather_config (WeatherConfig): New weather configuration.
    """
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


# Patterns for ALL LSystem-related DG nodes (shading nodes, utility nodes,
# expression nodes).  Used by ``cleanup_orphaned_lsystem_nodes`` to sweep
# the entire scene  -  not scoped to a specific tree root  -  so that
# orphaned nodes from a previous Maya session (where ``last_root`` was
# lost) are removed before a fresh generation.  Without this sweep, a
# leftover ``*_WindExpression`` referencing a deleted bend deformer
# raises "parse error" every time Maya evaluates the DG (which happens
# on every ``connectAttr`` / ``setAttr``), and the RuntimeError it
# propagates is silently swallowed by ``except RuntimeError: pass`` in
# ``_material_two_sided_leaf``, leaving the condition node's
# ``colorIfTrue`` / ``colorIfFalse`` at default black  -  the user sees
# "no color" on the leaves.
_ORPHAN_SHADING_PATTERNS = (
    # Leaf / flower / flower-center lambert materials (per-season).
    "LSystemLeaf_*",
    "LSystemFlower_*",
    "LSystemFlowerCenter_*",
    # Woody flower prototype materials (per-tree, shared across seasons).
    "LSystemTree_*_FlowerProto_*",
    # Two-sided leaf condition + samplerInfo nodes.
    "LSystemLeaf_*_FaceSwitch",
    "LSystemLeaf_*_Sampler",
    # Vein bump-mapping utility nodes (leaves and flower petals).
    "LSystemLeaf_*VeinFile*",
    "LSystemLeaf_*VeinBump",
    "LSystemTree_*_FlowerProto_*VeinFile*",
    "LSystemTree_*_FlowerProto_*VeinBump",
    # place2dTexture companions for the vein file nodes.
    "LSystemLeaf_*VeinFile*Place",
    "LSystemTree_*_FlowerProto_*VeinFile*Place",
    # Bark material (shared, singleton).
    "LSystemTree_Bark_MAT",
    "LSystemTree_Bark_MATSG",
)

_ORPHAN_EXPRESSION_PATTERNS = (
    "*_WindExpression",
    "*_OrganFlutterExpression",
)


def _collect_nodes_by_pattern(cmds, patterns):
    """Gather all scene nodes matching any of the given glob patterns.

    Parameters:
        cmds: Maya cmds module.
        patterns (tuple[str]): Glob patterns to match.

    Returns:
        list[str]: De-duplicated list of existing node names.
    """
    collected = []
    seen = set()
    for pattern in patterns:
        for node in cmds.ls(pattern) or []:
            if node not in seen and cmds.objExists(node):
                seen.add(node)
                collected.append(node)
    return collected


def cleanup_orphaned_lsystem_nodes(verbose=False):
    """Remove ALL orphaned LSystem nodes from the scene.

    Unlike ``delete_foliage_nodes`` and ``delete_weather_nodes``, this
    function does NOT require a tree root  -  it sweeps the entire scene
    by name pattern.  This is essential for the case where
    ``TreeGeneratorUI.last_root`` is None (fresh Maya session, or after
    a previous build failed and left orphaned DG nodes behind).  In that
    state ``delete_last`` does nothing, and the orphaned wind expression
    / condition / material nodes accumulate and collide with the new
    build, causing "parse error" and "no color" symptoms.

    Parameters:
        verbose (bool): When True, print a summary of deleted / surviving
            nodes to the returned dict so the caller can inspect what was cleaned up.

    Returns:
        dict: ``{"deleted": int, "survivors": list[str]}``  -  count of
        nodes successfully removed and list of nodes that could not be
        deleted (locked, referenced, etc.).
    """
    cmds = _maya_cmds()
    # Delete expressions FIRST.  A leftover ``*_WindExpression`` that
    # references a deleted bend deformer is the primary cause of the
    # "parse error" messages: every DG evaluation (triggered by
    # ``connectAttr`` / ``setAttr`` during foliage material setup) tries
    # to re-evaluate the broken expression, and the parse failure raises
    # RuntimeError in Python  -  which ``_material_two_sided_leaf``
    # silently swallows, skipping the ``colorIfTrue`` / ``colorIfFalse``
    # ``setAttr`` calls and leaving the condition node at default black.
    # Removing the expression before building new materials eliminates
    # the spurious DG errors entirely.
    expression_nodes = _collect_nodes_by_pattern(cmds, _ORPHAN_EXPRESSION_PATTERNS)
    shading_nodes = _collect_nodes_by_pattern(cmds, _ORPHAN_SHADING_PATTERNS)
    # Also sweep any orphaned Weather groups (transform + contents).
    weather_groups = cmds.ls("*_Weather", type="transform") or []
    all_nodes = []
    seen = set()
    for node in expression_nodes + shading_nodes + weather_groups:
        if node not in seen:
            seen.add(node)
            all_nodes.append(node)

    deleted = 0
    survivors = []
    for node in all_nodes:
        try:
            if cmds.objExists(node):
                cmds.delete(node)
                deleted += 1
        except RuntimeError:
            survivors.append(node)

    # Verbose logging removed; survivors are returned in the result dict
    # for callers that need to inspect them.

    return {"deleted": deleted, "survivors": survivors}
