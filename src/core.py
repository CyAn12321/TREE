# -*- coding: utf-8 -*-
"""Pure-Python L-System and 3D turtle implementation.

The output is a topological branch graph, independent of Maya.  Maya-specific
code converts the graph into a single polygon mesh.
"""

from __future__ import division, print_function

import math

from .math_utils import (
    EPSILON,
    stable_unit,
    add as _add,
    sub as _sub,
    mul as _mul,
    dot as _dot,
    cross as _cross,
    length as _length,
    normalize_strict as _normalize,
)


# Algorithm provenance: the two-stage L-System derivation plus 3D turtle
# interpretation follows the general method described by Prusinkiewicz and
# Lindenmayer, *The Algorithmic Beauty of Plants*.  This module contains the
# project's own implementation; no external source code is copied here.


class LModule(object):
    """Typed L-System symbol carrying a persistent derivation identity."""

    __slots__ = ("name", "parameters", "path_id")

    def __init__(self, name, parameters=(), path_id="0"):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            name: Input value used by this function.
            parameters: Input value used by this function.
            path_id: Input value used by this function.
        """
        self.name = str(name)
        self.parameters = tuple(parameters)
        self.path_id = str(path_id)

    def __str__(self):
        """Return the readable string representation of this object.
        """
        return self.name


def _rotate(vector, axis, radians):
    """Rodrigues rotation around an arbitrary axis."""
    axis = _normalize(axis)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return _add(
        _add(_mul(vector, cosine), _mul(_cross(axis, vector), sine)),
        _mul(axis, _dot(axis, vector) * (1.0 - cosine)),
    )


class TreePreset(object):
    def __init__(self, key, label, description, defaults, rules):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            key: Input value used by this function.
            label: Input value used by this function.
            description: Input value used by this function.
            defaults: Input value used by this function.
            rules: Input value used by this function.
        """
        self.key = key
        self.label = label
        self.description = description
        self.defaults = dict(defaults)
        self.rules = rules


PRESETS = (
    TreePreset(
        key="broadleaf_round",
        label="Broadleaf Round",
        description="Spreading branches and a full crown, resembling a common broadleaf tree silhouette.",
        defaults={
            "trunk_radius": 0.55,
            "branch_levels": 4,
            "branches_per_node": 4,
            "branch_angle": 28.0,
            "segment_length": 1.25,
            "length_decay": 0.76,
            "branch_radius_ratio": 0.67,
            "segment_taper": 0.965,
            "angle_jitter": 6.0,
            "length_jitter": 0.12,
            "internode_branch_density": 0.42,
            "branch_tropism": (0.0, 1.0, 0.0),
            "branch_tropism_strength": 0.07,
        },
        rules={
            "X": (
                (0.48, "F[+&X][-^X]F[\\&X][/&X]X"),
                (0.32, "F[+X][-X]F[&X]X"),
                (0.20, "F[&+X][^-X]F[/+X]X"),
            ),
            "F": ((0.74, "FF"), (0.26, "F")),
        },
    ),
    TreePreset(
        key="conifer_pyramidal",
        label="Conifer Pyramidal",
        description="Clear central axis with many whorled side branches, forming a tapered pyramidal silhouette.",
        defaults={
            "trunk_radius": 0.48,
            "branch_levels": 5,
            "branches_per_node": 4,
            "branch_angle": 38.0,
            "segment_length": 1.10,
            "length_decay": 0.66,
            "branch_radius_ratio": 0.58,
            "segment_taper": 0.975,
            "angle_jitter": 3.5,
            "length_jitter": 0.07,
            "internode_branch_density": 0.56,
            "branch_tropism": (0.0, 1.0, 0.0),
            "branch_tropism_strength": 0.04,
        },
        rules={
            "X": (
                (0.60, "F[+&X][-&X][\\&X][/&X]X"),
                (0.40, "FF[+&X][-&X]X"),
            ),
            "F": ((0.82, "FF"), (0.18, "F")),
        },
    ),
    TreePreset(
        key="willow_weeping",
        label="Weeping Willow",
        description="Trunk grows upward while long side branches gradually droop, forming a weeping silhouette.",
        defaults={
            "trunk_radius": 0.52,
            "branch_levels": 5,
            "branches_per_node": 4,
            "branch_angle": 23.0,
            "segment_length": 1.18,
            "length_decay": 0.84,
            "branch_radius_ratio": 0.64,
            "segment_taper": 0.96,
            "angle_jitter": 7.0,
            "length_jitter": 0.14,
            "internode_branch_density": 0.48,
            "branch_tropism": (0.0, -1.0, 0.0),
            "branch_tropism_strength": 0.14,
        },
        rules={
            "X": (
                (0.55, "F[+&X][-&X]F[\\&X][/&X]X"),
                (0.45, "F[+X][-X]F[&X]X"),
            ),
            "F": ((0.68, "FF"), (0.32, "F")),
        },
    ),
    TreePreset(
        key="columnar_poplar",
        label="Columnar Poplar",
        description="Small branch angles and upward-converging branches form a narrow columnar crown.",
        defaults={
            "trunk_radius": 0.44,
            "branch_levels": 5,
            "branches_per_node": 2,
            "branch_angle": 14.0,
            "segment_length": 1.30,
            "length_decay": 0.70,
            "branch_radius_ratio": 0.60,
            "segment_taper": 0.972,
            "angle_jitter": 3.0,
            "length_jitter": 0.08,
            "internode_branch_density": 0.62,
            "branch_tropism": (0.0, 1.0, 0.0),
            "branch_tropism_strength": 0.18,
        },
        rules={
            "X": (
                (0.70, "F[+^X][-^X]FX"),
                (0.30, "F[\\^X][/^X]FX"),
            ),
            "F": ((0.78, "FF"), (0.22, "F")),
        },
    ),
)


