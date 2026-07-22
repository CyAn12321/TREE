"""Season-driven leaf and flower distribution independent of Maya."""

from __future__ import division, print_function

import random

from .assets import OrganAssetLibrary, stable_unit


class SeasonProfile(object):
    def __init__(
        self,
        key,
        label,
        description,
        leaf_density,
        leaf_size,
        leaf_palette,
        flower_density,
        flower_size,
        flower_palette,
        flower_openness,
        flower_wilt,
        center_color,
    ):
        self.key = key
        self.label = label
        self.description = description
        self.leaf_density = float(leaf_density)
        self.leaf_size = float(leaf_size)
        self.leaf_palette = tuple(leaf_palette)
        self.flower_density = float(flower_density)
        self.flower_size = float(flower_size)
        self.flower_palette = tuple(flower_palette)
        self.flower_openness = float(flower_openness)
        self.flower_wilt = float(flower_wilt)
        self.center_color = tuple(center_color)


SEASONS = (
    SeasonProfile(
        key="spring",
        label="春季",
        description="嫩叶逐渐展开，花朵数量最多且花瓣充分开放。",
        leaf_density=0.62,
        leaf_size=0.34,
        leaf_palette=(
            (0.42, 0.76, 0.16),
            (0.28, 0.64, 0.10),
            (0.58, 0.82, 0.24),
        ),
        flower_density=0.52,
        flower_size=0.34,
        flower_palette=(
            (1.00, 0.55, 0.68),
            (1.00, 0.78, 0.84),
            (0.96, 0.92, 0.88),
        ),
        flower_openness=0.96,
        flower_wilt=0.02,
        center_color=(0.95, 0.68, 0.08),
    ),
    SeasonProfile(
        key="summer",
        label="夏季",
        description="叶片最大且最茂密，颜色转为深绿，仅保留少量成熟花朵。",
        leaf_density=0.96,
        leaf_size=0.46,
        leaf_palette=(
            (0.08, 0.42, 0.08),
            (0.12, 0.52, 0.10),
            (0.18, 0.58, 0.14),
        ),
        flower_density=0.10,
        flower_size=0.32,
        flower_palette=(
            (0.95, 0.48, 0.60),
            (0.92, 0.68, 0.76),
            (0.98, 0.88, 0.84),
        ),
        flower_openness=0.82,
        flower_wilt=0.16,
        center_color=(0.82, 0.53, 0.04),
    ),
    SeasonProfile(
        key="autumn",
        label="秋季",
        description="叶量下降并切换为黄、橙、红色；残花缩小、下垂并变暗。",
        leaf_density=0.58,
        leaf_size=0.42,
        leaf_palette=(
            (0.95, 0.62, 0.05),
            (0.86, 0.28, 0.03),
            (0.68, 0.12, 0.035),
        ),
        flower_density=0.075,
        flower_size=0.27,
        flower_palette=(
            (0.48, 0.16, 0.18),
            (0.38, 0.13, 0.10),
            (0.55, 0.26, 0.20),
        ),
        flower_openness=0.30,
        flower_wilt=0.84,
        center_color=(0.34, 0.20, 0.05),
    ),
    SeasonProfile(
        key="winter",
        label="冬季",
        description="绝大多数叶片和花朵脱落，仅保留极少量枯叶。",
        leaf_density=0.025,
        leaf_size=0.30,
        leaf_palette=(
            (0.30, 0.17, 0.06),
            (0.40, 0.24, 0.08),
            (0.23, 0.13, 0.05),
        ),
        flower_density=0.0,
        flower_size=0.22,
        flower_palette=((0.24, 0.12, 0.10),),
        flower_openness=0.0,
        flower_wilt=1.0,
        center_color=(0.22, 0.14, 0.05),
    ),
)


def list_seasons():
    return SEASONS


def get_season(key):
    for season in SEASONS:
        if season.key == key:
            return season
    raise KeyError("Unknown season: {}".format(key))


