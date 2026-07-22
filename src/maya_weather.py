"""Maya-native weather using deformers, particles, fields and instancers.

This is the original interactive mode: Maya evaluates the animation directly
through dependency-graph nodes, so playback does not depend on Python time
callbacks or pre-baked blendShape poses.
"""

from __future__ import division, print_function

import math
import json

from . import maya_foliage
from .weather import WeatherConfig, build_weather_plan


def _maya_cmds():
    try:
        import maya.cmds as cmds
    except ImportError as error:
        raise RuntimeError("Weather animation must be created inside Maya") from error
    return cmds


def _shape(cmds, transform):
    shapes = cmds.listRelatives(transform, shapes=True, fullPath=True) or []
    return shapes[0] if shapes else transform


def _safe_set(cmds, plug, *values, **kwargs):
    if cmds.objExists(plug):
        cmds.setAttr(plug, *values, **kwargs)


def _set_string_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, dataType="string")
    cmds.setAttr(node + "." + attr, value, type="string")


def _material(cmds, name, color, transparency=0.0):
    material = cmds.shadingNode("lambert", asShader=True, name=name)
    cmds.setAttr(material + ".color", *color, type="double3")
    cmds.setAttr(material + ".diffuse", 0.88)
    cmds.setAttr(
        material + ".transparency",
        transparency,
        transparency,
        transparency,
        type="double3",
    )
    shading_group = cmds.sets(
        renderable=True,
        noSurfaceShader=True,
        empty=True,
        name=name + "SG",
    )
    cmds.connectAttr(
        material + ".outColor",
        shading_group + ".surfaceShader",
        force=True,
    )
    return material, shading_group


def _mesh_targets(cmds, tree_result, foliage_result):
    targets = [tree_result.get("mesh")]
    if foliage_result:
        targets.extend(foliage_result.get("meshes", ()))
    return [target for target in targets if target and cmds.objExists(target)]


def _key_emitter_rate(cmds, emitter, rate, config):
    plug = _shape(cmds, emitter) + ".rate"
    if not cmds.objExists(plug):
        return
    for frame, value in (
        (config.start_frame - 1, 0.0),
        (config.start_frame, rate),
        (config.end_frame, rate),
        (config.end_frame + 1, 0.0),
    ):
        cmds.setKeyframe(plug, time=frame, value=value)


def _create_wind(cmds, targets, plan, group, name):
    if not targets or plan.config.wind_intensity <= 0.0:
        return []
    deformer, handle = cmds.nonLinear(
        targets,
        type="bend",
        name=name + "_WindBend",
    )
    center = plan["center"]
    minimum_y = plan["ground_y"]
    cmds.xform(
        handle,
        worldSpace=True,
        translation=(center[0], minimum_y, center[2]),
        rotation=(0.0, plan.config.wind_direction_degrees, 0.0),
    )
    _safe_set(cmds, handle + ".scaleY", max(plan["height"], 0.1))
    _safe_set(cmds, handle + ".visibility", False)
    _safe_set(cmds, deformer + ".lowBound", 0.0)
    _safe_set(cmds, deformer + ".highBound", 1.0)
    cmds.parent(handle, group)

    frequency = plan["wind_frequency"]
    amplitude = plan["wind_curvature"]
    expression = cmds.expression(
        name=name + "_WindExpression",
        alwaysEvaluate=True,
        unitConversion="all",
        string=(
            "{0}.curvature = {1:.8f} * "
            "(sin(frame * {2:.8f}) + 0.32 * sin(frame * {3:.8f} + 1.7));"
        ).format(deformer, amplitude, frequency, frequency * 2.31),
    )
    return [deformer, handle, expression]


def _create_particle_system(cmds, name, render_type, lifespan, max_count=0):
    cmds.select(clear=True)
    created = list(cmds.particle(name=name))
    shape = next(
        (node for node in created if cmds.nodeType(node) == "particle"),
        None,
    )
    if shape:
        parents = cmds.listRelatives(shape, parent=True, fullPath=False) or []
        transform = parents[0] if parents else created[0]
    else:
        transform = created[0]
        shape = _shape(cmds, transform)
    _safe_set(cmds, shape + ".particleRenderType", render_type)
    _safe_set(cmds, shape + ".lifespanMode", 1)
    _safe_set(cmds, shape + ".lifespan", lifespan)
    if max_count > 0:
        _safe_set(cmds, shape + ".maxCount", int(max_count))
    return transform, shape