def list_presets():
    """Return all available tree presets (broadleaf, conifer, willow, poplar).

    Returns:
        tuple[TreePreset]: Immutable tuple of all registered presets.
    """
    return PRESETS


def get_preset(key):
    """Return the tree preset with the given key.

    Parameters:
        key (str): Preset identifier (e.g. "broadleaf_round",
            "conifer_pyramidal", "willow_weeping", "columnar_poplar").
    """
    for preset in PRESETS:
        if preset.key == key:
            return preset
    raise KeyError("Unknown tree preset: {}".format(key))


class TreeConfig(object):
    """Complete generation configuration with required user overrides."""

    def __init__(
        self,
        preset_key="broadleaf_round",
        trunk_radius=0.55,
        branch_levels=4,
        branches_per_node=4,
        branch_angle=28.0,
        segment_length=1.25,
        length_decay=0.76,
        branch_radius_ratio=0.67,
        segment_taper=0.965,
        angle_jitter=6.0,
        length_jitter=0.12,
        internode_branch_density=0.42,
        branch_tropism=(0.0, 1.0, 0.0),
        branch_tropism_strength=0.07,
        minimum_radius=0.016,
        seed=17,
        max_symbols=180000,
    ):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            preset_key: Input value used by this function.
            trunk_radius: Input value used by this function.
            branch_levels: Input value used by this function.
            branches_per_node: Input value used by this function.
            branch_angle: Input value used by this function.
            segment_length: Input value used by this function.
            length_decay: Input value used by this function.
            branch_radius_ratio: Input value used by this function.
            segment_taper: Input value used by this function.
            angle_jitter: Input value used by this function.
            length_jitter: Input value used by this function.
            internode_branch_density: Input value used by this function.
            branch_tropism: Input value used by this function.
            branch_tropism_strength: Input value used by this function.
            minimum_radius: Input value used by this function.
            seed: Input value used by this function.
            max_symbols: Input value used by this function.
        """
        self.preset_key = preset_key
        self.trunk_radius = float(trunk_radius)
        self.branch_levels = int(branch_levels)
        self.branches_per_node = int(branches_per_node)
        self.branch_angle = float(branch_angle)
        self.segment_length = float(segment_length)
        self.length_decay = float(length_decay)
        self.branch_radius_ratio = float(branch_radius_ratio)
        self.segment_taper = float(segment_taper)
        self.angle_jitter = float(angle_jitter)
        self.length_jitter = float(length_jitter)
        self.internode_branch_density = float(internode_branch_density)
        self.branch_tropism = tuple(float(value) for value in branch_tropism)
        self.branch_tropism_strength = float(branch_tropism_strength)
        self.minimum_radius = float(minimum_radius)
        self.seed = int(seed)
        self.max_symbols = int(max_symbols)
        self.validate()

    @classmethod
    def from_preset(cls, preset_key, **overrides):
        """Execute the from preset operation.

        Parameters:
            preset_key: Input value used by this function.
            overrides: Input value used by this function.
        """
        preset = get_preset(preset_key)
        values = dict(preset.defaults)
        values.update(overrides)
        values["preset_key"] = preset_key
        return cls(**values)

    def validate(self):
        """Validate the current configuration and raise ValueError for invalid input.
        """
        get_preset(self.preset_key)
        if self.trunk_radius <= 0.0:
            raise ValueError("trunk_radius must be positive")
        if not 1 <= self.branch_levels <= 7:
            raise ValueError("branch_levels must be between 1 and 7")
        if not 1 <= self.branches_per_node <= 6:
            raise ValueError("branches_per_node must be between 1 and 6")
        if not 1.0 <= self.branch_angle <= 80.0:
            raise ValueError("branch_angle must be between 1 and 80 degrees")
        if self.segment_length <= 0.0:
            raise ValueError("segment_length must be positive")
        if not 0.0 < self.length_decay <= 1.0:
            raise ValueError("length_decay must be in (0, 1]")
        if not 0.0 < self.branch_radius_ratio < 1.0:
            raise ValueError("branch_radius_ratio must be in (0, 1)")
        if not 0.0 < self.segment_taper <= 1.0:
            raise ValueError("segment_taper must be in (0, 1]")
        if self.angle_jitter < 0.0:
            raise ValueError("angle_jitter cannot be negative")
        if not 0.0 <= self.length_jitter < 1.0:
            raise ValueError("length_jitter must be in [0, 1)")
        if not 0.0 <= self.internode_branch_density <= 1.0:
            raise ValueError("internode_branch_density must be in [0, 1]")
        if not 0.0 <= self.branch_tropism_strength <= 1.0:
            raise ValueError("branch_tropism_strength must be in [0, 1]")
        if self.minimum_radius <= 0.0:
            raise ValueError("minimum_radius must be positive")
        if self.max_symbols <= 0:
            raise ValueError("max_symbols must be positive")
        _normalize(self.branch_tropism)

    def as_dict(self):
        """Convert this object to dict.
        """
        return dict(self.__dict__)


class BranchSegment(object):
    __slots__ = (
        "index",
        "parent_index",
        "depth",
        "start",
        "end",
        "start_radius",
        "end_radius",
        "path_id",
        "heading",
        "left",
        "up",
    )

    def __init__(
        self,
        index,
        parent_index,
        depth,
        start,
        end,
        start_radius,
        end_radius,
        path_id=None,
        heading=None,
        left=None,
        up=None,
    ):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            index: Input value used by this function.
            parent_index: Input value used by this function.
            depth: Input value used by this function.
            start: Input value used by this function.
            end: Input value used by this function.
            start_radius: Input value used by this function.
            end_radius: Input value used by this function.
            path_id: Input value used by this function.
            heading: Input value used by this function.
            left: Input value used by this function.
            up: Input value used by this function.
        """
        self.index = index
        self.parent_index = parent_index
        self.depth = depth
        self.start = start
        self.end = end
        self.start_radius = start_radius
        self.end_radius = end_radius
        self.path_id = str(path_id if path_id is not None else index)
        self.heading = heading or _normalize(_sub(end, start))
        self.left = left or (-1.0, 0.0, 0.0)
        self.up = up or _normalize(_cross(self.heading, self.left))