class FoliageConfig(object):
    def __init__(
        self,
        season="spring",
        leaf_density_multiplier=1.0,
        leaf_size_multiplier=1.0,
        canopy_spread_multiplier=1.0,
        flower_density_multiplier=1.0,
        flower_size_multiplier=1.0,
        seed=101,
        samples_per_terminal_segment=4,
        leaves_per_cluster=5,
        flowers_per_tip=3,
        max_leaves=12000,
        max_flowers=2500,
    ):
        self.season = season
        self.leaf_density_multiplier = float(leaf_density_multiplier)
        self.leaf_size_multiplier = float(leaf_size_multiplier)
        self.canopy_spread_multiplier = float(canopy_spread_multiplier)
        self.flower_density_multiplier = float(flower_density_multiplier)
        self.flower_size_multiplier = float(flower_size_multiplier)
        self.seed = int(seed)
        self.samples_per_terminal_segment = int(samples_per_terminal_segment)
        self.leaves_per_cluster = int(leaves_per_cluster)
        self.flowers_per_tip = int(flowers_per_tip)
        self.max_leaves = int(max_leaves)
        self.max_flowers = int(max_flowers)
        self.validate()

    def validate(self):
        get_season(self.season)
        for name in (
            "leaf_density_multiplier",
            "leaf_size_multiplier",
            "canopy_spread_multiplier",
            "flower_density_multiplier",
            "flower_size_multiplier",
        ):
            if getattr(self, name) < 0.0:
                raise ValueError("{} cannot be negative".format(name))
        if self.samples_per_terminal_segment < 1:
            raise ValueError("samples_per_terminal_segment must be positive")
        if self.leaves_per_cluster < 1 or self.flowers_per_tip < 1:
            raise ValueError("cluster sizes must be positive")
        if self.max_leaves < 0 or self.max_flowers < 0:
            raise ValueError("instance limits cannot be negative")


class LeafInstance(object):
    __slots__ = (
        "position",
        "direction",
        "azimuth",
        "length",
        "width",
        "color_index",
        "source_segment",
        "attachment_id",
        "asset_id",
        "state",
    )

    def __init__(
        self,
        position,
        direction,
        azimuth,
        length,
        width,
        color_index,
        source_segment,
        attachment_id=None,
        asset_id=None,
        state="mature",
    ):
        self.position = position
        self.direction = direction
        self.azimuth = azimuth
        self.length = length
        self.width = width
        self.color_index = color_index
        self.source_segment = source_segment
        self.attachment_id = str(attachment_id if attachment_id is not None else source_segment)
        self.asset_id = asset_id
        self.state = state


class FlowerInstance(object):
    __slots__ = (
        "position",
        "direction",
        "azimuth",
        "size",
        "color_index",
        "openness",
        "wilt",
        "source_tip",
        "attachment_id",
        "asset_id",
        "state",
    )

    def __init__(
        self,
        position,
        direction,
        azimuth,
        size,
        color_index,
        openness,
        wilt,
        source_tip,
        attachment_id=None,
        asset_id=None,
        state="bloom",
    ):
        self.position = position
        self.direction = direction
        self.azimuth = azimuth
        self.size = size
        self.color_index = color_index
        self.openness = openness
        self.wilt = wilt
        self.source_tip = source_tip
        self.attachment_id = str(attachment_id if attachment_id is not None else source_tip)
        self.asset_id = asset_id
        self.state = state


class FoliageModel(object):
    def __init__(self, config, profile, leaves, flowers, asset_library=None):
        self.config = config
        self.profile = profile
        self.leaves = leaves
        self.flowers = flowers
        self.asset_library = asset_library


def _sub(a, b):
    return tuple(a[index] - b[index] for index in range(3))


def _add(a, b):
    return tuple(a[index] + b[index] for index in range(3))


def _mul(vector, scalar):
    return tuple(component * scalar for component in vector)


def _length(vector):
    return sum(component * component for component in vector) ** 0.5


def _normalize(vector):
    magnitude = _length(vector)
    if magnitude <= 1.0e-9:
        return (0.0, 1.0, 0.0)
    return _mul(vector, 1.0 / magnitude)


def _spread_direction(direction, rng, spread):
    direction = _normalize(direction)
    jitter = (
        rng.uniform(-spread, spread),
        rng.uniform(-spread, spread),
        rng.uniform(-spread, spread),
    )
    return _normalize(_add(direction, jitter))


def _instance_copies(expected_count, rng):
    whole = int(expected_count)
    remainder = expected_count - whole
    return whole + (1 if rng.random() < remainder else 0)


