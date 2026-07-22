"""Build combined Maya meshes for season-driven leaves and flowers."""

from __future__ import division, print_function

import math
from collections import Counter

from .foliage import (
    FlowerInstance,
    FoliageConfig,
    LeafInstance,
    generate_foliage,
)


def _add(a, b):
    return tuple(a[index] + b[index] for index in range(3))


def _sub(a, b):
    return tuple(a[index] - b[index] for index in range(3))


def _mul(vector, scalar):
    return tuple(component * scalar for component in vector)


def _dot(a, b):
    return sum(a[index] * b[index] for index in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(vector):
    length = math.sqrt(_dot(vector, vector))
    if length <= 1.0e-9:
        return (0.0, 1.0, 0.0)
    return _mul(vector, 1.0 / length)


def _orientation(direction, azimuth_degrees):
    forward = _normalize(direction)
    helper = (0.0, 1.0, 0.0)
    if abs(_dot(forward, helper)) > 0.92:
        helper = (1.0, 0.0, 0.0)
    side = _normalize(_cross(forward, helper))
    normal = _normalize(_cross(forward, side))
    radians = math.radians(azimuth_degrees)
    rotated_side = _add(
        _mul(side, math.cos(radians)),
        _mul(normal, math.sin(radians)),
    )
    rotated_normal = _normalize(_cross(forward, rotated_side))
    return forward, _normalize(rotated_side), rotated_normal


def build_leaf_mesh_groups(foliage_model):
    """Return one mesh-array group per seasonal leaf color."""
    groups = {}
    for leaf in foliage_model.leaves:
        points, counts, connects = groups.setdefault(leaf.color_index, ([], [], []))
        forward, side, normal = _orientation(leaf.direction, leaf.azimuth)
        base_index = len(points)
        base = _add(leaf.position, _mul(forward, -leaf.length * 0.12))
        tip = _add(leaf.position, _mul(forward, leaf.length * 0.88))
        middle = _add(
            _add(leaf.position, _mul(forward, leaf.length * 0.36)),
            _mul(normal, leaf.length * 0.09),
        )
        left = _add(
            _add(leaf.position, _mul(forward, leaf.length * 0.34)),
            _mul(side, leaf.width * 0.5),
        )
        right = _add(
            _add(leaf.position, _mul(forward, leaf.length * 0.34)),
            _mul(side, -leaf.width * 0.5),
        )
        points.extend((base, left, tip, right, middle))
        counts.extend((3, 3, 3, 3))
        connects.extend(
            (
                base_index,
                base_index + 1,
                base_index + 4,
                base_index + 1,
                base_index + 2,
                base_index + 4,
                base_index + 2,
                base_index + 3,
                base_index + 4,
                base_index + 3,
                base_index,
                base_index + 4,
            )
        )
    return groups


def build_flower_mesh_groups(foliage_model):
    """Return petal meshes per color plus a shared flower-center mesh."""
    petal_groups = {}
    center_points = []
    center_counts = []
    center_connects = []
    world_down = (0.0, -1.0, 0.0)

    for flower in foliage_model.flowers:
        points, counts, connects = petal_groups.setdefault(
            flower.color_index,
            ([], [], []),
        )
        axis, side, normal = _orientation(flower.direction, flower.azimuth)
        petal_length = flower.size * (1.0 - 0.25 * flower.wilt)
        petal_width = flower.size * 0.44 * (1.0 - 0.42 * flower.wilt)

        for petal_index in range(5):
            radians = 2.0 * math.pi * petal_index / 5.0
            radial = _normalize(
                _add(
                    _mul(side, math.cos(radians)),
                    _mul(normal, math.sin(radians)),
                )
            )
            target = _normalize(
                _add(
                    _add(
                        _mul(radial, flower.openness),
                        _mul(axis, (1.0 - flower.openness) * 0.65),
                    ),
                    _mul(world_down, flower.wilt * 1.05),
                )
            )
            petal_side = _cross(target, axis)
            if _dot(petal_side, petal_side) <= 1.0e-9:
                petal_side = side
            petal_side = _normalize(petal_side)
            base_index = len(points)
            petal_base = _add(flower.position, _mul(radial, flower.size * 0.06))
            petal_tip = _add(petal_base, _mul(target, petal_length))
            middle = _add(petal_base, _mul(target, petal_length * 0.48))
            left = _add(middle, _mul(petal_side, petal_width * 0.5))
            right = _add(middle, _mul(petal_side, -petal_width * 0.5))
            points.extend((petal_base, left, petal_tip, right))
            counts.extend((3, 3))
            connects.extend(
                (
                    base_index,
                    base_index + 1,
                    base_index + 2,
                    base_index,
                    base_index + 2,
                    base_index + 3,
                )
            )

        center_base = len(center_points)
        center_radius = flower.size * 0.15
        center_points.extend(
            (
                _add(flower.position, _mul(axis, center_radius)),
                _add(flower.position, _mul(axis, -center_radius)),
                _add(flower.position, _mul(side, center_radius)),
                _add(flower.position, _mul(side, -center_radius)),
                _add(flower.position, _mul(normal, center_radius)),
                _add(flower.position, _mul(normal, -center_radius)),
            )
        )
        for triangle in (
            (0, 2, 4),
            (0, 4, 3),
            (0, 3, 5),
            (0, 5, 2),
            (1, 4, 2),
            (1, 3, 4),
            (1, 5, 3),
            (1, 2, 5),
        ):
            center_counts.append(3)
            center_connects.extend(center_base + index for index in triangle)

    return petal_groups, (center_points, center_counts, center_connects)


def build_asset_mesh_groups(foliage_model, kind):
    """Build combined arrays from the licensed OBJ organ catalog."""
    library = getattr(foliage_model, "asset_library", None)
    instances = foliage_model.leaves if kind == "leaf" else foliage_model.flowers
    groups = {}
    if library is None:
        return groups
    for instance in instances:
        if not instance.asset_id:
            continue
        asset = library.get(instance.asset_id)
        mesh = library.mesh(instance.asset_id)
        arrays = groups.setdefault((instance.color_index, instance.asset_id), ([], [], []))
        points, counts, connects = arrays
        forward, side, normal = _orientation(instance.direction, instance.azimuth)
        scale = (instance.length if kind == "leaf" else instance.size) * asset.scale
        base_index = len(points)
        for x_value, y_value, z_value in mesh.vertices:
            point = _add(
                instance.position,
                _add(
                    _mul(side, x_value * scale),
                    _add(_mul(forward, y_value * scale), _mul(normal, z_value * scale)),
                ),
            )
            if kind == "flower" and instance.wilt > 0.0:
                point = _add(point, (0.0, -y_value * scale * instance.wilt * 0.55, 0.0))
            points.append(point)
        for face in mesh.faces:
            counts.append(len(face))
            connects.extend(base_index + index for index in face)
    return groups


def _material(cmds, name, color):
    shading_group = name + "SG"
    if not cmds.objExists(name):
        name = cmds.shadingNode("lambert", asShader=True, name=name)
        cmds.setAttr(name + ".color", color[0], color[1], color[2], type="double3")
        cmds.setAttr(name + ".diffuse", 0.88)
    if not cmds.objExists(shading_group):
        shading_group = cmds.sets(
            renderable=True,
            noSurfaceShader=True,
            empty=True,
            name=shading_group,
        )
        cmds.connectAttr(
            name + ".outColor",
            shading_group + ".surfaceShader",
            force=True,
        )
    return shading_group


def _create_mesh(cmds, om, arrays, name, parent, shading_group):
    points, counts, connects = arrays
    if not points:
        return None
    mesh_function = om.MFnMesh()
    mesh_function.create([om.MPoint(*point) for point in points], counts, connects)
    shape = mesh_function.fullPathName()
    transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    transform = cmds.rename(transform, name)
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
    cmds.rename(shape, transform.split("|")[-1] + "Shape")
    cmds.parent(transform, parent)
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
    cmds.setAttr(shape + ".doubleSided", True)
    cmds.sets(transform, edit=True, forceElement=shading_group)
    return transform


class _PrototypeFoliageModel(object):
    def __init__(self, profile, leaves=None, flowers=None, asset_library=None):
        self.profile = profile
        self.leaves = list(leaves or [])
        self.flowers = list(flowers or [])
        self.asset_library = asset_library


def _dominant_color_index(instances):
    return Counter(instance.color_index for instance in instances).most_common(1)[0][0]


def create_organ_prototype_in_maya(foliage_model, kind, parent, name):
    """Create one seasonal organ using the same geometry as attached organs."""
    try:
        import maya.api.OpenMaya as om
        import maya.cmds as cmds
    except ImportError as error:
        raise RuntimeError("This function must run inside Maya") from error

    profile = foliage_model.profile
    if kind == "leaf":
        if not foliage_model.leaves:
            return None, []
        color_index = _dominant_color_index(foliage_model.leaves)
        average_length = sum(leaf.length for leaf in foliage_model.leaves) / len(
            foliage_model.leaves
        )
        average_width = sum(leaf.width for leaf in foliage_model.leaves) / len(
            foliage_model.leaves
        )
        prototype_leaf = LeafInstance(
            position=(0.0, 0.0, 0.0),
            direction=(0.0, 1.0, 0.0),
            azimuth=0.0,
            length=average_length,
            width=average_width,
            color_index=color_index,
            source_segment=-1,
        )
        prototype_model = _PrototypeFoliageModel(
            profile,
            leaves=[prototype_leaf],
        )
        material_name = name + "_MAT"
        shading_group = _material(
            cmds,
            material_name,
            profile.leaf_palette[color_index],
        )
        arrays = build_leaf_mesh_groups(prototype_model)[color_index]
        prototype = _create_mesh(
            cmds,
            om,
            arrays,
            name,
            parent,
            shading_group,
        )
        cmds.setAttr(prototype + ".visibility", False)
        return prototype, [material_name, shading_group]

    if kind != "flower" or not foliage_model.flowers:
        return None, []
    color_index = _dominant_color_index(foliage_model.flowers)
    average_size = sum(flower.size for flower in foliage_model.flowers) / len(
        foliage_model.flowers
    )
    average_openness = sum(
        flower.openness for flower in foliage_model.flowers
    ) / len(foliage_model.flowers)
    average_wilt = sum(flower.wilt for flower in foliage_model.flowers) / len(
        foliage_model.flowers
    )
    prototype_flower = FlowerInstance(
        position=(0.0, 0.0, 0.0),
        direction=(0.0, 1.0, 0.0),
        azimuth=0.0,
        size=average_size,
        color_index=color_index,
        openness=average_openness,
        wilt=average_wilt,
        source_tip=-1,
    )
    prototype_model = _PrototypeFoliageModel(
        profile,
        flowers=[prototype_flower],
    )
    petal_groups, center_arrays = build_flower_mesh_groups(prototype_model)
    petal_material_name = name + "_Petal_MAT"
    petal_sg = _material(
        cmds,
        petal_material_name,
        profile.flower_palette[color_index],
    )
    center_material_name = name + "_Center_MAT"
    center_sg = _material(
        cmds,
        center_material_name,
        profile.center_color,
    )
    petal_mesh = _create_mesh(
        cmds,
        om,
        petal_groups[color_index],
        name + "_Petals",
        parent,
        petal_sg,
    )
    center_mesh = _create_mesh(
        cmds,
        om,
        center_arrays,
        name + "_Center",
        parent,
        center_sg,
    )
    prototype = cmds.polyUnite(
        petal_mesh,
        center_mesh,
        constructionHistory=False,
        name=name,
    )[0]
    cmds.parent(prototype, parent)
    cmds.setAttr(prototype + ".visibility", False)
    return prototype, [
        petal_material_name,
        petal_sg,
        center_material_name,
        center_sg,
    ]


def create_foliage_in_maya(
    tree_model,
    config=None,
    parent_root=None,
    name="LSystemTree",
):
    try:
        import maya.api.OpenMaya as om
        import maya.cmds as cmds
    except ImportError as error:
        raise RuntimeError("This function must run inside Maya") from error

    config = config or FoliageConfig(seed=tree_model.config.seed + 101)
    model = generate_foliage(tree_model, config)
    group = cmds.group(empty=True, name=name + "_Foliage", parent=parent_root)
    meshes = []
    leaf_meshes = []
    flower_meshes = []
    season_key = model.profile.key

    leaf_asset_groups = build_asset_mesh_groups(model, "leaf")
    leaf_groups = leaf_asset_groups or dict(
        ((color_index, "procedural"), arrays)
        for color_index, arrays in build_leaf_mesh_groups(model).items()
    )
    for (color_index, asset_id), arrays in leaf_groups.items():
        shading_group = _material(
            cmds,
            "LSystemLeaf_{}_{:02d}_MAT".format(season_key, color_index),
            model.profile.leaf_palette[color_index],
        )
        mesh = _create_mesh(
            cmds,
            om,
            arrays,
            "{}_Leaves_{:02d}_{}".format(name, color_index, asset_id),
            group,
            shading_group,
        )
        if mesh:
            meshes.append(mesh)
            leaf_meshes.append(mesh)

    flower_asset_groups = build_asset_mesh_groups(model, "flower")
    if flower_asset_groups:
        flower_groups = flower_asset_groups
        center_arrays = ([], [], [])
    else:
        petal_groups, center_arrays = build_flower_mesh_groups(model)
        flower_groups = dict(
            ((color_index, "procedural"), arrays)
            for color_index, arrays in petal_groups.items()
        )
    for (color_index, asset_id), arrays in flower_groups.items():
        shading_group = _material(
            cmds,
            "LSystemFlower_{}_{:02d}_MAT".format(season_key, color_index),
            model.profile.flower_palette[color_index],
        )
        mesh = _create_mesh(
            cmds,
            om,
            arrays,
            "{}_Flowers_{:02d}_{}".format(name, color_index, asset_id),
            group,
            shading_group,
        )
        if mesh:
            meshes.append(mesh)
            flower_meshes.append(mesh)

    center_material = _material(
        cmds,
        "LSystemFlowerCenter_{}_MAT".format(season_key),
        model.profile.center_color,
    )
    center_mesh = _create_mesh(
        cmds,
        om,
        center_arrays,
        name + "_FlowerCenters",
        group,
        center_material,
    )
    if center_mesh:
        meshes.append(center_mesh)

    cmds.addAttr(group, longName="season", dataType="string")
    cmds.setAttr(group + ".season", season_key, type="string")
    cmds.addAttr(group, longName="leafCount", attributeType="long")
    cmds.setAttr(group + ".leafCount", len(model.leaves))
    cmds.addAttr(group, longName="flowerCount", attributeType="long")
    cmds.setAttr(group + ".flowerCount", len(model.flowers))
    cmds.addAttr(group, longName="flowerWilt", attributeType="double")
    cmds.setAttr(group + ".flowerWilt", model.profile.flower_wilt)
    cmds.addAttr(group, longName="organAssetSource", dataType="string")
    cmds.setAttr(
        group + ".organAssetSource",
        "Kenney Nature Kit 2.1 (CC0-1.0)",
        type="string",
    )

    return {
        "group": group,
        "meshes": meshes,
        "leaf_meshes": leaf_meshes,
        "flower_meshes": flower_meshes,
        "flower_center_mesh": center_mesh,
        "model": model,
    }