class GrowthTip(object):
    __slots__ = ("position", "direction", "depth", "parent_segment", "path_id")

    def __init__(self, position, direction, depth, parent_segment, path_id=None):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            position: Input value used by this function.
            direction: Input value used by this function.
            depth: Input value used by this function.
            parent_segment: Input value used by this function.
            path_id: Input value used by this function.
        """
        self.position = position
        self.direction = direction
        self.depth = depth
        self.parent_segment = parent_segment
        self.path_id = str(path_id if path_id is not None else parent_segment)


class AttachmentPoint(object):
    """Stable organ socket exported by the tree generator."""

    __slots__ = (
        "id", "kind", "segment_index", "amount", "position", "tangent",
        "normal", "binormal", "depth", "exposure", "seed",
    )

    def __init__(self, identity, kind, segment_index, amount, position, tangent,
                 normal, binormal, depth, exposure, seed):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            identity: Input value used by this function.
            kind: Input value used by this function.
            segment_index: Input value used by this function.
            amount: Input value used by this function.
            position: Input value used by this function.
            tangent: Input value used by this function.
            normal: Input value used by this function.
            binormal: Input value used by this function.
            depth: Input value used by this function.
            exposure: Input value used by this function.
            seed: Input value used by this function.
        """
        self.id = str(identity)
        self.kind = str(kind)
        self.segment_index = segment_index
        self.amount = float(amount)
        self.position = position
        self.tangent = tangent
        self.normal = normal
        self.binormal = binormal
        self.depth = int(depth)
        self.exposure = float(exposure)
        self.seed = int(seed)