def _emitter_positions(plan, grid_size=3):
    center = plan["center"]
    size = plan["size"]
    height = plan["emitter_height"]
    positions = []
    for x_index in range(grid_size):
        for z_index in range(grid_size):
            x_amount = x_index / float(grid_size - 1) - 0.5
            z_amount = z_index / float(grid_size - 1) - 0.5
            positions.append(
                (
                    center[0] + x_amount * max(size[0] * 1.15, 4.0),
                    height,
                    center[2] + z_amount * max(size[2] * 1.15, 4.0),
                )
            )
    return positions


def _create_directional_emitters(
    cmds,
    particle_transform,
    plan,
    group,
    name,
    rate,
    speed,
    grid_size=3,
):
    emitters = []
    positions = _emitter_positions(plan, grid_size=grid_size)
    direction_radians = math.radians(plan.config.wind_direction_degrees)
    wind_drift = plan.config.wind_intensity * 0.12
    for index, position in enumerate(positions):
        cmds.select(clear=True)
        emitter = cmds.emitter(
            type="direction",
            position=position,
            rate=rate / float(len(positions)),
            speed=speed,
            directionX=math.cos(direction_radians) * wind_drift,
            directionY=-1.0,
            directionZ=math.sin(direction_radians) * wind_drift,
            name="{}_{:02d}".format(name, index),
        )[0]
        cmds.connectDynamic(particle_transform, emitters=emitter)
        _key_emitter_rate(
            cmds,
            emitter,
            rate / float(len(positions)),
            plan.config,
        )
        cmds.parent(emitter, group)
        emitters.append(emitter)
    return emitters


def _create_gravity(cmds, particle_transform, group, name, magnitude):
    # Field commands inspect the active selection.  The last created emitter
    # is otherwise still selected and Maya tries (invalidly) to make it own
    # the gravity field.
    cmds.select(clear=True)
    field = cmds.gravity(
        name=name,
        magnitude=magnitude,
        directionX=0.0,
        directionY=-1.0,
        directionZ=0.0,
    )[0]
    cmds.connectDynamic(particle_transform, fields=field)
    cmds.parent(field, group)
    return field


def _create_air(cmds, particle_transform, group, name, plan, magnitude):
    radians = math.radians(plan.config.wind_direction_degrees)
    cmds.select(clear=True)
    field = cmds.air(
        name=name,
        magnitude=magnitude,
        directionX=math.cos(radians),
        directionY=0.0,
        directionZ=math.sin(radians),
        speed=1.0,
        inheritVelocity=0.0,
    )[0]
    cmds.connectDynamic(particle_transform, fields=field)
    cmds.parent(field, group)
    return field


def _add_collision(cmds, target, particles, resilience, friction):
    if not target or not cmds.objExists(target):
        return []
    try:
        result = cmds.collision(
            target,
            particles,
            resilience=resilience,
            friction=friction,
        )
        if isinstance(result, (list, tuple)):
            return list(result)
        return [result] if result else []
    except RuntimeError:
        # Some Maya versions reject collisions on meshes with particular
        # construction histories.  Weather generation should still succeed.
        return []


def _create_rain(cmds, tree_result, plan, group, name):
    if plan.config.rain_intensity <= 0.0:
        return []
    particles, shape = _create_particle_system(
        cmds,
        name + "_RainParticles",
        render_type=2,
        lifespan=max(2.0, plan["height"] / max(plan["rain_speed"], 0.1) * 2.0),
    )
    cmds.parent(particles, group)
    _safe_set(cmds, shape + ".tailSize", 0.42)
    _safe_set(cmds, shape + ".lineWidth", 1.15)
    material, shading_group = _material(
        cmds,
        name + "_Rain_MAT",
        (0.28, 0.58, 0.92),
        transparency=0.18,
    )
    cmds.sets(particles, edit=True, forceElement=shading_group)
    emitters = _create_directional_emitters(
        cmds,
        particles,
        plan,
        group,
        name + "_RainEmitter",
        plan["rain_rate"],
        plan["rain_speed"],
    )
    gravity = _create_gravity(cmds, particles, group, name + "_RainGravity", 4.5)
    collisions = _add_collision(
        cmds,
        tree_result.get("mesh"),
        particles,
        resilience=0.12,
        friction=0.20,
    )
    return [particles, shape, material, shading_group, gravity] + emitters + collisions


