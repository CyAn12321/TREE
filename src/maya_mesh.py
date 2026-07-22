"""Create a Maya polygon mesh from the pure branch graph."""

from __future__ import division, print_function

import math

from .core import TreeConfig, generate_tree


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
        raise ValueError("Cannot normalize a zero-length vector")
    return _mul(vector, 1.0 / length)


def build_mesh_arrays(model, radial_sides=8):
    """Return points and face topology without importing Maya."""
    if radial_sides < 3:
        raise ValueError("radial_sides must be at least 3")
    points = []
    face_counts = []
    face_connects = []

    for segment in model.segments:
        direction = _normalize(_sub(segment.end, segment.start))
        helper = (0.0, 1.0, 0.0)
        if abs(_dot(direction, helper)) > 0.92:
            helper = (1.0, 0.0, 0.0)
        side = _normalize(_cross(direction, helper))
        binormal = _normalize(_cross(direction, side))
        base = len(points)

        for position, radius in (
            (segment.start, segment.start_radius),
            (segment.end, segment.end_radius),
        ):
            for index in range(radial_sides):
                radians = 2.0 * math.pi * index / radial_sides
                offset = _add(
                    _mul(side, math.cos(radians) * radius),
                    _mul(binormal, math.sin(radians) * radius),
                )
                points.append(_add(position, offset))

        for index in range(radial_sides):
            next_index = (index + 1) % radial_sides
            face_counts.append(4)
            face_connects.extend(
                (
                    base + index,
                    base + next_index,
                    base + radial_sides + next_index,
                    base + radial_sides + index,
                )
            )

        face_counts.append(radial_sides)
        face_connects.extend(base + index for index in reversed(range(radial_sides)))
        face_counts.append(radial_sides)
        face_connects.extend(
            base + radial_sides + index for index in range(radial_sides)
        )

    return points, face_counts, face_connects


def _get_bark_shading_group(cmds):
    material = "LSystemTree_Bark_MAT"
    shading_group = material + "SG"
    if not cmds.objExists(material):
        material = cmds.shadingNode("lambert", asShader=True, name=material)
        cmds.setAttr(material + ".color", 0.20, 0.075, 0.025, type="double3")
        cmds.setAttr(material + ".diffuse", 0.82)
    if not cmds.objExists(shading_group):
        shading_group = cmds.sets(
            renderable=True,
            noSurfaceShader=True,
            empty=True,
            name=shading_group,
        )
        cmds.connectAttr(
            material + ".outColor",
            shading_group + ".surfaceShader",
            force=True,
        )
    return shading_group


def create_tree_in_maya(
    config=None,
    name="LSystemTree",
    radial_sides=8,
    create_tip_locators=False,
):
    """Generate a tree and create one Maya mesh plus optional tip locators."""
    try:
        import maya.api.OpenMaya as om
        import maya.cmds as cmds
    except ImportError as error:
        raise RuntimeError("This function must run inside Maya") from error

    config = config or TreeConfig.from_preset("broadleaf_round")
    model = generate_tree(config)
    raw_points, face_counts, face_connects = build_mesh_arrays(model, radial_sides)
    maya_points = [om.MPoint(*point) for point in raw_points]

    root = None
    cmds.undoInfo(openChunk=True, chunkName="GenerateLSystemTree")
    try:
        root = cmds.group(empty=True, name=name)
        mesh_function = om.MFnMesh()
        mesh_function.create(maya_points, face_counts, face_connects)
        shape = mesh_function.fullPathName()
        transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
        transform = cmds.rename(transform, name + "_Branches")
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        cmds.rename(shape, transform.split("|")[-1] + "Shape")
        cmds.parent(transform, root)
        cmds.polySoftEdge(transform, angle=55.0, constructionHistory=False)
        cmds.sets(
            transform,
            edit=True,
            forceElement=_get_bark_shading_group(cmds),
        )

        tip_group = None
        if create_tip_locators:
            tip_group = cmds.group(empty=True, name=name + "_Tips", parent=root)
            locator_scale = max(config.minimum_radius * 4.0, 0.045)
            for index, tip in enumerate(model.tips):
                locator = cmds.spaceLocator(
                    name="{}_Tip_{:03d}".format(name, index)
                )[0]
                cmds.xform(locator, worldSpace=True, translation=tip.position)
                locator_shape = cmds.listRelatives(locator, shapes=True, fullPath=True)[0]
                for axis in "XYZ":
                    cmds.setAttr(locator_shape + ".localScale" + axis, locator_scale)
                cmds.addAttr(locator, longName="branchDepth", attributeType="long")
                cmds.setAttr(locator + ".branchDepth", tip.depth)
                cmds.addAttr(locator, longName="parentSegment", attributeType="long")
                cmds.setAttr(
                    locator + ".parentSegment",
                    -1 if tip.parent_segment is None else tip.parent_segment,
                )
                cmds.parent(locator, tip_group)

        metadata = (
            ("seed", config.seed),
            ("branchLevels", config.branch_levels),
            ("segmentCount", len(model.segments)),
            ("tipCount", len(model.tips)),
            ("attachmentCount", len(model.attachment_points)),
        )
        for attribute, value in metadata:
            cmds.addAttr(root, longName=attribute, attributeType="long")
            cmds.setAttr(root + "." + attribute, value)
        cmds.addAttr(root, longName="trunkRadius", attributeType="double")
        cmds.setAttr(root + ".trunkRadius", config.trunk_radius)
        cmds.addAttr(root, longName="branchAngle", attributeType="double")
        cmds.setAttr(root + ".branchAngle", config.branch_angle)
        cmds.addAttr(root, longName="preset", dataType="string")
        cmds.setAttr(root + ".preset", config.preset_key, type="string")

        cmds.select(root, replace=True)
        return {
            "root": root,
            "mesh": transform,
            "tip_group": tip_group,
            "model": model,
            "attachment_points": model.attachment_points,
        }
    except Exception:
        if root and cmds.objExists(root):
            cmds.delete(root)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
