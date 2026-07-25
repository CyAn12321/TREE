# -*- coding: utf-8 -*-
"""Season-driven leaf and flower distribution independent of Maya."""

from __future__ import division, print_function

import math
import random

from .assets import stable_unit
# NOTE (2026-07): OrganAssetLibrary is no longer used  -  all leaves and
# flowers are now procedurally generated.  The OBJ organ catalog
# (assets/organs/) and OrganAssetLibrary class remain in assets.py for
# reference but are not imported at runtime.
# from .assets import OrganAssetLibrary
from .math_utils import (
    add as _add,
    sub as _sub,
    mul as _mul,
    dot as _dot,
    length as _length,
    cross as _cross_vectors,
    normalize_default as _normalize,
)


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
        label="Spring",
        description="Tender leaves unfold gradually; flowers are most numerous and fully open.",
        leaf_density=0.62,
        leaf_size=0.24,
        leaf_palette=(
            (0.42, 0.76, 0.16),
            (0.28, 0.64, 0.10),
            (0.58, 0.82, 0.24),
        ),
        flower_density=0.52,
        flower_size=0.24,
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
        label="Summer",
        description="Largest and densest leaves in deep green; only a few mature flowers remain.",
        leaf_density=0.96,
        leaf_size=0.32,
        leaf_palette=(
            (0.08, 0.42, 0.08),
            (0.12, 0.52, 0.10),
            (0.18, 0.58, 0.14),
        ),
        flower_density=0.10,
        flower_size=0.22,
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
        label="Autumn",
        description="Leaf count drops and shifts to yellow, orange, red; remaining flowers shrink, droop and darken.",
        leaf_density=0.58,
        leaf_size=0.29,
        leaf_palette=(
            (0.95, 0.62, 0.05),
            (0.86, 0.28, 0.03),
            (0.68, 0.12, 0.035),
        ),
        flower_density=0.075,
        flower_size=0.19,
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
        label="Winter",
        description="Most leaves and flowers drop; only a very small number of dry leaves remain.",
        leaf_density=0.025,
        leaf_size=0.21,
        leaf_palette=(
            (0.30, 0.17, 0.06),
            (0.40, 0.24, 0.08),
            (0.23, 0.13, 0.05),
        ),
        flower_density=0.0,
        flower_size=0.15,
        flower_palette=((0.24, 0.12, 0.10),),
        flower_openness=0.0,
        flower_wilt=1.0,
        center_color=(0.22, 0.14, 0.05),
    ),
)


class WoodyFlowerSpec(object):
    """Botanical parameters for a woody flower species.

    Captures the geometric and chromatic differences between peach, cherry,
    pear and plum blossoms so the procedural flower builder can emit
    species-accurate petals without external OBJ assets.

    Botanical references (Flora of China, eflora):
    - ``petal_notch``: cherry's V-notch (Prunus serrulata "petal apex notched")
    - ``petal_claw``: basal claw narrowing (Rosaceae petals "clawed at base")
    - ``stamen_count``: peach ~30, pear 20-30, plum/cherry "numerous"
    - ``inflorescence``: peach/plum solitary, cherry/pear raceme
    """
    __slots__ = (
        "key", "label", "petal_count", "petal_shape", "petal_ratio",
        "petal_notch", "petal_claw", "palette", "center_color",
        "openness", "size_factor", "stamen_count", "pedicel_ratio",
        "inflorescence", "droop_bias", "peduncle_ratio",
        "pedicel_thickness", "flowers_per_inflorescence",
        # Phenology slots (2026-07): real-world flowering period per
        # species, used to filter the season profile's flower_density.
        # Botanical references (Flora of China / eflora):
        #   Prunus persica   (peach)   -  Mar-Apr, spring only
        #   Prunus serrulata (cherry)  -  Mar-Apr, spring only
        #   Pyrus spp.       (pear)    -  Mar-Apr, spring only
        #   Prunus mume      (plum)    -  late Jan to early Mar,
        #                                 winter-early spring (the
        #                                 iconic "winter plum")
        "flowering_seasons", "season_flower_density", "season_flower_wilt",
    )

    def __init__(
        self, key, label, petal_count, petal_shape, petal_ratio,
        petal_notch, petal_claw, palette, center_color,
        openness, size_factor, stamen_count, pedicel_ratio,
        inflorescence="solitary", droop_bias=0.0, peduncle_ratio=0.0,
        pedicel_thickness=0.06, flowers_per_inflorescence=2,
        flowering_seasons=("spring",), season_flower_density=None,
        season_flower_wilt=None,
    ):
        self.key = key
        self.label = label
        self.petal_count = int(petal_count)
        self.petal_shape = petal_shape  # 'round' | 'obovate' | 'wide_oval'
        self.petal_ratio = float(petal_ratio)  # length / width
        self.petal_notch = float(petal_notch)  # 0..1 V-notch depth at petal tip
        self.petal_claw = float(petal_claw)  # 0..1 basal claw narrowing
        self.palette = tuple(tuple(color) for color in palette)
        self.center_color = tuple(center_color)
        self.openness = float(openness)
        self.size_factor = float(size_factor)
        self.stamen_count = int(stamen_count)
        self.pedicel_ratio = float(pedicel_ratio)  # pedicel / flower_size
        self.inflorescence = inflorescence  # 'solitary' | 'corymbose' | 'racemose' | 'fascicled'
        self.droop_bias = float(droop_bias)  # -1=downward droop, 0=neutral, +1=upward
        self.peduncle_ratio = float(peduncle_ratio)  # central peduncle / flower_size (cherry/pear)
        self.pedicel_thickness = float(pedicel_thickness)  # pedicel radius / flower_size
        self.flowers_per_inflorescence = int(flowers_per_inflorescence)  # target count per cluster
        # Seasons in which this species actually produces flowers.
        # Seasons NOT listed here will have flower_density forced to 0
        # so the foliage generator emits no blossoms out of season.
        self.flowering_seasons = tuple(flowering_seasons)
        # Per-season density/wilt overrides.  When a season is listed
        # in ``flowering_seasons`` but absent from these dicts, the
        # season profile's default value is used.  Primary use case:
        # plum's winter bloom uses density 0.20 + wilt 0.10 (fresh
        # early-bloom flowers) instead of the season default 0.0 / 1.0
        # (which would produce no flowers or fully-wilted residue).
        self.season_flower_density = (
            dict(season_flower_density) if season_flower_density else {}
        )
        self.season_flower_wilt = (
            dict(season_flower_wilt) if season_flower_wilt else {}
        )


