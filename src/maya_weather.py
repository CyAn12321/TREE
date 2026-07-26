# -*- coding: utf-8 -*-
"""Maya-native wind sway animation.

The old animation layer mixed wind with rain, snow, snow cover, falling
leaves, falling flowers, particles, fields and collisions.  This module is a
clean first animation layer: it creates one shared canopy bend layer driven
by an expression, so branches, leaves and flowers move together.

All nodes are placed under a managed animation group and are registered via a
message attribute, so refreshing animation removes previous deformers,
expressions and falling-organ particle systems before rebuilding them.
"""

from __future__ import division, print_function

import json
import math

from . import maya_foliage
from .weather import WeatherConfig, build_weather_plan


# Animation provenance: the bounded multi-frequency sway is informed by the
# vegetation-wind techniques discussed in GPU Gems 3, Chapter 6.  This file
# implements a project-specific Maya bend/deformer and keyed-instance layer;
# it does not copy source code from that reference.


ANIMATION_MARKER = "lsystemAnimationManaged"
LEGACY_WEATHER_MARKER = "lsystemWeatherManaged"
ANIMATION_GROUP_SUFFIX = "_WindAnimation"
EXPRESSION_SUFFIX = "_WindExpression"


def _maya_cmds():
    """Internal helper for maya cmds.
    """
    try:
        import maya.cmds as cmds
    except ImportError:
        # Keep this syntax compatible with Maya's Python 2.7 builds.
        raise RuntimeError("Weather animation must be created inside Maya")
    return cmds




def _safe_set(cmds, plug, *values, **kwargs):
    """Internal helper for safe set.

    Parameters:
        cmds: Input value used by this function.
        plug: Input value used by this function.
        values: Input value used by this function.
        **kwargs: Input value used by this function.
    """
    if cmds.objExists(plug):
        cmds.setAttr(plug, *values, **kwargs)


def _set_string_attr(cmds, node, attr, value):
    """Internal helper for set string attr.

    Parameters:
        cmds: Input value used by this function.
        node: Input value used by this function.
        attr: Input value used by this function.
        value: Input value used by this function.
    """
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, dataType="string")
    cmds.setAttr(node + "." + attr, value, type="string")


def _set_bool_attr(cmds, node, attr, value):
    """Internal helper for set bool attr.

    Parameters:
        cmds: Input value used by this function.
        node: Input value used by this function.
        attr: Input value used by this function.
        value: Input value used by this function.
    """
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="bool")
    cmds.setAttr(node + "." + attr, bool(value))


def _mesh_targets(cmds, tree_result, foliage_result):
    """Return all geometry targets for the shared tree-canopy sway."""
    candidates = [tree_result.get("mesh")]
    if foliage_result:
        candidates.extend(foliage_result.get("meshes", ()))
        candidates.extend(foliage_result.get("twig_meshes", ()))
    targets = []
    seen = set()
    for target in candidates:
        if target and target not in seen and cmds.objExists(target):
            seen.add(target)
            targets.append(target)
    return targets


def _delete_node(cmds, node):
    """Internal helper for delete node.

    Parameters:
        cmds: Input value used by this function.
        node: Input value used by this function.
    """
    try:
        if node and cmds.objExists(node):
            cmds.delete(node)
    except RuntimeError:
        # Locked nodes should not prevent the rest of the managed animation
        # from being removed.  The next cleanup pass will try again.
        pass


def _direct_children(cmds, root):
    """Internal helper for direct children.

    Parameters:
        cmds: Input value used by this function.
        root: Input value used by this function.
    """
    return cmds.listRelatives(
        root,
        children=True,
        type="transform",
        fullPath=True,
    ) or []


def _is_animation_group(cmds, node):
    """Internal helper for is animation group.

    Parameters:
        cmds: Input value used by this function.
        node: Input value used by this function.
    """
    return (
        cmds.attributeQuery(ANIMATION_MARKER, node=node, exists=True)
        or cmds.attributeQuery(LEGACY_WEATHER_MARKER, node=node, exists=True)
    )