def _create_snow(cmds, tree_result, plan, group, name):
    if plan.config.snow_intensity <= 0.0:
        return []
    particles, shape = _create_particle_system(
        cmds,
        name + "_SnowParticles",
        render_type=6,
        lifespan=max(6.0, plan["height"] / max(plan["snow_speed"], 0.1) * 1.8),
    )
    cmds.parent(particles, group)
    _safe_set(cmds, shape + ".radius", max(0.025, plan["height"] * 0.0028))
    material, shading_group = _material(
        cmds,
        name + "_Snow_MAT",
        (0.96, 0.98, 1.0),
        transparency=0.02,
    )
    cmds.sets(particles, edit=True, forceElement=shading_group)
    emitters = _create_directional_emitters(
        cmds,
        particles,
        plan,
        group,
        name + "_SnowEmitter",
        plan["snow_rate"],
        plan["snow_speed"],
    )
    gravity = _create_gravity(cmds, particles, group, name + "_SnowGravity", 0.28)
    air = _create_air(
        cmds,
        particles,
        group,
        name + "_SnowAir",
        plan,
        0.6 + 1.8 * plan.config.wind_intensity,
    )
    collisions = _add_collision(
        cmds,
        tree_result.get("mesh"),
        particles,
        resilience=0.02,
        friction=0.78,
    )
    return [particles, shape, material, shading_group, gravity, air] + emitters + collisions


def _create_snow_cover(cmds, tree_result, plan, group, name):
    if plan.config.snow_intensity <= 0.0:
        return []
    snow_mesh = cmds.duplicate(
        tree_result["mesh"],
        returnRootsOnly=True,
        name=name + "_SnowCover",
    )[0]
    cmds.parent(snow_mesh, group)
    center = plan["center"]
    cmds.xform(
        snow_mesh,
        worldSpace=True,
        pivots=(center[0], plan["ground_y"], center[2]),
    )
    material, shading_group = _material(
        cmds,
        name + "_SnowCover_MAT",
        (0.94, 0.97, 1.0),
        transparency=1.0,
    )
    cmds.sets(snow_mesh, edit=True, forceElement=shading_group)
    start = plan.config.start_frame
    accumulation_end = plan["snow_accumulation_end"]
    end = plan.config.end_frame
    amount = plan.config.snow_intensity
    for axis, final_scale in (
        ("X", 1.002 + 0.020 * amount),
        ("Y", 1.001 + 0.010 * amount),
        ("Z", 1.002 + 0.020 * amount),
    ):
        plug = snow_mesh + ".scale" + axis
        cmds.setKeyframe(plug, time=start, value=1.0005)
        cmds.setKeyframe(plug, time=accumulation_end, value=final_scale)
        cmds.setKeyframe(plug, time=end, value=final_scale)
    for channel in ("R", "G", "B"):
        plug = material + ".transparency" + channel
        cmds.setKeyframe(plug, time=start, value=1.0)
        cmds.setKeyframe(
            plug,
            time=accumulation_end,
            value=max(0.02, 0.36 - 0.32 * amount),
        )
        cmds.setKeyframe(
            plug,
            time=end,
            value=max(0.02, 0.36 - 0.32 * amount),
        )
    return [snow_mesh, material, shading_group]


def _create_surface_emitters(
    cmds,
    meshes,
    particles,
    group,
    name,
    total_rate,
    config,
):
    valid_meshes = [mesh for mesh in meshes if mesh and cmds.objExists(mesh)]
    if not valid_meshes:
        return []
    emitters = []
    rate = total_rate / float(len(valid_meshes))
    for index, mesh in enumerate(valid_meshes):
        try:
            emitter = cmds.emitter(
                mesh,
                type="surface",
                rate=rate,
                speed=0.15,
                normalSpeed=0.12,
                name="{}_{:02d}".format(name, index),
            )[0]
        except RuntimeError:
            continue
        cmds.connectDynamic(particles, emitters=emitter)
        _key_emitter_rate(cmds, emitter, rate, config)
        emitters.append(emitter)
    return emitters