def _fair_capped_quotas(desired_counts, limit, rng):
    """Cap a global budget without letting early traversal entries monopolize it."""
    desired_counts = [max(0, int(count)) for count in desired_counts]
    if limit <= 0 or not desired_counts:
        return [0] * len(desired_counts)
    if sum(desired_counts) <= limit:
        return desired_counts

    quotas = [0] * len(desired_counts)
    active = [index for index, count in enumerate(desired_counts) if count]
    rng.shuffle(active)
    remaining = limit
    while remaining > 0 and active:
        next_active = []
        for index in active:
            if remaining <= 0:
                break
            quotas[index] += 1
            remaining -= 1
            if quotas[index] < desired_counts[index]:
                next_active.append(index)
        active = next_active
    return quotas


def _canopy_cloud_offset(rng, radius, vertical_scale=1.0, inner_fraction=0.18):
    """Return a volume-distributed offset instead of hugging a branch line."""
    if radius <= 0.0:
        return (0.0, 0.0, 0.0)
    while True:
        direction = (
            rng.uniform(-1.0, 1.0),
            rng.uniform(-1.0, 1.0),
            rng.uniform(-1.0, 1.0),
        )
        direction_length = _length(direction)
        if 1.0e-6 < direction_length <= 1.0:
            break
    direction = _normalize(direction)
    volume_amount = rng.random() ** (1.0 / 3.0)
    distance = radius * (
        inner_fraction + (1.0 - inner_fraction) * volume_amount
    )
    return (
        direction[0] * distance,
        direction[1] * distance * vertical_scale,
        direction[2] * distance,
    )


def _keep_above_canopy_floor(position, canopy_base):
    if position[1] >= canopy_base:
        return position
    return (
        position[0],
        canopy_base + (canopy_base - position[1]) * 0.35,
        position[2],
    )


def _lerp(a, b, amount):
    return tuple(
        a[index] + (b[index] - a[index]) * amount for index in range(3)
    )


LEAF_WIDTH_BY_TREE_PRESET = {
    "broadleaf_round": 0.52,
    "conifer_pyramidal": 0.18,
    "willow_weeping": 0.30,
    "columnar_poplar": 0.42,
}


FLOWER_FACTOR_BY_TREE_PRESET = {
    "broadleaf_round": 1.0,
    "conifer_pyramidal": 0.12,
    "willow_weeping": 0.85,
    "columnar_poplar": 0.55,
}


CANOPY_BASE_FRACTION_BY_TREE_PRESET = {
    "broadleaf_round": 0.20,
    "conifer_pyramidal": 0.06,
    "willow_weeping": 0.0,
    "columnar_poplar": 0.12,
}


CANOPY_SPREAD_BY_TREE_PRESET = {
    "broadleaf_round": 2.35,
    "conifer_pyramidal": 1.15,
    "willow_weeping": 2.25,
    "columnar_poplar": 1.05,
}


CANOPY_VERTICAL_SCALE_BY_TREE_PRESET = {
    "broadleaf_round": 0.72,
    "conifer_pyramidal": 0.48,
    "willow_weeping": 2.05,
    "columnar_poplar": 0.92,
}


# The non-round presets need more foliage-bearing branch layers to close the
# gaps between their characteristic branch structures.  A span of 2 means the
# maximum branch depth and the two preceding depths are eligible.
LEAF_DEPTH_SPAN_BY_TREE_PRESET = {
    "broadleaf_round": 2,
    "conifer_pyramidal": 3,
    "willow_weeping": 4,
    "columnar_poplar": 3,
}


LEAF_DENSITY_BY_TREE_PRESET = {
    "broadleaf_round": 1.0,
    "conifer_pyramidal": 1.65,
    "willow_weeping": 1.35,
    "columnar_poplar": 1.45,
}


def _canopy_radius_scale(preset_key, position, minimum_y, tree_height):
    """Preserve each preset's silhouette while filling its local crown volume."""
    if tree_height <= 1.0e-9:
        height_fraction = 0.5
    else:
        height_fraction = max(
            0.0,
            min(1.0, (position[1] - minimum_y) / tree_height),
        )

    if preset_key == "conifer_pyramidal":
        # A broad skirt and a compact top retain the conifer's tapered outline.
        return 1.30 - height_fraction * 0.68
    if preset_key == "columnar_poplar":
        # Fill the middle of the crown without turning the column into a sphere.
        return 0.82 + 0.22 * (1.0 - abs(height_fraction * 2.0 - 1.0))
    return 1.0