def _delete_group_and_managed_nodes(cmds, group):
    """Delete a current or legacy animation group and every registered node."""
    nodes = []
    if cmds.attributeQuery("managedNodes", node=group, exists=True):
        nodes = cmds.listConnections(
            group + ".managedNodes",
            source=True,
            destination=False,
        ) or []

    # Delete DG nodes individually.  Maya can abort a batch delete when one
    # node is locked, leaving later stale expressions behind.
    for node in set(nodes):
        _delete_node(cmds, node)
    _delete_node(cmds, group)


def _delete_orphan_wind_expressions(cmds):
    """Remove old tree and foliage wind expressions."""
    for pattern in ("*_WindExpression", "*_OrganFlutterExpression"):
        for expression in cmds.ls(pattern, type="expression") or []:
            _delete_node(cmds, expression)


def _delete_orphan_falling_nodes(cmds):
    """Remove dynamic falling nodes left by an interrupted old build."""
    patterns = (
        "*_FallingLeafParticles*",
        "*_FallingFlowerParticles*",
        "*_LeafSurfaceEmitter*",
        "*_FlowerSurfaceEmitter*",
        "*_LeafGravity",
        "*_FlowerGravity",
        "*_LeafAir",
        "*_FlowerAir",
        "*_LeafInstancer",
        "*_FlowerInstancer",
        "*_FallingLeafPrototype*",
        "*_FallingFlowerPrototype*",
    )
    for pattern in patterns:
        for node in cmds.ls(pattern) or []:
            _delete_node(cmds, node)


def delete_weather_nodes(root):
    """Delete all old weather nodes and the current wind animation below root.

    The public name is retained because editable-scene code and older Maya
    scenes already call it.  Its behavior now means "delete the whole managed
    animation layer", including the legacy particle-based layer.
    """
    cmds = _maya_cmds()
    for child in _direct_children(cmds, root):
        if _is_animation_group(cmds, child):
            _delete_group_and_managed_nodes(cmds, child)
    # Expressions are DG nodes and may have survived after a root was deleted
    # manually in an older scene.
    _delete_orphan_wind_expressions(cmds)
    _delete_orphan_falling_nodes(cmds)


def _register_managed_nodes(cmds, group, nodes):
    # Maya can invalidate a short DAG name after a poly operation creates or
    # renames a sibling.  Resolve the group again before querying attributes;
    # otherwise refresh ends with "no object named ..._WindAnimation" even
    # though the animation itself was created and can play.
    """Internal helper for register managed nodes.

    Parameters:
        cmds: Input value used by this function.
        group: Input value used by this function.
        nodes: Input value used by this function.
    """
    resolved_groups = cmds.ls(group, long=True) or []
    if not resolved_groups:
        return
    group = resolved_groups[0]
    if not cmds.attributeQuery("managedNodes", node=group, exists=True):
        cmds.addAttr(
            group,
            longName="managedNodes",
            attributeType="message",
            multi=True,
        )
    slot = 0
    for node in nodes:
        if not node or not cmds.objExists(node):
            continue
        plug = group + ".managedNodes[{}]".format(slot)
        try:
            cmds.connectAttr(node + ".message", plug, force=True)
            slot += 1
        except RuntimeError:
            pass