class WoodyLeafSpec(object):
    """Botanical parameters for a woody plant leaf species.

    ``blade_shape`` selects the silhouette: ``lanceolate`` (long, narrow,
    peach), ``ovate`` (egg-shaped, cherry/plum), or ``elliptic`` (rounded
    oval, pear).

    Botanical references (Flora of China, eflora):
    - ``margin_type``: peach "simple blunt serrate", cherry "double serrate with aristulate tips", pear "aristulate serrate", plum "fine sharp serrate"
    - ``apex_type``: peach "acuminate", cherry "suddenly caudate", pear "acuminate", plum "caudate"
    - ``base_type``: peach/cherry "broadly cuneate", pear "rounded", plum "broadly cuneate or rounded"
    """
    __slots__ = (
        "key", "label", "blade_shape", "length_width_ratio", "tip_acuity",
        "margin_type", "margin_depth", "apex_type", "base_type",
        "leaf_size_factor",
    )

    def __init__(
        self, key, label, blade_shape, length_width_ratio, tip_acuity,
        margin_type="entire", margin_depth=0.0, apex_type="acute", base_type="wedge",
        leaf_size_factor=1.0,
    ):
        self.key = key
        self.label = label
        self.blade_shape = blade_shape  # 'lanceolate' | 'ovate' | 'elliptic'
        self.length_width_ratio = float(length_width_ratio)
        self.tip_acuity = float(tip_acuity)  # 0..1
        self.margin_type = margin_type  # 'entire' | 'serrate' | 'double_serrate' | 'aristate'
        self.margin_depth = float(margin_depth)  # 0..1 sawtooth depth
        self.apex_type = apex_type  # 'acute' | 'acuminate' | 'caudate' | 'mucronate'
        self.base_type = base_type  # 'wedge' | 'round' | 'cordate'
        self.leaf_size_factor = float(leaf_size_factor)  # species-relative blade scale