def _finish_canopy_position(
    preset_key,
    position,
    canopy_base,
    minimum_y,
):
    if preset_key != "willow_weeping":
        return _keep_above_canopy_floor(position, canopy_base)
    if position[1] >= minimum_y:
        return position
    # Keep the lowest hanging clusters visible without pushing them back up to
    # the former global canopy floor.
    return (
        position[0],
        minimum_y + (minimum_y - position[1]) * 0.12,
        position[2],
    )


LEAF_STATE_BY_SEASON = {
    "spring": "fresh",
    "summer": "mature",
    "autumn": "dry",
    "winter": "dry",
}


FLOWER_STATE_BY_SEASON = {
    "spring": "bloom",
    "summer": "wilted",
    "autumn": "wilted",
    "winter": "wilted",
}


def _stable_rng(seed, identity):
    return random.Random(int(stable_unit(seed, identity, "instance") * 2147483647))


def generate_foliage(tree_model, config=None):
    """Create reproducible leaf and flower instance data from a tree model."""
    config = config or FoliageConfig(seed=tree_model.config.seed + 101)
    profile = get_season(config.season)
    rng = random.Random(config.seed)
    asset_library = OrganAssetLibrary()
    leaves = []
    flowers = []
    preset_key = tree_model.config.preset_key
    maximum_depth = tree_model.maximum_depth()
    leaf_depth_span = LEAF_DEPTH_SPAN_BY_TREE_PRESET.get(preset_key, 2)
    minimum_leaf_depth = max(0, maximum_depth - leaf_depth_span)
    minimum_bounds, maximum_bounds = tree_model.bounds()
    tree_height = maximum_bounds[1] - minimum_bounds[1]
    canopy_base = minimum_bounds[1] + tree_height * CANOPY_BASE_FRACTION_BY_TREE_PRESET.get(
        preset_key,
        0.18,
    )
    canopy_spread = (
        tree_model.config.segment_length
        * CANOPY_SPREAD_BY_TREE_PRESET.get(preset_key, 1.0)
        * config.canopy_spread_multiplier
    )
    canopy_vertical_scale = CANOPY_VERTICAL_SCALE_BY_TREE_PRESET.get(
        preset_key,
        0.75,
    )
    expected_leaf_copies = (
        profile.leaf_density
        * config.leaf_density_multiplier
        * LEAF_DENSITY_BY_TREE_PRESET.get(preset_key, 1.0)
    )
    leaf_width_ratio = LEAF_WIDTH_BY_TREE_PRESET.get(
        preset_key,
        0.45,
    )

    leaf_sockets_by_segment = {}
    for socket in getattr(tree_model, "attachment_points", ()):
        if socket.kind == "leaf":
            leaf_sockets_by_segment.setdefault(socket.segment_index, []).append(socket)

    leaf_sites = []
    desired_leaf_counts = []
    for segment in tree_model.segments:
        if segment.depth < minimum_leaf_depth:
            continue
        direction = _sub(segment.end, segment.start)
        sockets = leaf_sockets_by_segment.get(segment.index, ())
        if not sockets:
            continue
        sockets = [
            socket for socket in sockets
            if preset_key == "willow_weeping" or socket.position[1] >= canopy_base
        ]
        if not sockets:
            continue
        leaf_sites.append((segment, direction, sockets))
        quota_rng = _stable_rng(config.seed, "leaf-quota:{}".format(segment.path_id))
        desired_leaf_counts.append(
            _instance_copies(
                config.samples_per_terminal_segment * config.leaves_per_cluster
                * expected_leaf_copies,
                quota_rng,
            )
        )

    leaf_quotas = _fair_capped_quotas(
        desired_leaf_counts,
        config.max_leaves,
        rng,
    )
    for site_index, site in enumerate(leaf_sites):
        segment, direction, sockets = site
        for leaf_index in range(leaf_quotas[site_index]):
            socket = sockets[leaf_index % len(sockets)]
            attachment_id = "{}:copy{}".format(socket.id, leaf_index)
            local_rng = _stable_rng(config.seed, attachment_id)
            cluster_center = socket.position
            length = profile.leaf_size * config.leaf_size_multiplier
            length *= local_rng.uniform(0.78, 1.22)
            local_spread = canopy_spread * _canopy_radius_scale(
                preset_key,
                cluster_center,
                minimum_bounds[1],
                tree_height,
            )
            cloud_offset = _canopy_cloud_offset(
                local_rng,
                local_spread,
                vertical_scale=canopy_vertical_scale,
            )
            if preset_key == "willow_weeping":
                # A hanging crown needs organ mass below the supporting twig,
                # not only a wider spherical cloud around it.
                cloud_offset = (
                    cloud_offset[0],
                    cloud_offset[1] - local_spread * local_rng.uniform(1.45, 2.35),
                    cloud_offset[2],
                )
            leaf_position = _finish_canopy_position(
                preset_key,
                _add(cluster_center, cloud_offset),
                canopy_base,
                minimum_bounds[1],
            )
            leaves.append(
                LeafInstance(
                    position=leaf_position,
                    direction=_spread_direction(
                        _add(direction, _normalize(cloud_offset)),
                        local_rng,
                        0.70,
                    ),
                    azimuth=local_rng.uniform(0.0, 360.0),
                    length=length,
                    width=(
                        length
                        * leaf_width_ratio
                        * local_rng.uniform(0.82, 1.18)
                    ),
                    color_index=local_rng.randrange(len(profile.leaf_palette)),
                    source_segment=segment.index,
                    attachment_id=attachment_id,
                    asset_id=(
                        asset_library.choose(
                            "leaf", LEAF_STATE_BY_SEASON[config.season],
                            config.seed, attachment_id,
                        ).id
                    ),
                    state=LEAF_STATE_BY_SEASON[config.season],
                )
            )

    expected_flower_copies = (
        profile.flower_density
        * config.flower_density_multiplier
        * FLOWER_FACTOR_BY_TREE_PRESET.get(preset_key, 1.0)
    )
    flower_sites = []
    desired_flower_counts = []
    seen_tip_positions = set()
    expected_flowers_per_tip = config.flowers_per_tip * expected_flower_copies
    flower_socket_by_id = dict(
        (socket.id, socket)
        for socket in getattr(tree_model, "attachment_points", ())
        if socket.kind == "flower"
    )
    for tip_index, tip in enumerate(tree_model.tips):
        position_key = tuple(round(value, 4) for value in tip.position)
        if position_key in seen_tip_positions:
            continue
        seen_tip_positions.add(position_key)
        if preset_key != "willow_weeping" and tip.position[1] < canopy_base:
            continue
        socket = flower_socket_by_id.get("flower:{}".format(tip.path_id))
        if socket is None:
            continue
        flower_sites.append((tip_index, tip, socket))
        quota_rng = _stable_rng(config.seed, "flower-quota:{}".format(socket.id))
        desired_flower_counts.append(
            _instance_copies(expected_flowers_per_tip, quota_rng)
        )

    flower_quotas = _fair_capped_quotas(
        desired_flower_counts,
        config.max_flowers,
        rng,
    )
    for site_index, site in enumerate(flower_sites):
        tip_index, tip, socket = site
        for flower_index in range(flower_quotas[site_index]):
            attachment_id = "{}:copy{}".format(socket.id, flower_index)
            local_rng = _stable_rng(config.seed, attachment_id)
            size = profile.flower_size * config.flower_size_multiplier
            size *= local_rng.uniform(0.80, 1.20)
            local_spread = canopy_spread * _canopy_radius_scale(
                preset_key,
                tip.position,
                minimum_bounds[1],
                tree_height,
            )
            offset = _canopy_cloud_offset(
                local_rng,
                local_spread * 0.68,
                vertical_scale=canopy_vertical_scale,
                inner_fraction=0.35,
            )
            flower_position = _finish_canopy_position(
                preset_key,
                _add(tip.position, offset),
                canopy_base,
                minimum_bounds[1],
            )
            flowers.append(
                FlowerInstance(
                    position=flower_position,
                    direction=_spread_direction(
                        _add(tip.direction, _normalize(offset)),
                        local_rng,
                        0.45,
                    ),
                    azimuth=local_rng.uniform(0.0, 360.0),
                    size=size,
                    color_index=local_rng.randrange(len(profile.flower_palette)),
                    openness=profile.flower_openness * local_rng.uniform(0.92, 1.0),
                    wilt=min(
                        1.0,
                        profile.flower_wilt * local_rng.uniform(0.92, 1.08),
                    ),
                    source_tip=tip_index,
                    attachment_id=attachment_id,
                    asset_id=(
                        asset_library.choose(
                            "flower", FLOWER_STATE_BY_SEASON[config.season],
                            config.seed, attachment_id,
                        ).id
                    ),
                    state=FLOWER_STATE_BY_SEASON[config.season],
                )
            )

    return FoliageModel(config, profile, leaves, flowers, asset_library)
