# -*- coding: utf-8 -*-
"""Create a Maya polygon mesh from the pure branch graph."""

from __future__ import division, print_function

import math
import json

from .core import TreeConfig, generate_tree
from .math_utils import (
    add as _add,
    sub as _sub,
    mul as _mul,
    dot as _dot,
    cross as _cross,
    normalize_strict as _normalize,
)


def build_mesh_arrays(model, radial_sides=8, radius_rings=4):
    """Return points and face topology without importing Maya.

    Parameters:
        model (TreeModel): Tree model whose segments will be tessellated.
        radial_sides (int): Cross-section vertex count per branch end.
            Must be >= 3.
        radius_rings (int): Number of interpolating rings along each
            branch segment for smooth radius transitions.  Must be >= 1.
    """
    if radial_sides < 3:
        raise ValueError("radial_sides must be at least 3")
    if radius_rings < 1:
        raise ValueError("radius_rings must be at least 1")
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

        # A single cone gives a constant taper slope and makes each fork
        # look like a hard radius break.  Multiple rings plus smoothstep make
        # the radius slope zero at both ends, so adjacent branch segments
        # meet without a visible kink.
        for ring_index in range(radius_rings + 1):
            amount = ring_index / float(radius_rings)
            smooth_amount = amount * amount * (3.0 - 2.0 * amount)
            radius = segment.start_radius + (
                segment.end_radius - segment.start_radius
            ) * smooth_amount
            position = _add(
                segment.start,
                _mul(_sub(segment.end, segment.start), amount),
            )
            for index in range(radial_sides):
                radians = 2.0 * math.pi * index / radial_sides
                offset = _add(
                    _mul(side, math.cos(radians) * radius),
                    _mul(binormal, math.sin(radians) * radius),
                )
                points.append(_add(position, offset))

        for ring_index in range(radius_rings):
            ring_base = base + ring_index * radial_sides
            next_ring_base = ring_base + radial_sides
            for index in range(radial_sides):
                next_index = (index + 1) % radial_sides
                face_counts.append(4)
                face_connects.extend(
                    (
                        ring_base + index,
                        ring_base + next_index,
                        next_ring_base + next_index,
                        next_ring_base + index,
                    )
                )

        face_counts.append(radial_sides)
        face_connects.extend(base + index for index in reversed(range(radial_sides)))
        face_counts.append(radial_sides)
        face_connects.extend(
            base + radius_rings * radial_sides + index
            for index in range(radial_sides)
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


def _set_bool_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="bool")
    cmds.setAttr(node + "." + attr, bool(value))


def _set_long_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="long")
    cmds.setAttr(node + "." + attr, int(value))


def _set_string_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, dataType="string")
    cmds.setAttr(node + "." + attr, value, type="string")


def _ensure_user_overrides_group(cmds, root, name):
    group = cmds.group(empty=True, name=name + "_User_Overrides", parent=root)
    _set_bool_attr(cmds, group, "lsystemUserOverrides", True)
    return group


def create_tree_in_maya(
    config=None,
    name="LSystemTree",
    radial_sides=8,
    create_tip_locators=False,
    radius_rings=4,
):
    """Generate a tree and create one Maya mesh plus optional tip locators.

    Parameters:
        config (TreeConfig|None): Tree configuration.  Defaults to the
            ``broadleaf_round`` preset.
        name (str): Maya node name prefix for the generated tree root.
        radial_sides (int): Cross-section vertex count per branch end.
        create_tip_locators (bool): If True, add a locator at every
            growth tip (used as flower sockets by the foliage layer).
    """
    try:
        import maya.api.OpenMaya as om
        import maya.cmds as cmds
    except ImportError:
        # ``raise X from Y`` is Python 3+ syntax  -  Maya's Python 2.7
        # raises SyntaxError at import ("parse error").  Plain raise is
        # the 2.7-compatible form.
        raise RuntimeError("This function must run inside Maya")

    config = config or TreeConfig.from_preset("broadleaf_round")
    model = generate_tree(config)
    raw_points, face_counts, face_connects = build_mesh_arrays(
        model, radial_sides, radius_rings
    )
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
        _set_bool_attr(cmds, transform, "lsystemBranchesManaged", True)
        cmds.polySoftEdge(transform, angle=55.0, constructionHistory=False)
        cmds.sets(
            transform,
            edit=True,
            forceElement=_get_bark_shading_group(cmds),
        )

        tip_group = None
        if create_tip_locators:
            tip_group = cmds.group(empty=True, name=name + "_Tips", parent=root)
            _set_bool_attr(cmds, tip_group, "lsystemTipsManaged", True)
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
        _set_bool_attr(cmds, root, "lsystemEditableTree", True)
        _set_long_attr(cmds, root, "radialSides", radial_sides)
        _set_long_attr(cmds, root, "radiusRings", radius_rings)
        _set_bool_attr(cmds, root, "createTipLocators", create_tip_locators)
        _set_string_attr(
            cmds,
            root,
            "treeConfigJson",
            json.dumps(config.as_dict(), sort_keys=True),
        )
        _ensure_user_overrides_group(cmds, root, name)

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