# Botanical references (Flora of China / eflora):
#   Prunus persica   (peach)   -  flowers solitary, nearly sessile on
#                               branches; 5 wide-oval pink petals with
#                               shallow apical notch; calyx hairy;
#                               ~30 yellow-anthered stamens.
#   Prunus serrulata (cherry)  -  corymbose 3-5 flower clusters with
#                               long peduncle + equal pedicels; 5 obovate
#                               petals with deep V-notch; pedicel/calyx
#                               hairy; flowers often droop.
#   Pyrus spp.       (pear)    -  corymbose raceme of 5-10 flowers on
#                               erect peduncle; 5 round pure-white petals,
#                               no notch; 20-30 stamens with dark-purple
#                               anthers; flowers face upward.
#   Prunus salicina  (plum)    -  2-3 flowers fascicled on slender
#                               hairless pedicels (1-2cm); 5 narrow-obovate
#                               white petals with shallow apical notch;
#                               delicate appearance.
WOODY_FLOWER_SPECS = {
    "peach": WoodyFlowerSpec(
        key="peach",
        label="Peach Blossom",
        petal_count=5,
        petal_shape="wide_oval",
        petal_ratio=1.10,
        # Peach petals have a shallow apical notch ("apex shallowly
        # notched")  -  distinct from cherry's deep V-notch and
        # pear's perfectly round tip.
        petal_notch=0.06,
        # Peach petals "short clawed at base".
        petal_claw=0.18,
        palette=(
            (1.00, 0.55, 0.68),
            (1.00, 0.71, 0.78),
            (0.98, 0.85, 0.88),
        ),
        center_color=(0.95, 0.45, 0.10),
        openness=0.95,
        size_factor=1.00,
        stamen_count=12,
        # "nearly sessile"  -  pedicel nearly absent.
        pedicel_ratio=0.05,
        inflorescence="solitary",
        # Flowers sit flush on the branch; no droop.
        droop_bias=0.0,
        # No central peduncle (solitary).
        peduncle_ratio=0.0,
        # Thickened receptacle base compensates for the missing pedicel.
        pedicel_thickness=0.08,
        # Peach flowers are solitary; 1-2 per tip.
        flowers_per_inflorescence=2,
    ),
    "cherry": WoodyFlowerSpec(
        key="cherry",
        label="Cherry Blossom",
        petal_count=5,
        # TEMP (2026-07): switched from "obovate" to "wide_oval" to
        # isolate the basal-transition bug.  obovate's peak=0.65 makes
        # the natural width rise too slowly near t=0, which collides
        # with the base_floor clamp and produces a "platform -> steep
        # flare" near t=0.27.  wide_oval (peak=0.5) rises faster early
        # on, so the base transition is smooth.  Will switch back to
        # obovate after fixing its early-rise curve.
        petal_shape="wide_oval",
        # Increased ratio (1.20 -> 1.35) to make cherry petals narrower
        # and more elongated  -  visually "flatter" (扁) than peach's
        # 1.10 ratio.  Combined with size_factor reduction below, the
        # overall blossom reads as smaller and more delicate.
        petal_ratio=1.35,
        # The signature V-notch at the petal tip distinguishes cherry
        # from all other Rosaceae blossoms.  Depth is 0.24 (24% of
        # petal length) to survive Catmull-Clark subdivision (divisions=2)
        # which would otherwise average a shallower notch into a flat tip.
        petal_notch=0.24,
        petal_claw=0.22,
        palette=(
            (1.00, 0.78, 0.84),
            (1.00, 0.88, 0.92),
            (0.98, 0.95, 0.97),
        ),
        center_color=(0.95, 0.78, 0.10),
        openness=0.92,
        # Reduced (1.05 -> 0.90) to make the overall blossom smaller
        # and more delicate  -  cherry flowers are botanically smaller
        # than peach (Prunus serrulata vs Prunus persica).
        size_factor=0.90,
        stamen_count=14,
        # "pedicel 1.5-3cm long"  -  long pedicel, the cherry's signature.
        pedicel_ratio=0.55,
        inflorescence="corymbose",
        # Cherry blossoms characteristically droop ("flowers often
        # nodding"), giving the corymb a graceful pendulous look.
        droop_bias=-0.25,
        # Central peduncle extending from the branch before the
        # individual pedicels fan out (corymb structure).
        peduncle_ratio=0.35,
        # Slender pedicel.
        pedicel_thickness=0.05,
        # Cherry corymbs have 3-5 flowers per inflorescence.
        flowers_per_inflorescence=5,
    ),
    "pear": WoodyFlowerSpec(
        key="pear",
        label="Pear Blossom",
        petal_count=5,
        petal_shape="round",
        petal_ratio=1.00,
        # Pear petals are perfectly round with no notch at all
        # ("petals white, suborbicular, apex obtuse").
        petal_notch=0.0,
        # Pear petals "clawed at base"  -  pronounced claw.
        petal_claw=0.25,
        palette=(
            (1.00, 1.00, 1.00),
            (0.96, 0.97, 0.98),
            (0.92, 0.94, 0.96),
        ),
        # Dark-purple to nearly black anthers  -  the field mark for pear.
        center_color=(0.18, 0.10, 0.22),
        openness=0.82,
        size_factor=0.95,
        # Pear has 20-30 stamens ("stamens 20-30").
        stamen_count=16,
        # Pear pedicels are moderately long.
        pedicel_ratio=0.35,
        inflorescence="corymbose",
        # Pear inflorescence is erect; flowers face outward or slightly
        # upward, never drooping ("inflorescence erect, flowers
        # horizontally spreading").
        droop_bias=+0.15,
        # Central peduncle before the individual pedicels fan out.
        peduncle_ratio=0.30,
        # Medium pedicel thickness.
        pedicel_thickness=0.06,
        # Pear has the largest inflorescence: 5-10 flowers per cluster.
        flowers_per_inflorescence=8,
    ),
    "plum": WoodyFlowerSpec(
        key="plum",
        label="Plum Blossom",
        petal_count=5,
        petal_shape="obovate",
        petal_ratio=1.05,
        # Plum petals have a subtle apical notch ("apex shallowly
        # retuse or obtuse")  -  less deep than cherry, but present.
        petal_notch=0.04,
        # Plum petals "broadly obovate, clawed at base".
        petal_claw=0.20,
        palette=(
            (0.95, 0.92, 0.95),
            (1.00, 0.72, 0.78),
            (0.88, 0.32, 0.38),
        ),
        center_color=(0.95, 0.72, 0.08),
        openness=0.78,
        # Plum blossoms are smaller and more delicate than the other
        # three Rosaceae species ("flowers 1.5-2cm across").
        size_factor=0.85,
        stamen_count=13,
        # Plum pedicels are 1-2 cm, slender and hairless ("pedicel
        # 1-2cm, glabrous")  -  the species has visible pedicels,
        # unlike peach.  Previously this was mis-set to 0.04 (nearly
        # sessile), which made plum blossoms indistinguishable from
        # peach at a glance.
        pedicel_ratio=0.25,
        # Plum flowers grow in fascicles of 2-3 ("flowers 2-3,
        # fascicled"), not solitary like peach.
        inflorescence="fascicled",
        # Neutral orientation  -  plum flowers neither droop nor face
        # strongly upward.
        droop_bias=0.0,
        # No central peduncle (fascicled = clustered directly from one
        # point without a common stalk).
        peduncle_ratio=0.0,
        # Slender, hairless pedicel  -  plum's "delicate" look.
        pedicel_thickness=0.04,
        # Plum flowers in tight fascicles of 2-3.
        flowers_per_inflorescence=3,
        # Phenology (Flora of China): Prunus mume is the iconic
        # "winter plum"  -  it blooms from late January through early
        # March, spaning winter and early spring.  Winter blooms are
        # the early flush (稀疏, fresh, just-opening buds braving the
        # cold); spring blooms are the peak flush (繁密, fully open)
        # before petals drop.  Other three Rosaceae species only
        # flower in spring (Mar-Apr), so they keep the default
        # ``flowering_seasons=("spring",)`` and need no override.
        flowering_seasons=("winter", "spring"),
        # Winter: ~38% of spring peak  -  sparse but visible early
        # blooms.  Spring keeps the season profile default (0.52).
        season_flower_density={"winter": 0.20},
        # Winter flowers are FRESH (just opening in the cold), so
        # override the season's default wilt=1.0 (which assumes
        # dead residue).  Spring keeps the season default (0.02).
        season_flower_wilt={"winter": 0.10},
    ),
}