def _create_bend_layer(
    cmds,
    targets,
    plan,
    group,
    name,
    deformer_suffix,
    expression_suffix,
    amplitude,
    frequency,
):
    """Internal helper for create bend layer.

    Parameters:
        cmds: Input value used by this function.
        targets: Input value used by this function.
        plan: Input value used by this function.
        group: Input value used by this function.
        name: Input value used by this function.
        deformer_suffix: Input value used by this function.
        expression_suffix: Input value used by this function.
        amplitude: Input value used by this function.
        frequency: Input value used by this function.
    """
    if not targets or amplitude <= 0.0:
        return []

    deformer, handle = cmds.nonLinear(
        targets,
        type="bend",
        name=name + deformer_suffix,
    )

    center = plan["center"]
    cmds.xform(
        handle,
        worldSpace=True,
        translation=(center[0], plan["ground_y"], center[2]),
        rotation=(0.0, plan.config.wind_direction_degrees, 0.0),
    )
    _safe_set(cmds, handle + ".scaleY", max(plan["height"], 0.1))
    _safe_set(cmds, handle + ".visibility", False)
    _safe_set(cmds, deformer + ".lowBound", plan["wind_low_bound"])
    _safe_set(cmds, deformer + ".highBound", plan["wind_high_bound"])
    _safe_set(cmds, deformer + ".curvature", 0.0)
    cmds.parent(handle, group)

    phase = plan["wind_phase"]
    signed_amplitude = amplitude * plan["wind_curvature_sign"]
    expression_name = name + expression_suffix
    expression_body = (
        "{0}.curvature = {1:.6f} * "
        "sin(frame * {2:.6f} + {3:.6f});"
    ).format(
        deformer,
        signed_amplitude,
        frequency,
        phase,
    )
    expression = cmds.expression(
        name=expression_name,
        alwaysEvaluate=True,
        unitConversion="all",
        string=expression_body,
    )
    return [deformer, handle, expression]




def _organ_rotation(source):
    """Internal helper for organ rotation.

    Parameters:
        source: Input value used by this function.
    """
    direction = source.direction
    horizontal = math.sqrt(direction[0] ** 2 + direction[2] ** 2)
    pitch = math.degrees(math.atan2(horizontal, max(direction[1], 0.001)))
    yaw = math.degrees(math.atan2(direction[0], direction[2]))
    return pitch, yaw, float(source.azimuth)


def _set_keyed_value(cmds, node, attribute, start_frame, end_frame, start, end):
    """Internal helper for set keyed value.

    Parameters:
        cmds: Input value used by this function.
        node: Input value used by this function.
        attribute: Input value used by this function.
        start_frame: Input value used by this function.
        end_frame: Input value used by this function.
        start: Input value used by this function.
        end: Input value used by this function.
    """
    plug = node + "." + attribute
    cmds.setAttr(plug, start)
    cmds.setKeyframe(plug, time=start_frame, value=start)
    cmds.setKeyframe(plug, time=end_frame, value=end)


def _set_keyed_curve(cmds, node, attribute, keys):
    """Key a multi-point curve for a falling-organ transform channel."""
    plug = node + "." + attribute
    cmds.setAttr(plug, keys[0][1])
    for frame, value in keys:
        cmds.setKeyframe(plug, time=frame, value=value)