class BranchGraph(object):
    def __init__(self, segments):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            segments: Input value used by this function.
        """
        self.segments = segments
        self.children = dict((segment.index, []) for segment in segments)
        self.roots = []
        for segment in segments:
            if segment.parent_index is None:
                self.roots.append(segment.index)
            else:
                self.children[segment.parent_index].append(segment.index)

    def terminal_indices(self):
        """Return terminal-branch information for the graph.
        """
        return [index for index, children in self.children.items() if not children]


class TreeModel(object):
    def __init__(self, config, expanded_string, segments, tips, modules=None,
                 attachment_points=None):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            config: Input value used by this function.
            expanded_string: Input value used by this function.
            segments: Input value used by this function.
            tips: Input value used by this function.
            modules: Input value used by this function.
            attachment_points: Input value used by this function.
        """
        self.config = config
        self.expanded_string = expanded_string
        self.segments = segments
        self.tips = tips
        self.modules = tuple(modules or ())
        self.graph = BranchGraph(segments)
        self.attachment_points = tuple(attachment_points or ())

    def bounds(self):
        """Execute the bounds operation.
        """
        points = []
        for segment in self.segments:
            points.extend((segment.start, segment.end))
        minimum = tuple(min(point[axis] for point in points) for axis in range(3))
        maximum = tuple(max(point[axis] for point in points) for axis in range(3))
        return minimum, maximum

    def maximum_depth(self):
        """Return the maximum value represented by this object.
        """
        return max(segment.depth for segment in self.segments)