# Leaf silhouettes follow the classic botanical leaf-shape taxonomy
# (Flora of China / eflora descriptions).
#   lanceolate: long and narrow, tip acuminate (peach  -  "leaves lanceolate, apex acuminate")
#   ovate:      egg-shaped, widest below middle (cherry/plum  -  "leaves ovate")
#   elliptic:   rounded oval, widest at middle (pear  -  "leaves elliptic")
WOODY_LEAF_SPECS = {
    "peach": WoodyLeafSpec(
        "peach", "Peach Leaf", "lanceolate", 3.5, 0.85,
        margin_type="serrate", margin_depth=0.08,
        apex_type="acuminate", base_type="wedge",
        # Peach leaves are the largest among the four (8-15cm).
        leaf_size_factor=1.05,
    ),
    "cherry": WoodyLeafSpec(
        "cherry", "Cherry Leaf", "ovate", 2.2, 0.65,
        margin_type="double_serrate", margin_depth=0.12,
        apex_type="caudate", base_type="wedge",
        # Cherry leaves are medium-sized (5-12cm).
        leaf_size_factor=0.95,
    ),
    "pear": WoodyLeafSpec(
        "pear", "Pear Leaf", "elliptic", 1.8, 0.55,
        margin_type="aristate", margin_depth=0.10,
        apex_type="acute", base_type="round",
        # Pear leaves are medium-sized, wide and rounded (5-10cm).
        leaf_size_factor=0.90,
    ),
    "plum": WoodyLeafSpec(
        "plum", "Plum Leaf", "ovate", 2.0, 0.75,
        margin_type="serrate", margin_depth=0.07,
        apex_type="caudate", base_type="wedge",
        # Plum leaves are the smallest of the four (4-8cm).
        leaf_size_factor=0.78,
    ),
}


def list_seasons():
    """Return all available season profiles (spring, summer, autumn, winter).

    Returns:
        tuple[SeasonProfile]: Immutable tuple of all registered seasons.
    """
    return SEASONS


def get_season(key):
    """Return the season profile with the given key.

    Parameters:
        key (str): Season identifier ("spring", "summer", "autumn",
            "winter").
    """
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
        woody_species=None,
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
        # When set to a key in WOODY_FLOWER_SPECS (e.g. "cherry"), the
        # foliage generator emits species-accurate blossoms and leaves
        # instead of the generic round-petal flower.  None preserves the
        # legacy procedural flower used by existing tests and scenes.
        self.woody_species = woody_species if woody_species is not None else None
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
        if self.woody_species is not None and self.woody_species not in WOODY_FLOWER_SPECS:
            raise ValueError(
                "Unknown woody_species '{}'; expected one of {}".format(
                    self.woody_species, sorted(WOODY_FLOWER_SPECS.keys())
                )
            )


class LeafInstance(object):
    """A single leaf instance.

    ``position`` is the petiole base  -  the contact point where the
    petiole meets the branch bark.  The leaf blade geometry starts at
    ``position + forward * petiole_length`` so the petiole acts as the
    connector between branch and blade.
    """

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
        "petiole_length",
        "species",
        "droop_factor",
        "blade_curve",
        "curl_variation",
        "tip_fold",
        "has_damage",
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
        petiole_length=0.0,
        species=None,
        droop_factor=0.0,
        blade_curve=0.0,
        curl_variation=1.0,
        tip_fold=0.0,
        has_damage=False,
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
        self.petiole_length = float(petiole_length)
        self.species = species
        self.droop_factor = float(droop_factor)
        self.blade_curve = float(blade_curve)
        self.curl_variation = float(curl_variation)
        self.tip_fold = float(tip_fold)
        self.has_damage = bool(has_damage)