def _create_falling_organs(
    cmds, foliage_result, plan, group, name, kind, duration_override=None
):
    """Internal helper for create falling organs.

    Parameters:
        cmds: Input value used by this function.
        foliage_result: Input value used by this function.
        plan: Input value used by this function.
        group: Input value used by this function.
        name: Input value used by this function.
        kind: Input value used by this function.
        duration_override: Input value used by this function.
    """
    if not foliage_result:
        return []
    if kind == "leaf":
        count = plan["falling_leaf_count"]
        meshes = foliage_result.get("leaf_meshes", ())
        sources = foliage_result["model"].leaves
    else:
        count = plan["falling_flower_count"]
        meshes = foliage_result.get("flower_meshes", ())
        sources = foliage_result["model"].flowers
    if count <= 0 or not meshes or not sources:
        return []

    prototype, prototype_nodes = maya_foliage.create_organ_prototype_in_maya(
        foliage_result["model"],
        kind,
        group,
        name + "_Falling" + kind.title() + "Prototype",
    )
    if not prototype:
        return []
    managed = [prototype] + list(prototype_nodes)
    span = max(2, plan.config.end_frame - plan.config.start_frame)
    # The previous 16% span made a drop look like a snap.  A falling organ
    # should remain visible for several seconds while drops are staggered.
    if duration_override is None:
        fall_duration = max(
            84,
            int(round(span * (0.72 if kind == "leaf" else 0.82))),
        )
    else:
        fall_duration = max(12, int(duration_override))
    first_start = plan.config.start_frame + 2
    last_start = max(first_start, plan.config.end_frame - fall_duration - 1)
    radians = math.radians(plan.config.wind_direction_degrees)
    wind_x = math.cos(radians)
    wind_z = math.sin(radians)
    for index in range(count):
        # Do not cycle through the source list in order.  A seeded integer
        # mixer gives each drop a different canopy origin while preserving
        # reproducibility when the same tree seed is used.
        source_key = (
            (index + 1) * 1103515245
            + (plan.config.seed + 17) * 12345
        ) & 0x7fffffff
        source = sources[source_key % len(sources)]
        if count == 1:
            start_frame = (first_start + last_start) // 2
        else:
            start_frame = int(round(
                first_start
                + (last_start - first_start) * index / float(count - 1)
            ))
        end_frame = min(plan.config.end_frame, start_frame + fall_duration)
        instance = cmds.instance(
            prototype,
            name="{}_Falling{}_{:04d}".format(name, kind.title(), index),
        )[0]
        resolved_group = cmds.ls(group, long=True) or []
        if resolved_group:
            cmds.parent(instance, resolved_group[0])
        cmds.setAttr(instance + ".visibility", False)
        cmds.setKeyframe(instance + ".visibility", time=start_frame - 1, value=0)
        cmds.setKeyframe(instance + ".visibility", time=start_frame, value=1)
        cmds.setKeyframe(instance + ".visibility", time=end_frame, value=1)
        cmds.setKeyframe(instance + ".visibility", time=end_frame + 1, value=0)

        direction_phase = (
            index * 1.61803398875 + plan.config.seed * 0.73
        ) * 0.017453292519943295
        cross_x = -wind_z
        cross_z = wind_x
        # The source position is the actual attachment position on the tree.
        # Do not add a launch offset here: the organ must visibly detach from
        # a real leaf/flower location rather than appearing in mid-air.
        start_pos = source.position
        drift = plan["height"] * (0.38 + 0.12 * plan.config.wind_intensity)
        lateral_spread = plan["height"] * (0.28 if kind == "leaf" else 0.22)
        lateral = math.sin(direction_phase * 1.31) * lateral_spread
        end_pos = (
            start_pos[0] + wind_x * drift + cross_x * lateral,
            plan["ground_y"] - max(0.5, plan["height"] * 0.08),
            start_pos[2] + wind_z * drift + cross_z * lateral,
        )
        # Use several directional waypoints instead of one straight segment.
        # The forward component follows the wind; the cross-wind component
        # changes sign and magnitude so every organ describes a loose drift.
        path_fractions = (0.0, 0.22, 0.48, 0.74, 1.0)
        path_points = []
        for fraction in path_fractions:
            forward = drift * (fraction ** 1.08)
            side_factor = (
                0.48 * math.sin(math.pi * fraction)
                * math.sin(direction_phase * 0.7)
                + 0.52 * fraction
            )
            wobble = (
                plan["height"] * 0.055
                * math.sin(math.pi * fraction)
                * math.sin(direction_phase + fraction * math.pi * 2.4)
                * (1.0 - fraction * 0.25)
            )
            path_points.append((
                start_frame + int(round((end_frame - start_frame) * fraction)),
                (
                    start_pos[0] + wind_x * forward + cross_x * (lateral * side_factor) + cross_x * wobble,
                    # Stronger ease-in keeps the organ floating near its
                    # source for longer and removes the fast snap near the
                    # beginning of the drop.
                    start_pos[1] + (end_pos[1] - start_pos[1]) * (fraction ** 1.38),
                    start_pos[2] + wind_z * forward + cross_z * (lateral * side_factor) + cross_z * wobble,
                ),
            ))
        rotation = _organ_rotation(source)
        tumble = 120.0 + (index % 5) * 55.0
        _set_keyed_curve(
            cmds, instance, "translateX",
            tuple((frame, point[0]) for frame, point in path_points),
        )
        _set_keyed_curve(
            cmds, instance, "translateY",
            tuple((frame, point[1]) for frame, point in path_points),
        )
        _set_keyed_curve(
            cmds, instance, "translateZ",
            tuple((frame, point[2]) for frame, point in path_points),
        )
        _set_keyed_value(
            cmds, instance, "rotateX", start_frame, end_frame,
            rotation[0], rotation[0] + tumble,
        )
        _set_keyed_value(
            cmds, instance, "rotateY", start_frame, end_frame,
            rotation[1], rotation[1] + tumble * 0.7,
        )
        _set_keyed_value(
            cmds, instance, "rotateZ", start_frame, end_frame,
            rotation[2], rotation[2] + tumble * 0.45,
        )
        managed.append(instance)
    return managed