def _create_falling_organs(
    cmds,
    foliage_result,
    plan,
    group,
    name,
    kind,
):
    if not foliage_result:
        return []
    if kind == "leaf":
        count = plan["falling_leaf_count"]
        rate = plan["leaf_fall_rate"]
        meshes = foliage_result.get("leaf_meshes", ())
        max_count = plan.config.max_falling_leaves
    else:
        count = plan["falling_flower_count"]
        rate = plan["flower_fall_rate"]
        meshes = foliage_result.get("flower_meshes", ())
        max_count = plan.config.max_falling_flowers
    if count <= 0 or not meshes:
        return []

    prototype, prototype_nodes = maya_foliage.create_organ_prototype_in_maya(
        foliage_result["model"],
        kind,
        group,
        name + "_" + kind.title() + "Prototype",
    )
    if not prototype:
        return []
    particles, shape = _create_particle_system(
        cmds,
        name + "_Falling" + kind.title() + "Particles",
        render_type=0,
        lifespan=max(5.0, plan["height"] / 2.2),
        max_count=max_count,
    )
    cmds.parent(particles, group)
    emitters = _create_surface_emitters(
        cmds,
        meshes,
        particles,
        group,
        name + "_" + kind.title() + "SurfaceEmitter",
        rate,
        plan.config,
    )
    gravity = _create_gravity(
        cmds,
        particles,
        group,
        name + "_" + kind.title() + "Gravity",
        1.4 if kind == "leaf" else 0.85,
    )
    air = _create_air(
        cmds,
        particles,
        group,
        name + "_" + kind.title() + "Air",
        plan,
        0.8 + 2.0 * plan.config.wind_intensity,
    )
    instancer = cmds.particleInstancer(
        shape,
        name=name + "_" + kind.title() + "Instancer",
        addObject=True,
        object=prototype,
        cycle="None",
        position="worldPosition",
        particleAge="age",
    )
    if isinstance(instancer, (list, tuple)):
        instancer_nodes = list(instancer)
    else:
        instancer_nodes = [instancer]
    return (
        [prototype, particles, shape, gravity, air]
        + prototype_nodes
        + emitters
        + instancer_nodes
    )


def _register_managed_nodes(cmds, group, nodes):
    if not cmds.attributeQuery("managedNodes", node=group, exists=True):
        cmds.addAttr(
            group,
            longName="managedNodes",
            attributeType="message",
            multi=True,
        )
    connected = []
    for node in nodes:
        if not node or not cmds.objExists(node):
            continue
        if cmds.isConnected(node + ".message", group + ".managedNodes[{}]".format(len(connected))):
            continue
        try:
            cmds.connectAttr(
                node + ".message",
                group + ".managedNodes[{}]".format(len(connected)),
                force=True,
            )
            connected.append(node)
        except RuntimeError:
            pass


def delete_weather_nodes(root):
    cmds = _maya_cmds()
    groups = cmds.listRelatives(
        root,
        children=True,
        type="transform",
        fullPath=True,
    ) or []
    for group in groups:
        if not cmds.attributeQuery("lsystemWeatherManaged", node=group, exists=True):
            continue
        nodes = []
        if cmds.attributeQuery("managedNodes", node=group, exists=True):
            nodes = cmds.listConnections(
                group + ".managedNodes",
                source=True,
                destination=False,
            ) or []
        outside_group = [
            node for node in set(nodes)
            if cmds.objExists(node) and not str(node).startswith(str(group) + "|")
        ]
        if outside_group:
            try:
                cmds.delete(outside_group)
            except RuntimeError:
                pass
        if cmds.objExists(group):
            cmds.delete(group)


def create_weather_in_maya(
    tree_result,
    foliage_result=None,
    config=None,
    name="LSystemTree",
):
    cmds = _maya_cmds()
    tree_model = tree_result["model"]
    foliage_model = foliage_result.get("model") if foliage_result else None
    config = config or WeatherConfig(seed=tree_model.config.seed + 211)
    plan = build_weather_plan(tree_model, foliage_model, config)
    root = tree_result["root"]
    delete_weather_nodes(root)
    if not config.any_effect_enabled():
        return {"group": None, "plan": plan, "managed_nodes": []}

    group = cmds.group(empty=True, name=name + "_Weather", parent=root)
    cmds.addAttr(group, longName="lsystemWeatherManaged", attributeType="bool")
    cmds.setAttr(group + ".lsystemWeatherManaged", True)
    cmds.addAttr(group, longName="animationMode", dataType="string")
    cmds.setAttr(
        group + ".animationMode",
        "Maya deformers and particles",
        type="string",
    )
    cmds.addAttr(group, longName="implementationVersion", dataType="string")
    cmds.setAttr(
        group + ".implementationVersion",
        "3.0-original-particles",
        type="string",
    )
    _set_string_attr(
        cmds,
        group,
        "weatherConfigJson",
        json.dumps(dict(config.__dict__), sort_keys=True),
    )

    managed = [group]
    managed.extend(
        _create_wind(
            cmds,
            _mesh_targets(cmds, tree_result, foliage_result),
            plan,
            group,
            name,
        )
    )
    managed.extend(_create_rain(cmds, tree_result, plan, group, name))
    managed.extend(_create_snow(cmds, tree_result, plan, group, name))
    managed.extend(_create_snow_cover(cmds, tree_result, plan, group, name))
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
    _register_managed_nodes(cmds, group, managed[1:])

    cmds.playbackOptions(minTime=config.start_frame, maxTime=config.end_frame)
    cmds.currentTime(config.start_frame, edit=True)
    cmds.select(clear=True)
    return {"group": group, "plan": plan, "managed_nodes": managed}