class FlowerInstance(object):
    """A single flower instance.

    ``position`` is the pedicel base  -  the contact point where the
    pedicel meets the branch bark.  The flower head geometry starts at
    ``position + forward * peduncle_length`` so the pedicel acts as the
    connector between branch and flower.
    """

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
        "peduncle_length",
        "species",
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
        peduncle_length=0.0,
        species=None,
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
        self.peduncle_length = float(peduncle_length)
        self.species = species


class FoliageModel(object):
    def __init__(self, config, profile, leaves, flowers, asset_library=None):
        self.config = config
        self.profile = profile
        self.leaves = leaves
        self.flowers = flowers
        self.asset_library = asset_library


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


def _surface_offset(socket, segment):
    """Offset from the branch center line to its surface at the socket.

    The socket sits on the segment center line at ``amount``.  The branch
    radius there is the linear interpolation between ``start_radius`` and
    ``end_radius``.  Pushing outward along ``socket.normal`` moves the
    organ onto the branch surface (the bark), so leaves/flowers grow from
    the bark rather than floating inside the wood.
    """
    start_radius = float(getattr(segment, "start_radius", 0.0))
    end_radius = float(getattr(segment, "end_radius", 0.0))
    amount = float(getattr(socket, "amount", 0.5))
    surface_radius = start_radius + (end_radius - start_radius) * amount
    normal = _normalize(getattr(socket, "normal", (0.0, 1.0, 0.0)))
    return _mul(normal, surface_radius)


def _project_to_branch_surface(socket, segment):
    """Analytically project the socket contact point onto the branch frustum.

    This is the collision-detection step: it computes the exact point on
    the tapered cylinder (frustum) surface of ``segment`` that corresponds
    to ``socket``.  The result is guaranteed to lie ON the bark surface  - 
    neither floating outside nor clipping inside the wood.

    The branch segment is modelled as a frustum from ``segment.start``
    (radius ``start_radius``) to ``segment.end`` (radius ``end_radius``).
    For the socket at parameter ``amount`` along the axis, the surface
    radius is linearly interpolated, and the true radial direction is
    derived from the geometry (not from the precomputed socket normal,
    which may have accumulated rounding error from the golden-angle
    rotation).  A push-out safety check ensures the point is never inside
    the frustum even if the radial direction is degenerate.
    """
    amount = float(getattr(socket, "amount", 0.5))
    start_radius = float(getattr(segment, "start_radius", 0.0))
    end_radius = float(getattr(segment, "end_radius", 0.0))
    radius = start_radius + (end_radius - start_radius) * amount

    # Axis point at this amount along the segment.
    axis_point = _lerp(segment.start, segment.end, amount)

    # True radial direction: from the axis point toward the socket position,
    # projected onto the plane perpendicular to the branch heading.
    heading = _normalize(getattr(segment, "heading", _sub(segment.end, segment.start)))
    to_socket = _sub(socket.position, axis_point)
    along = _dot(to_socket, heading)
    radial = _sub(to_socket, _mul(heading, along))
    radial_len = _length(radial)

    if radial_len < 1.0e-9:
        # Socket sits exactly on the axis (degenerate case); fall back to
        # the socket normal, which is always a valid radial direction.
        radial = _normalize(getattr(socket, "normal", (0.0, 1.0, 0.0)))
    else:
        radial = _mul(radial, 1.0 / radial_len)

    # Surface point = axis_point + radius * radial_direction.
    surface_point = _add(axis_point, _mul(radial, radius))

    # Push-out safety: if the surface point is somehow still inside the
    # frustum (numerical edge case), push it outward along the socket
    # normal until it is on or outside the surface.
    surface_to_axis = _sub(surface_point, axis_point)
    surface_dist = _length(surface_to_axis)
    if surface_dist < radius - 1.0e-6:
        fallback = _normalize(getattr(socket, "normal", (0.0, 1.0, 0.0)))
        surface_point = _add(axis_point, _mul(fallback, radius))

    return surface_point


def _lerp(a, b, amount):
    return tuple(
        a[index] + (b[index] - a[index]) * amount for index in range(3)
    )


# --- Foliage preset tables (2026-07): only "broadleaf_round" is active
# through the UI now that the four Rosaceae species (peach/cherry/pear/
# plum) are the sole focus.  The entries for conifer/willow/poplar are
# preserved for test coverage and future re-introduction of non-flowering
# tree silhouettes.
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