def _create_wind(cmds, tree_targets, plan, group, name):
    """Internal helper for create wind.

    Parameters:
        cmds: Input value used by this function.
        tree_targets: Input value used by this function.
        plan: Input value used by this function.
        group: Input value used by this function.
        name: Input value used by this function.
    """
    if not plan.config.has_wind():
        return []

    managed = _create_bend_layer(
        cmds,
        tree_targets,
        plan,
        group,
        name,
        "_WindBend",
        EXPRESSION_SUFFIX,
            plan["wind_amplitude_degrees"],
            plan["wind_frequency"],
    )
    return managed


def create_weather_in_maya(
    tree_result,
    foliage_result=None,
    config=None,
    name="LSystemTree",
):
    """Create the wind-only animation layer for a generated tree."""
    cmds = _maya_cmds()
    tree_model = tree_result["model"]
    foliage_model = foliage_result.get("model") if foliage_result else None
    config = config or WeatherConfig(seed=tree_model.config.seed + 211)
    plan = build_weather_plan(tree_model, foliage_model, config)
    root = tree_result["root"]

    # Always remove the previous layer first, including old particle-based
    # weather nodes, so refreshing animation cannot stack deformers or
    # duplicate falling-organ systems.
    delete_weather_nodes(root)
    if not config.any_effect_enabled():
        return {
            "group": None,
            "plan": plan,
            "managed_nodes": [],
            "animation_type": "none",
        }

    group = cmds.group(
        empty=True,
        name=name + ANIMATION_GROUP_SUFFIX,
        parent=root,
    )
    _set_bool_attr(cmds, group, ANIMATION_MARKER, True)
    # This marker keeps old cleanup code and old editable scenes compatible.
    _set_bool_attr(cmds, group, LEGACY_WEATHER_MARKER, True)
    animation_types = []
    if config.has_wind():
        animation_types.append("wind_sway")
    if config.has_falling_organs():
        animation_types.append("falling_organs")
    _set_string_attr(cmds, group, "animationType", "+".join(animation_types))
    _set_string_attr(
        cmds,
        group,
        "animationMode",
        "Maya bend deformer + keyed falling organ instances",
    )
    _set_string_attr(cmds, group, "implementationVersion", "weather-keyed-fall-1.9")
    _set_string_attr(
        cmds,
        group,
        "weatherConfigJson",
        json.dumps(dict(config.__dict__), sort_keys=True),
    )

    managed = _create_wind(
        cmds,
        _mesh_targets(cmds, tree_result, foliage_result),
        plan,
        group,
        name,
    )
    managed.extend(
        _create_falling_organs(
            cmds,
            foliage_result,
            plan,
            group,
            name,
            "leaf",
        )
    )
    managed.extend(
        _create_falling_organs(
            cmds,
            foliage_result,
            plan,
            group,
            name,
            "flower",
        )
    )
    _register_managed_nodes(cmds, group, managed)
    cmds.playbackOptions(minTime=config.start_frame, maxTime=config.end_frame)
    cmds.currentTime(config.start_frame, edit=True)
    cmds.select(clear=True)
    return {
        "group": group,
        "plan": plan,
        "managed_nodes": [group] + managed,
        "animation_type": "+".join(animation_types),
    }