class _TurtleState(object):
    __slots__ = (
        "position",
        "heading",
        "left",
        "up",
        "radius",
        "depth",
        "last_segment",
    )

    def __init__(
        self,
        position=(0.0, 0.0, 0.0),
        heading=(0.0, 1.0, 0.0),
        left=(-1.0, 0.0, 0.0),
        up=(0.0, 0.0, 1.0),
        radius=1.0,
        depth=0,
        last_segment=None,
    ):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            position: Input value used by this function.
            heading: Input value used by this function.
            left: Input value used by this function.
            up: Input value used by this function.
            radius: Input value used by this function.
            depth: Input value used by this function.
            last_segment: Input value used by this function.
        """
        self.position = position
        self.heading = heading
        self.left = left
        self.up = up
        self.radius = radius
        self.depth = depth
        self.last_segment = last_segment

    def copy(self):
        """Return a copy of this object.
        """
        return _TurtleState(
            self.position,
            self.heading,
            self.left,
            self.up,
            self.radius,
            self.depth,
            self.last_segment,
        )

    def rotate(self, axis, radians):
        """Execute the rotate operation.

        Parameters:
            axis: Input value used by this function.
            radians: Input value used by this function.
        """
        self.heading = _normalize(_rotate(self.heading, axis, radians))
        self.left = _normalize(_rotate(self.left, axis, radians))
        self.up = _normalize(_cross(self.heading, self.left))
        self.left = _normalize(_cross(self.up, self.heading))


def _weighted_successor_value(options, value):
    """Internal helper for weighted successor value.

    Parameters:
        options: Input value used by this function.
        value: Input value used by this function.
    """
    if any(weight < 0.0 for weight, unused_successor in options):
        raise ValueError("L-System rule weights cannot be negative")
    total = sum(weight for weight, unused_successor in options)
    if total <= 0.0:
        raise ValueError("L-System rule weights must have a positive sum")
    target = value * total
    accumulated = 0.0
    for weight, successor in options:
        accumulated += weight
        if target <= accumulated:
            return successor
    return options[-1][1]


BRANCH_GROUPS_BY_PRESET = {
    "broadleaf_round": (
        "[+&X]",
        "[-&X]",
        "[\\&X]",
        "[/&X]",
        "[+^X]",
        "[-^X]",
    ),
    "conifer_pyramidal": (
        "[+&X]",
        "[-&X]",
        "[\\&X]",
        "[/&X]",
        "[+X]",
        "[-X]",
    ),
    "willow_weeping": (
        "[+&X]",
        "[-&X]",
        "[\\&X]",
        "[/&X]",
        "[&+X]",
        "[&-X]",
    ),
    "columnar_poplar": (
        "[+^X]",
        "[-^X]",
        "[\\^X]",
        "[/^X]",
        "[+X]",
        "[-X]",
    ),
}


INTERNODE_GROUP_BY_PRESET = {
    "broadleaf_round": "[+&X]",
    "conifer_pyramidal": "[+&X]",
    "willow_weeping": "[&+X]",
    "columnar_poplar": "[+^X]",
}


def _add_internode_branch_site(replacement, module, iteration, seed,
                               config_density, preset_key):
    """Add a recursive lateral bud between F segments at stable random sites.

    Existing X rules control branching at growth points.  This separate rule
    adds branching opportunities along internodes, so density can increase
    without merely increasing the number of children at each X.
    """
    if config_density <= 0.0 or not replacement:
        return replacement
    if stable_unit(seed, module.path_id, "internode-density:{}".format(iteration)) > config_density:
        return replacement
    group = INTERNODE_GROUP_BY_PRESET.get(
        preset_key, INTERNODE_GROUP_BY_PRESET["broadleaf_round"]
    )
    insert_at = 1 if replacement.startswith("FF") else 0
    return replacement[:insert_at] + group + replacement[insert_at:]


def _top_level_branch_spans(successor):
    """Internal helper for top level branch spans.

    Parameters:
        successor: Input value used by this function.
    """
    spans = []
    depth = 0
    start = None
    for index, symbol in enumerate(successor):
        if symbol == "[":
            if depth == 0:
                start = index
            depth += 1
        elif symbol == "]":
            depth -= 1
            if depth == 0 and start is not None:
                spans.append((start, index + 1, successor[start : index + 1]))
                start = None
    return spans


def _rewrite_successor_branch_count(successor, branch_count, preset_key):
    """Resize the top-level lateral branch set while retaining the main axis."""
    spans = _top_level_branch_spans(successor)
    if not spans or len(spans) == branch_count:
        return successor

    if branch_count < len(spans):
        if branch_count == 1:
            selected_indices = {0}
        else:
            selected_indices = {
                int(round(index * (len(spans) - 1) / float(branch_count - 1)))
                for index in range(branch_count)
            }
        pieces = []
        cursor = 0
        for span_index, (start, end, unused_group) in enumerate(spans):
            pieces.append(successor[cursor:start])
            if span_index in selected_indices:
                pieces.append(successor[start:end])
            cursor = end
        pieces.append(successor[cursor:])
        return "".join(pieces)

    existing_groups = {group for unused_start, unused_end, group in spans}
    candidates = BRANCH_GROUPS_BY_PRESET.get(
        preset_key,
        BRANCH_GROUPS_BY_PRESET["broadleaf_round"],
    )
    extras = [group for group in candidates if group not in existing_groups]
    needed = branch_count - len(spans)
    if len(extras) < needed:
        extras.extend(candidates[: needed - len(extras)])
    main_axis_index = successor.rfind("X")
    return (
        successor[:main_axis_index]
        + "".join(extras[:needed])
        + successor[main_axis_index:]
    )


def expand_lsystem(
    axiom,
    rules,
    iterations,
    seed,
    max_symbols,
    branches_per_node=None,
    internode_branch_density=0.0,
    preset_key="broadleaf_round",
):
    """Expand an L-System axiom into a flat symbol string.

    Parameters:
        axiom (str): Start symbol (typically "X").
        rules (dict[str, tuple]): Map from symbol to weighted alternatives,
            e.g. ``{"X": ((0.5, "F[+X]"), (0.5, "F[-X]"))}``.
        iterations (int): Number of derivation passes (== branch_levels).
        seed (int): Reproducible seed for path-stable randomness.
        max_symbols (int): Hard cap on total symbol count to prevent
            runaway expansion.
        branches_per_node (int|None): If set, resize each X successor's
            top-level lateral branch group to this count.
        preset_key (str): Tree preset key used for branch group selection.
    """
    modules = expand_lsystem_modules(
        axiom,
        rules,
        iterations,
        seed,
        max_symbols,
        branches_per_node=branches_per_node,
        internode_branch_density=internode_branch_density,
        preset_key=preset_key,
    )
    return "".join(module.name for module in modules)


def expand_lsystem_modules(
    axiom,
    rules,
    iterations,
    seed,
    max_symbols,
    branches_per_node=None,
    internode_branch_density=0.0,
    preset_key="broadleaf_round",
):
    """Expand into identity-carrying modules using path-stable randomness.

    Parameters:
        axiom (str): Start symbol (typically "X").
        rules (dict[str, tuple]): Weighted alternatives per symbol.
        iterations (int): Derivation passes (= branch_levels).
        seed (int): Reproducible seed feeding ``stable_unit``.
        max_symbols (int): Hard cap; raises ValueError if exceeded.
        branches_per_node (int|None): Resize top-level branch groups.
        preset_key (str): Tree preset key for branch group candidates.
    """
    current = [LModule(symbol, path_id="a{}".format(index)) for index, symbol in enumerate(str(axiom))]
    for iteration in range(iterations):
        pieces = []
        total_length = 0
        for module in current:
            symbol = module.name
            replacement = (
                _weighted_successor_value(
                    rules[symbol],
                    stable_unit(seed, module.path_id, "rewrite:{}".format(iteration)),
                )
                if symbol in rules
                else symbol
            )
            if symbol == "X" and branches_per_node is not None:
                replacement = _rewrite_successor_branch_count(
                    replacement,
                    branches_per_node,
                    preset_key,
                )
            if symbol == "F" and iteration < iterations - 1:
                replacement = _add_internode_branch_site(
                    replacement,
                    module,
                    iteration,
                    seed,
                    internode_branch_density,
                    preset_key,
                )
            pieces.extend(
                LModule(
                    child_symbol,
                    path_id="{}.{}.{}".format(module.path_id, iteration, child_index),
                )
                for child_index, child_symbol in enumerate(replacement)
            )
            total_length += len(replacement)
            if total_length > max_symbols:
                raise ValueError(
                    "L-System exceeded max_symbols={} at level {}".format(
                        max_symbols,
                        iteration + 1,
                    )
                )
        current = pieces
    return current


def _apply_branch_tropism(state, config):
    """Internal helper for apply branch tropism.

    Parameters:
        state: Input value used by this function.
        config: Input value used by this function.
    """
    if state.depth == 0 or config.branch_tropism_strength <= 0.0:
        return
    target = _normalize(config.branch_tropism)
    perpendicular = _sub(target, _mul(state.heading, _dot(target, state.heading)))
    if _length(perpendicular) <= EPSILON:
        return
    desired = _normalize(
        _add(
            state.heading,
            _mul(perpendicular, config.branch_tropism_strength),
        )
    )
    axis = _cross(state.heading, desired)
    if _length(axis) <= EPSILON:
        return
    axis = _normalize(axis)
    cosine = max(-1.0, min(1.0, _dot(state.heading, desired)))
    radians = math.acos(cosine)
    state.heading = desired
    state.left = _normalize(_rotate(state.left, axis, radians))
    state.up = _normalize(_cross(state.heading, state.left))
    state.left = _normalize(_cross(state.up, state.heading))


def interpret_lsystem(symbols, config):
    """Interpret an L-System symbol string as a 3D branch graph.

    Walks the symbol stream with a turtle state machine.  ``F`` emits a
    BranchSegment, ``[``/``]`` push/pop the turtle stack, ``+ - & ^ \\ /``
    rotate around heading/left/up axes, ``!`` shrinks the radius.

    Parameters:
        symbols (str|list): Symbol string or list of LModule objects.
        config (TreeConfig): Provides branch_angle, segment_length,
            length_decay, branch_radius_ratio, segment_taper, jitter
            strengths and tropism vector.
    """
    state = _TurtleState(radius=config.trunk_radius)
    stack = []
    segments = []
    tips = []

    def angle(module, sign=1.0):
        """Return the angle represented by this vector or branch state.

        Parameters:
            module: Input value used by this function.
            sign: Input value used by this function.
        """
        jitter = stable_unit(config.seed, module.path_id, "angle") * 2.0 - 1.0
        degrees = config.branch_angle + jitter * config.angle_jitter
        return math.radians(degrees) * sign

    for symbol_index, raw_module in enumerate(symbols):
        module = raw_module if isinstance(raw_module, LModule) else LModule(raw_module, path_id="legacy{}".format(symbol_index))
        symbol = module.name
        if symbol in ("F", "f"):
            _apply_branch_tropism(state, config)
            step = config.segment_length * (config.length_decay ** state.depth)
            length_jitter = stable_unit(config.seed, module.path_id, "length") * 2.0 - 1.0
            step *= 1.0 + length_jitter * config.length_jitter
            new_position = _add(state.position, _mul(state.heading, step))
            if symbol == "F":
                start_radius = max(config.minimum_radius, state.radius)
                end_radius = max(
                    config.minimum_radius,
                    start_radius * config.segment_taper,
                )
                segment = BranchSegment(
                    index=len(segments),
                    parent_index=state.last_segment,
                    depth=state.depth,
                    start=state.position,
                    end=new_position,
                    start_radius=start_radius,
                    end_radius=end_radius,
                    path_id=module.path_id,
                    heading=state.heading,
                    left=state.left,
                    up=state.up,
                )
                segments.append(segment)
                state.last_segment = segment.index
                state.radius = end_radius
            state.position = new_position
        elif symbol == "+":
            state.rotate(state.up, angle(module, 1.0))
        elif symbol == "-":
            state.rotate(state.up, angle(module, -1.0))
        elif symbol == "&":
            state.rotate(state.left, angle(module, 1.0))
        elif symbol == "^":
            state.rotate(state.left, angle(module, -1.0))
        elif symbol == "\\":
            state.rotate(state.heading, angle(module, 1.0))
        elif symbol == "/":
            state.rotate(state.heading, angle(module, -1.0))
        elif symbol == "|":
            state.rotate(state.up, math.pi)
        elif symbol == "[":
            stack.append(state.copy())
            state.depth += 1
            state.radius = max(
                config.minimum_radius,
                state.radius * config.branch_radius_ratio,
            )
        elif symbol == "]":
            if not stack:
                raise ValueError("Unmatched closing bracket in L-System")
            state = stack.pop()
        elif symbol == "!":
            state.radius = max(
                config.minimum_radius,
                state.radius * config.branch_radius_ratio,
            )
        elif symbol == "X":
            tips.append(
                GrowthTip(
                    state.position,
                    state.heading,
                    state.depth,
                    state.last_segment,
                    module.path_id,
                )
            )

    if stack:
        raise ValueError("Unmatched opening bracket in L-System")
    return segments, tips


def _apply_pipe_model(segments, config, exponent=2.3):
    """Size branches from supported terminal load (Leonardo/pipe model)."""
    graph = BranchGraph(segments)
    loads = {}

    def terminal_load(index):
        """Return terminal-branch information for the graph.

        Parameters:
            index: Input value used by this function.
        """
        children = graph.children[index]
        loads[index] = 1.0 if not children else sum(terminal_load(child) for child in children)
        return loads[index]

    for root in graph.roots:
        terminal_load(root)
    root_load = max(loads[root] for root in graph.roots)

    # Compute the load-driven target first.  A child used to start at
    # ``min(parent.end_radius, target_radius)`` which created a visible step
    # at every fork.  The parent endpoint is now the shared junction radius;
    # the child eases down to its own target over its first segment.
    target_radii = {}
    for segment in segments:
        target_radius = config.trunk_radius * (
            (loads[segment.index] / root_load) ** (1.0 / exponent)
        )
        target_radii[segment.index] = max(
            config.minimum_radius,
            target_radius * config.branch_radius_ratio ** (segment.depth * 0.22),
        )

    for segment in segments:
        if segment.parent_index is None:
            segment.start_radius = config.trunk_radius
        else:
            # Every parent/child pair shares the same radius at the junction.
            # This is especially important at a fork, where the old min()
            # caused the child cylinder to become thin immediately.
            segment.start_radius = max(
                config.minimum_radius,
                segments[segment.parent_index].end_radius,
            )
        segment.end_radius = max(
            config.minimum_radius,
            min(
                segment.start_radius * config.segment_taper,
                target_radii[segment.index],
            ),
        )


_GOLDEN_ANGLE = 2.0 * math.pi * (1.0 - (math.sqrt(5.0) - 1.0) / 2.0)  # ~137.5 degrees


def build_attachment_points(segments, tips, config, samples_per_segment=3):
    """Derive persistent leaf/flower sockets from the interpreted branch graph.

    Leaf sockets follow a phyllotaxis (golden-angle spiral) around each
    branch segment so that leaves are distributed naturally around the
    circumference instead of clustering on one side.  The ``normal`` of
    each socket points radially outward from the branch axis at a rotation
    of ``sample_index * golden_angle``, and the ``binormal`` is rotated
    consistently to preserve the orthonormal frame.

    Parameters:
        segments (list[BranchSegment]): Branch segments from
            ``interpret_lsystem``.
        tips (list[GrowthTip]): Branch tips (growth endpoints).
        config (TreeConfig): Provides seed for deterministic socket ids.
        samples_per_segment (int): Leaf sockets per eligible segment.
    """
    if not segments:
        return []
    maximum_depth = max(segment.depth for segment in segments)
    # Never place leaf sockets on the trunk (depth 0); leaves and flowers
    # should only grow on branches, not on the main trunk.
    minimum_depth = max(1, maximum_depth - 3)
    points = []
    for segment in segments:
        if segment.depth < minimum_depth:
            continue
        # Internode shortening: terminal branches (high depth) have
        # shortened internodes so leaves cluster toward the tip  -
        # mimics real woody plants' short shoots (brachyblasts).
        # A power curve with exponent < 1 pushes samples toward amount=1.
        depth_ratio = segment.depth / float(maximum_depth or 1)
        cluster_power = 1.0 - 0.45 * depth_ratio  # 1.0 at base, 0.55 at tip
        for sample_index in range(samples_per_segment):
            raw_amount = (sample_index + 1.0) / (samples_per_segment + 1.0)
            amount = raw_amount ** cluster_power
            identity = "leaf:{}:{}".format(segment.path_id, sample_index)
            position = _add(segment.start, _mul(_sub(segment.end, segment.start), amount))
            exposure = 0.55 + 0.45 * (segment.depth / float(maximum_depth or 1))
            # Rotate the socket normal around the branch heading using the
            # golden-angle spiral so successive samples are distributed
            # around the circumference (phyllotaxis), not stacked on one side.
            angle = sample_index * _GOLDEN_ANGLE
            rotated_normal = _rotate(segment.up, segment.heading, angle)
            rotated_binormal = _rotate(segment.left, segment.heading, angle)
            points.append(
                AttachmentPoint(
                    identity, "leaf", segment.index, amount, position,
                    segment.heading, rotated_normal, rotated_binormal, segment.depth,
                    exposure, int(stable_unit(config.seed, identity, "socket") * 2147483647),
                )
            )
    seen = set()
    for tip in tips:
        key = tuple(round(value, 5) for value in tip.position)
        if key in seen:
            continue
        seen.add(key)
        segment = segments[tip.parent_segment] if tip.parent_segment is not None else segments[0]
        identity = "flower:{}".format(tip.path_id)
        points.append(
            AttachmentPoint(
                identity, "flower", tip.parent_segment, 1.0, tip.position,
                tip.direction, segment.up, segment.left, tip.depth, 1.0,
                int(stable_unit(config.seed, identity, "socket") * 2147483647),
            )
        )
    return points


def generate_tree(config=None):
    """Generate a complete tree model from the given configuration.

    Parameters:
        config (TreeConfig|None): Full generation config.  Defaults to
            ``TreeConfig.from_preset("broadleaf_round")``.
    """
    config = config or TreeConfig.from_preset("broadleaf_round")
    preset = get_preset(config.preset_key)
    modules = expand_lsystem_modules(
        axiom="X",
        rules=preset.rules,
        iterations=config.branch_levels,
        seed=config.seed,
        max_symbols=config.max_symbols,
        branches_per_node=config.branches_per_node,
        internode_branch_density=config.internode_branch_density,
        preset_key=config.preset_key,
    )
    expanded = "".join(module.name for module in modules)
    segments, tips = interpret_lsystem(modules, config)
    if not segments:
        raise ValueError("The selected configuration generated no branch segments")
    _apply_pipe_model(segments, config)
    attachment_points = build_attachment_points(segments, tips, config)
    return TreeModel(config, expanded, segments, tips, modules, attachment_points)