# Leaf-bearing branch layer span (how many depth levels from the
# maximum participate in foliage).  A span of 2 means the maximum
# branch depth and the two preceding depths are eligible.
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
    """Create reproducible leaf and flower instance data from a tree model.

    Parameters:
        tree_model (TreeModel): Tree to dress with foliage.
        config (FoliageConfig|None): Foliage configuration.  Defaults to
            ``FoliageConfig(seed=tree_model.config.seed + 101)``.
    """
    config = config or FoliageConfig(seed=tree_model.config.seed + 101)
    profile = get_season(config.season)
    rng = random.Random(config.seed)
    # NOTE (2026-07): OrganAssetLibrary loading removed.  All leaves and
    # flowers are now procedurally generated (asset_id=None).  The OBJ
    # organ catalog (assets/organs/) is preserved for reference but no
    # longer imported at runtime.
    # When a woody species is selected, override the season profile's
    # flower palette, center color and openness with the species-accurate
    # botanical values so peach/cherry/pear/plum blossoms are visually
    # distinct from the generic round-petal flower.  We build a shallow
    # copy of the season profile first so the global SEASONS table is
    # never mutated across runs.
    #
    # Phenology filter (2026-07): real-world flowering period is
    # species-specific.  Peach/cherry/pear bloom only in spring
    # (Mar-Apr); plum (Prunus mume) blooms in late winter through
    # early spring.  When the selected season is OUTSIDE the species'
    # ``flowering_seasons``, flower_density is forced to 0 so no
    # blossoms are emitted  -  this fixes the unrealistic "autumn
    # flowers" the user reported.  When the season IS a flowering
    # season, per-season overrides (mainly plum's winter early-bloom
    # density 0.20 + fresh wilt 0.10) take precedence over the season
    # profile default; absent overrides fall back to the profile.
    woody_flower_spec = None
    woody_leaf_spec = None
    if config.woody_species is not None:
        woody_flower_spec = WOODY_FLOWER_SPECS[config.woody_species]
        woody_leaf_spec = WOODY_LEAF_SPECS[config.woody_species]
        if profile.key in woody_flower_spec.flowering_seasons:
            flower_density = woody_flower_spec.season_flower_density.get(
                profile.key, profile.flower_density
            )
            flower_wilt = woody_flower_spec.season_flower_wilt.get(
                profile.key, profile.flower_wilt
            )
            flower_openness = woody_flower_spec.openness
        else:
            # Out of season for this species  -  suppress all flowers.
            # Wilt is set to 1.0 so any residual petals (none, since
            # density=0) would render as fully wilted; openness=0.0
            # keeps the profile internally consistent.
            flower_density = 0.0
            flower_wilt = 1.0
            flower_openness = 0.0
        profile = SeasonProfile(
            key=profile.key,
            label=profile.label,
            description=profile.description,
            leaf_density=profile.leaf_density,
            leaf_size=profile.leaf_size,
            leaf_palette=profile.leaf_palette,
            flower_density=flower_density,
            flower_size=profile.flower_size,
            flower_palette=woody_flower_spec.palette,
            flower_openness=flower_openness,
            flower_wilt=flower_wilt,
            center_color=woody_flower_spec.center_color,
        )
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
    segments_by_index = {segment.index: segment for segment in tree_model.segments}
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
            length = profile.leaf_size * config.leaf_size_multiplier
            length *= local_rng.uniform(0.78, 1.22)
            # Species-specific leaf size scaling (2026-07):
            # peach leaves are largest, plum smallest.
            if woody_leaf_spec is not None:
                length *= woody_leaf_spec.leaf_size_factor
            # The petiole base (contact point) must lie EXACTLY on the
            # branch bark surface via analytical frustum projection.
            leaf_position = _project_to_branch_surface(socket, segment)
            socket_tangent = _normalize(getattr(socket, "tangent", direction))
            socket_exposure = float(getattr(socket, "exposure", 0.8))
            socket_amount = float(getattr(socket, "amount", 0.5))
            # Leaves near the branch base (low amount) are slightly larger.
            length *= 0.85 + 0.30 * (1.0 - socket_amount)
            petiole_length = length * local_rng.uniform(0.15, 0.30)
            azimuth = local_rng.uniform(0.0, 360.0)
            if woody_leaf_spec is not None:
                # Species-accurate leaf silhouette: width derived from the
                # botanical length/width ratio so peach leaves are long and
                # narrow (lanceolate) while pear leaves are round (elliptic).
                width = length / woody_leaf_spec.length_width_ratio * local_rng.uniform(0.82, 1.18)
            else:
                width = length * leaf_width_ratio * local_rng.uniform(0.82, 1.18)
            # Grow along the branch heading (tangent) with a small outward
            # radial tilt.  Visual penetration is handled by the Maya
            # shader (depthBias + doubleSided), not by collision detection.
            branch_heading = _normalize(getattr(segment, "heading", socket_tangent))
            socket_normal = _normalize(getattr(socket, "normal", (0.0, 1.0, 0.0)))
            # Gravity + phototropism: leaves in the upper canopy point
            # more upward (light-seeking), while lower leaves droop more
            # (shade avoidance + gravity).  The droop_factor is passed
            # to the mesh builder for progressive blade bending.
            height_ratio = (
                (leaf_position[1] - canopy_base) / max(tree_height - canopy_base, 1.0e-6)
            )
            height_ratio = max(0.0, min(1.0, height_ratio))
            droop_factor = 0.65 - 0.50 * height_ratio  # 0.65 at bottom, 0.15 at top
            droop_factor *= local_rng.uniform(0.80, 1.20)
            # Vertical bias: upper leaves get an upward component, lower
            # leaves get a downward (gravity) component.
            vertical_bias = 0.25 * (height_ratio - 0.4)
            base_direction = _normalize(
                _add(
                    _add(_mul(branch_heading, 0.65), _mul(socket_normal, 0.28)),
                    (0.0, vertical_bias, 0.0),
                )
            )
            raw_direction = _spread_direction(
                base_direction, local_rng, 0.55 + 0.30 * socket_exposure
            )
            # Per-leaf morphological variation for naturalism:
            # blade_curve: asymmetric lateral bend along midrib (-1..+1)
            # curl_variation: margin curl multiplier (0.5..1.8)
            # tip_fold: tip fold angle in radians (0 or 0.35..0.70)
            # has_damage: ~8% of leaves have insect-damage notches
            blade_curve = local_rng.uniform(-1.0, 1.0) * 0.6
            curl_variation = local_rng.uniform(0.5, 1.8)
            tip_fold = (
                local_rng.uniform(0.35, 0.70)
                if local_rng.random() < 0.15
                else 0.0
            )
            has_damage = local_rng.random() < 0.08
            leaves.append(
                LeafInstance(
                    position=leaf_position,
                    direction=raw_direction,
                    azimuth=azimuth,
                    length=length,
                    width=width,
                    color_index=local_rng.randrange(len(profile.leaf_palette)),
                    source_segment=segment.index,
                    attachment_id=attachment_id,
                    asset_id=(
                        # All leaves are now procedurally generated;
                        # asset_id is always None (2026-07).
                        None
                    ),
                    state=LEAF_STATE_BY_SEASON[config.season],
                    petiole_length=petiole_length,
                    species=config.woody_species,
                    droop_factor=droop_factor,
                    blade_curve=blade_curve,
                    curl_variation=curl_variation,
                    tip_fold=tip_fold,
                    has_damage=has_damage,
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
    expected_flowers_per_tip = (
        woody_flower_spec.flowers_per_inflorescence * expected_flower_copies
        if woody_flower_spec is not None
        else config.flowers_per_tip * expected_flower_copies
    )
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
        # Skip tips on or near the trunk (low depth) so flowers only grow
        # on actual branches, not on the main trunk.
        if tip.depth < minimum_leaf_depth:
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
        flower_segment = segments_by_index.get(socket.segment_index)
        for flower_index in range(flower_quotas[site_index]):
            attachment_id = "{}:copy{}".format(socket.id, flower_index)
            local_rng = _stable_rng(config.seed, attachment_id)
            size = profile.flower_size * config.flower_size_multiplier
            size *= local_rng.uniform(0.80, 1.20)
            if woody_flower_spec is not None:
                # Species-specific size scaling: plum blossoms are smaller,
                # cherry blossoms slightly larger than the generic flower.
                size *= woody_flower_spec.size_factor
            # The pedicel base (contact point) must lie EXACTLY on the
            # branch bark surface via analytical frustum projection.
            if flower_segment is not None:
                flower_position = _project_to_branch_surface(socket, flower_segment)
            else:
                flower_position = tip.position
            socket_tangent = _normalize(getattr(socket, "tangent", tip.direction))
            socket_exposure = float(getattr(socket, "exposure", 1.0))
            # Flowers on outer-facing tips open slightly more; inner ones droop.
            openness_boost = 0.88 + 0.12 * socket_exposure
            peduncle_length = size * local_rng.uniform(0.30, 0.60)
            if woody_flower_spec is not None:
                # Species-specific pedicel length from the botanical spec
                # (cherry 1.5-3cm, plum 1-2cm, peach sessile, pear moderate).
                peduncle_length = size * woody_flower_spec.pedicel_ratio * local_rng.uniform(0.80, 1.20)
            azimuth = local_rng.uniform(0.0, 360.0)
            # Grow along the branch tip direction with a small outward
            # tilt.  Visual penetration is handled by the Maya shader.
            tip_heading = _normalize(getattr(tip, "direction", socket_tangent))
            socket_normal = _normalize(getattr(socket, "normal", (0.0, 1.0, 0.0)))
            # When multiple flowers share the same tip, distribute them
            # according to the species' inflorescence type:
            # - solitary: no offset (only first flower, extras skipped)
            # - fascicled: 2-3 flowers cluster tightly with short pedicels
            # - corymbose: fan out on a hemisphere from a central peduncle
            # - racemose: spiral along the tip heading
            inflorescence = (
                woody_flower_spec.inflorescence
                if woody_flower_spec is not None
                else "racemose"
            )
            # Two-level inflorescence: for corymbose species (cherry, pear),
            # first extend a central peduncle from the branch surface, then
            # fan out individual pedicels from the peduncle tip.  This
            # creates the characteristic "umbel" silhouette.
            peduncle_tip = flower_position
            if inflorescence == "corymbose" and woody_flower_spec is not None:
                peduncle_ratio = woody_flower_spec.peduncle_ratio
                if peduncle_ratio > 0.0:
                    peduncle_len = size * peduncle_ratio * local_rng.uniform(0.85, 1.15)
                    peduncle_tip = _add(
                        flower_position,
                        _mul(tip_heading, peduncle_len),
                    )
                # The first flower (index 0) sits at the peduncle tip;
                # subsequent flowers fan out from there.
                if flower_index == 0:
                    flower_position = peduncle_tip
            if flower_index > 0:
                if inflorescence == "corymbose":
                    # Fan out on a hemisphere from the peduncle tip: each
                    # flower gets a radial offset perpendicular to the tip
                    # heading.
                    golden_angle = 2.399963
                    fan_angle = flower_index * golden_angle
                    fan_radius = size * 0.55 * (0.5 + 0.5 * flower_index ** 0.5)
                    # Build a perpendicular frame around tip_heading.
                    perp_helper = (
                        (1.0, 0.0, 0.0)
                        if abs(tip_heading[1]) < 0.9
                        else (0.0, 0.0, 1.0)
                    )
                    perp_a = _normalize(_cross_vectors(tip_heading, perp_helper))
                    perp_b = _normalize(_cross_vectors(tip_heading, perp_a))
                    offset = _add(
                        _mul(perp_a, math.cos(fan_angle) * fan_radius),
                        _mul(perp_b, math.sin(fan_angle) * fan_radius),
                    )
                    # Slight forward offset so flowers don't clip the branch.
                    offset = _add(offset, _mul(tip_heading, size * 0.2 * flower_index))
                    flower_position = _add(peduncle_tip, offset)
                elif inflorescence == "fascicled":
                    # Fascicled cluster (plum): 2-3 flowers emerge from
                    # nearly the same point with short, slightly diverging
                    # pedicels  -  no central peduncle, no wide fan.
                    golden_angle = 2.399963
                    cluster_angle = flower_index * golden_angle
                    # Tight radius keeps the cluster compact.
                    cluster_radius = size * 0.20 * (0.5 + 0.5 * flower_index ** 0.5)
                    perp_helper = (
                        (1.0, 0.0, 0.0)
                        if abs(tip_heading[1]) < 0.9
                        else (0.0, 0.0, 1.0)
                    )
                    perp_a = _normalize(_cross_vectors(tip_heading, perp_helper))
                    perp_b = _normalize(_cross_vectors(tip_heading, perp_a))
                    offset = _add(
                        _mul(perp_a, math.cos(cluster_angle) * cluster_radius),
                        _mul(perp_b, math.sin(cluster_angle) * cluster_radius),
                    )
                    # Very slight forward offset for each successive flower.
                    offset = _add(offset, _mul(tip_heading, size * 0.08 * flower_index))
                    flower_position = _add(flower_position, offset)
                else:
                    # Racemose / default: spiral along the tip heading.
                    spacing = size * 0.6 * flower_index
                    flower_position = _add(
                        flower_position, _mul(tip_heading, spacing)
                    )
            base_direction = _normalize(
                _add(_mul(tip_heading, 0.70), _mul(socket_normal, 0.30))
            )
            # Species-specific flower orientation (2026-07):
            # droop_bias < 0 -> flowers nod downward (cherry)
            # droop_bias = 0 -> neutral (peach, plum)
            # droop_bias > 0 -> flowers face upward (pear)
            droop_bias = woody_flower_spec.droop_bias if woody_flower_spec is not None else 0.0
            if droop_bias != 0.0:
                # Multiply world-up by droop_bias: negative bias adds a
                # downward component, positive bias adds an upward one.
                world_up = (0.0, 1.0, 0.0)
                base_direction = _normalize(
                    _add(base_direction, _mul(world_up, droop_bias))
                )
            raw_direction = _spread_direction(base_direction, local_rng, 0.40)
            # Openness gradient: wider variation range (0.55-1.0) plus
            # a basipetal gradient (later flowers on the same tip are
            # less open, simulating sequential blooming).  ~10% of
            # flowers are buds (openness < 0.3).
            is_bud = local_rng.random() < 0.10
            if is_bud:
                flower_openness = local_rng.uniform(0.12, 0.28)
            else:
                # Basipetal gradient: first flower most open, later ones less.
                index_factor = 1.0 - 0.18 * min(flower_index, 3)
                flower_openness = min(
                    1.0,
                    profile.flower_openness
                    * local_rng.uniform(0.55, 1.0)
                    * openness_boost
                    * index_factor,
                )
            flowers.append(
                FlowerInstance(
                    position=flower_position,
                    direction=raw_direction,
                    azimuth=azimuth,
                    size=size,
                    color_index=local_rng.randrange(len(profile.flower_palette)),
                    openness=flower_openness,
                    wilt=min(
                        1.0,
                        profile.flower_wilt * local_rng.uniform(0.92, 1.08),
                    ),
                    source_tip=tip_index,
                    attachment_id=attachment_id,
                    asset_id=(
                        # All flowers are now procedurally generated;
                        # asset_id is always None (2026-07).
                        None
                    ),
                    state=FLOWER_STATE_BY_SEASON[config.season],
                    peduncle_length=peduncle_length,
                    species=config.woody_species,
                )
            )

    return FoliageModel(config, profile, leaves, flowers, None)
