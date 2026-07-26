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
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            key: Input value used by this function.
            label: Input value used by this function.
            description: Input value used by this function.
            leaf_density: Input value used by this function.
            leaf_size: Input value used by this function.
            leaf_palette: Input value used by this function.
            flower_density: Input value used by this function.
            flower_size: Input value used by this function.
            flower_palette: Input value used by this function.
            flower_openness: Input value used by this function.
            flower_wilt: Input value used by this function.
            center_color: Input value used by this function.
        """
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
        "sepal_color", "pedicel_color",
    )

    def __init__(
        self, key, label, petal_count, petal_shape, petal_ratio,
        petal_notch, petal_claw, palette, center_color,
        openness, size_factor, stamen_count, pedicel_ratio,
        inflorescence="solitary", droop_bias=0.0, peduncle_ratio=0.0,
        pedicel_thickness=0.06, flowers_per_inflorescence=2,
        flowering_seasons=("spring",), season_flower_density=None,
        season_flower_wilt=None,
        sepal_color=(0.18, 0.42, 0.14), pedicel_color=(0.18, 0.42, 0.14),
    ):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            key: Input value used by this function.
            label: Input value used by this function.
            petal_count: Input value used by this function.
            petal_shape: Input value used by this function.
            petal_ratio: Input value used by this function.
            petal_notch: Input value used by this function.
            petal_claw: Input value used by this function.
            palette: Input value used by this function.
            center_color: Input value used by this function.
            openness: Input value used by this function.
            size_factor: Input value used by this function.
            stamen_count: Input value used by this function.
            pedicel_ratio: Input value used by this function.
            inflorescence: Input value used by this function.
            droop_bias: Input value used by this function.
            peduncle_ratio: Input value used by this function.
            pedicel_thickness: Input value used by this function.
            flowers_per_inflorescence: Input value used by this function.
            flowering_seasons: Input value used by this function.
            season_flower_density: Input value used by this function.
            season_flower_wilt: Input value used by this function.
            sepal_color: Input value used by this function.
            pedicel_color: Input value used by this function.
        """
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
        self.sepal_color = tuple(sepal_color)
        self.pedicel_color = tuple(pedicel_color)
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
        "leaf_size_factor", "leaf_color_shift",
    )

    def __init__(
        self, key, label, blade_shape, length_width_ratio, tip_acuity,
        margin_type="entire", margin_depth=0.0, apex_type="acute", base_type="wedge",
        leaf_size_factor=1.0, leaf_color_shift=(0.0, 0.0, 0.0),
    ):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            key: Input value used by this function.
            label: Input value used by this function.
            blade_shape: Input value used by this function.
            length_width_ratio: Input value used by this function.
            tip_acuity: Input value used by this function.
            margin_type: Input value used by this function.
            margin_depth: Input value used by this function.
            apex_type: Input value used by this function.
            base_type: Input value used by this function.
            leaf_size_factor: Input value used by this function.
            leaf_color_shift: Input value used by this function.
        """
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
        # Per-species leaf colour shift (RGB delta) added to the seasonal
        # palette colour.  Peach leaves are dark glossy-green (shift
        # toward darker), cherry leaves are lighter yellow-green, pear
        # leaves are rich mid-green, plum leaves are cool blue-green.
        self.leaf_color_shift = tuple(leaf_color_shift)


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
        sepal_color=(0.35, 0.18, 0.12), pedicel_color=(0.15, 0.40, 0.10),
        # Peach flowers are solitary; 1-2 per tip.
        flowers_per_inflorescence=2,
    ),
    "cherry": WoodyFlowerSpec(
        key="cherry",
        label="Cherry Blossom",
        petal_count=5,
        petal_shape="obovate",
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
        sepal_color=(0.22, 0.48, 0.18), pedicel_color=(0.28, 0.15, 0.12),
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
        sepal_color=(0.16, 0.38, 0.12), pedicel_color=(0.18, 0.42, 0.14),
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
        sepal_color=(0.20, 0.45, 0.16), pedicel_color=(0.18, 0.42, 0.14),
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
    # --- Non-flowering tree species (2026-07) ---
    # Willow has no showy petals.  ``flowering_seasons`` is set to an
    # empty tuple so that no flowers are emitted in any season; the
    # foliage generator picks up only the WOODY_LEAF_SPECS entry.
    "willow": WoodyFlowerSpec(
        key="willow",
        label="Weeping Willow",
        petal_count=5,
        petal_shape="round",
        petal_ratio=1.0,
        petal_notch=0.0,
        petal_claw=0.0,
        palette=((0.85, 0.82, 0.55),),
        center_color=(0.7, 0.65, 0.4),
        openness=0.0,
        size_factor=0.0,
        stamen_count=0,
        pedicel_ratio=0.0,
        flowering_seasons=(),  # no showy flowers; catkins deferred to Phase 3
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
        # Leaf-to-flower ratio matches reality: peach leaves 8-15cm vs
        # flowers 2.5-3.5cm (median 11.5 / 3.0 = 3.83x).  Since flowers
        # are visually enlarged in code (flower_size_factor=1.00), leaves
        # are scaled by the same ratio so the blossom-vs-leaf proportion
        # reads as botanical rather than toy-like.
        # leaf_factor = flower_factor * (real_leaf / real_flower)
        #             = 1.00 * 3.83 = 3.83
        # Shrink history: 75% (2.87) -> 65% (2.44) of real-ratio.
        leaf_size_factor=2.44,
        leaf_color_shift=(-0.04, 0.02, -0.04),
    ),
    "cherry": WoodyLeafSpec(
        "cherry", "Cherry Leaf", "ovate", 2.2, 0.65,
        margin_type="double_serrate", margin_depth=0.12,
        apex_type="caudate", base_type="wedge",
        # Cherry leaves 4-12cm vs flowers 2-3.5cm
        # (median 8 / 2.75 = 2.91x).  leaf_factor = 0.90 * 2.91 = 2.62.
        # Shrink history: 75% (1.97) -> 65% (1.67) of real-ratio.
        leaf_size_factor=1.67,
        leaf_color_shift=(-0.02, 0.04, -0.01),
    ),
    "pear": WoodyLeafSpec(
        "pear", "Pear Leaf", "elliptic", 1.8, 0.55,
        margin_type="aristate", margin_depth=0.10,
        apex_type="acute", base_type="round",
        # Pear leaves 7-12cm vs flowers 2.5-3.5cm
        # (median 9.5 / 3.0 = 3.17x).  leaf_factor = 0.95 * 3.17 = 3.01.
        # Shrink history: 75% (2.26) -> 65% (1.92) of real-ratio.
        leaf_size_factor=1.92,
        leaf_color_shift=(0.00, 0.00, 0.00),
    ),
    "plum": WoodyLeafSpec(
        "plum", "Plum Leaf", "ovate", 2.0, 0.75,
        margin_type="serrate", margin_depth=0.07,
        apex_type="caudate", base_type="wedge",
        # Plum leaves 4-8cm vs flowers 2-2.5cm
        # (median 6 / 2.25 = 2.67x).  leaf_factor = 0.85 * 2.67 = 2.27.
        # Shrink history: 75% (1.70) -> 65% (1.45) of real-ratio.
        leaf_size_factor=1.45,
        leaf_color_shift=(-0.02, 0.00, 0.03),
    ),
    # --- Non-flowering tree species (2026-07) ---
    # Leaf-only species; their WOODY_FLOWER_SPECS entries use
    # flowering_seasons=() so no blossoms are emitted.
    "willow": WoodyLeafSpec(
        "willow", "Willow Leaf", "lanceolate", 10.0, 0.85,
        margin_type="serrate", margin_depth=0.03,
        apex_type="acuminate", base_type="wedge",
        # Willow leaves: 7-16cm x 0.5-1.5cm (median 11.5cm).
        # Similar size to peach → same leaf_size_factor.
        leaf_size_factor=2.44,
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
        # Twig (fine shoot) generation parameters (2026-07):
        # Visible curved twigs grow from each GrowthTip and carry leaves
        # at their ends, replacing the prior "leaves glued to main
        # branch bark" attachment.  This fills the canopy volume with
        # realistic fine branches whose diameter matches the botanical
        # twig-to-leaf ratio.
        twig_enabled=True,
        twig_radius_ratio=0.035,
        twig_length_ratio=2.5,
        twig_curvature=0.35,
        twig_leaf_ratio=0.7,
    ):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            season: Input value used by this function.
            leaf_density_multiplier: Input value used by this function.
            leaf_size_multiplier: Input value used by this function.
            canopy_spread_multiplier: Input value used by this function.
            flower_density_multiplier: Input value used by this function.
            flower_size_multiplier: Input value used by this function.
            seed: Input value used by this function.
            samples_per_terminal_segment: Input value used by this function.
            leaves_per_cluster: Input value used by this function.
            flowers_per_tip: Input value used by this function.
            max_leaves: Input value used by this function.
            max_flowers: Input value used by this function.
            woody_species: Input value used by this function.
            twig_enabled: Input value used by this function.
            twig_radius_ratio: Input value used by this function.
            twig_length_ratio: Input value used by this function.
            twig_curvature: Input value used by this function.
            twig_leaf_ratio: Input value used by this function.
        """
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
        # Twig parameters:
        #   twig_enabled       -  master switch; False restores the legacy
        #                          "leaves on bark" attachment.
        #   twig_radius_ratio  -  twig base RADIUS as a fraction of the
        #                          attached leaf length.  Botanical ref:
        #                          Rosaceae 1-yr twig RADIUS / leaf length
        #                          ~ 0.030-0.045 (e.g. peach 3.5mm twig
        #                          radius vs 11.5cm leaf = 0.030).  0.035
        #                          is the visible default; the prior
        #                          0.015 was too thin to read in render.
        #   twig_length_ratio  -  twig length as a multiple of the
        #                          attached leaf length (short shoots
        #                          are 2-4 leaf-lengths long).
        #   twig_curvature     -  sideways bend magnitude (0 = straight,
        #                          1 = 90 deg over the length); 0.35
        #                          gives a gentle natural arc.
        #   twig_leaf_ratio    -  fraction of leaves placed on twigs
        #                          (brachyblast cluster at twig tip);
        #                          the remaining 1-ratio leaves stay on
        #                          the main branch bark (legacy per-
        #                          segment placement) to fill canopy
        #                          gaps.  0.0 = all-on-bark, 1.0 =
        #                          all-on-twig.  Only meaningful when
        #                          twig_enabled=True.
        self.twig_enabled = bool(twig_enabled)
        self.twig_radius_ratio = float(twig_radius_ratio)
        self.twig_length_ratio = float(twig_length_ratio)
        self.twig_curvature = float(twig_curvature)
        self.twig_leaf_ratio = max(0.0, min(1.0, float(twig_leaf_ratio)))
        self.validate()

    def validate(self):
        """Validate the current configuration and raise ValueError for invalid input.
        """
        get_season(self.season)
        for name in (
            "leaf_density_multiplier",
            "leaf_size_multiplier",
            "canopy_spread_multiplier",
            "flower_density_multiplier",
            "flower_size_multiplier",
            "twig_radius_ratio",
            "twig_length_ratio",
            "twig_curvature",
        ):
            if getattr(self, name) < 0.0:
                raise ValueError("{} cannot be negative".format(name))
        if not 0.0 <= self.twig_leaf_ratio <= 1.0:
            raise ValueError("twig_leaf_ratio must be in [0.0, 1.0]")
        if self.samples_per_terminal_segment < 1:
            raise ValueError("samples_per_terminal_segment must be positive")
        if self.leaves_per_cluster < 1 or self.flowers_per_tip < 1:
            raise ValueError("cluster sizes must be positive")
        if self.max_leaves < 0 or self.max_flowers < 0:
            raise ValueError("instance limits cannot be negative")
        if self.woody_species is not None:
            if self.woody_species not in WOODY_FLOWER_SPECS:
                raise ValueError(
                    "Unknown woody_species '{}' in flower specs; expected one of {}".format(
                        self.woody_species, sorted(WOODY_FLOWER_SPECS.keys())
                    )
                )
            if self.woody_species not in WOODY_LEAF_SPECS:
                raise ValueError(
                    "Unknown woody_species '{}' in leaf specs; expected one of {}".format(
                        self.woody_species, sorted(WOODY_LEAF_SPECS.keys())
                    )
                )
        if self.twig_curvature > 1.0:
            raise ValueError("twig_curvature must be <= 1.0 (90 degrees max bend)")


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
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            position: Input value used by this function.
            direction: Input value used by this function.
            azimuth: Input value used by this function.
            length: Input value used by this function.
            width: Input value used by this function.
            color_index: Input value used by this function.
            source_segment: Input value used by this function.
            attachment_id: Input value used by this function.
            asset_id: Input value used by this function.
            state: Input value used by this function.
            petiole_length: Input value used by this function.
            species: Input value used by this function.
            droop_factor: Input value used by this function.
            blade_curve: Input value used by this function.
            curl_variation: Input value used by this function.
            tip_fold: Input value used by this function.
            has_damage: Input value used by this function.
        """
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
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            position: Input value used by this function.
            direction: Input value used by this function.
            azimuth: Input value used by this function.
            size: Input value used by this function.
            color_index: Input value used by this function.
            openness: Input value used by this function.
            wilt: Input value used by this function.
            source_tip: Input value used by this function.
            attachment_id: Input value used by this function.
            asset_id: Input value used by this function.
            state: Input value used by this function.
            peduncle_length: Input value used by this function.
            species: Input value used by this function.
        """
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


class TwigInstance(object):
    """A visible fine shoot (twig) growing from a GrowthTip.

    Twigs carry leaves at their tips instead of leaves being glued
    directly to the main branch bark.  Each twig is a slightly curved
    tapered cylinder described by a start frame (position + tangent +
    side + normal) and a length, so the mesh builder can tessellate it
    with arbitrary radial/lengthwise resolution.  ``tip_index`` links
    the twig back to the parent GrowthTip so leaves can be associated
    with it.

    Parameters:
        tip_index (int): Index into ``TreeModel.tips`` of the parent
            growth tip this twig grows from.
        start (tuple): 3D position of the twig base (on the branch
            bark surface at the tip position).
        axis (tuple): Normalized initial direction the twig grows
            (typically the parent tip's direction).
        side (tuple): First radial basis vector of the start frame.
        normal (tuple): Second radial basis vector of the start frame.
        length (float): Total twig length in world units.
        base_radius (float): Twig radius at the base.
        tip_radius (float): Twig radius at the tip (after taper).
        bend_axis (tuple): Normalized direction in the side/normal
            plane along which the twig curves.  Curve magnitude is
            ``bend_strength``.
        bend_strength (float): Transverse offset of the twig tip due
            to curvature, in world units.
        seed (int): Stable per-twig random seed for future variation
            (e.g. bark texture, leaf arrangement).
    """

    __slots__ = (
        "tip_index",
        "start",
        "axis",
        "side",
        "normal",
        "length",
        "base_radius",
        "tip_radius",
        "bend_axis",
        "bend_strength",
        "seed",
        "leaf_attachment_id",
    )

    def __init__(
        self,
        tip_index,
        start,
        axis,
        side,
        normal,
        length,
        base_radius,
        tip_radius,
        bend_axis,
        bend_strength,
        seed,
        leaf_attachment_id,
    ):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            tip_index: Input value used by this function.
            start: Input value used by this function.
            axis: Input value used by this function.
            side: Input value used by this function.
            normal: Input value used by this function.
            length: Input value used by this function.
            base_radius: Input value used by this function.
            tip_radius: Input value used by this function.
            bend_axis: Input value used by this function.
            bend_strength: Input value used by this function.
            seed: Input value used by this function.
            leaf_attachment_id: Input value used by this function.
        """
        self.tip_index = int(tip_index)
        self.start = start
        self.axis = axis
        self.side = side
        self.normal = normal
        self.length = float(length)
        self.base_radius = float(base_radius)
        self.tip_radius = float(tip_radius)
        self.bend_axis = bend_axis
        self.bend_strength = float(bend_strength)
        self.seed = int(seed)
        self.leaf_attachment_id = str(leaf_attachment_id)

    def tip_position(self):
        """Return the 3D position of the twig tip (curved end).

        The curve is approximated as a single arc: the tip moves
        forward by ``length`` along ``axis`` and sideways by
        ``bend_strength`` along ``bend_axis``.
        """
        forward = _mul(self.axis, self.length)
        bend = _mul(self.bend_axis, self.bend_strength)
        return _add(_add(self.start, forward), bend)

    def point_at(self, t):
        """Return the 3D position at parameter ``t`` along the twig.

        Parameters:
            t (float): Curve parameter in [0, 1]; 0 = base, 1 = tip.
                Uses the same quadratic-bend approximation as
                ``tip_position`` so node flowers placed at intermediate
                ``t`` follow the twig's natural arc.

        Returns:
            tuple: 3D world position at parameter ``t``.
        """
        forward = _mul(self.axis, self.length * t)
        bend = _mul(self.bend_axis, self.bend_strength * t * t)
        return _add(_add(self.start, forward), bend)


class FoliageModel(object):
    def __init__(self, config, profile, leaves, flowers, asset_library=None, twigs=None):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            config: Input value used by this function.
            profile: Input value used by this function.
            leaves: Input value used by this function.
            flowers: Input value used by this function.
            asset_library: Input value used by this function.
            twigs: Input value used by this function.
        """
        self.config = config
        self.profile = profile
        self.leaves = leaves
        self.flowers = flowers
        self.asset_library = asset_library
        # Twigs (visible fine shoots).  Empty list preserves legacy
        # behavior when twig generation is disabled.
        self.twigs = twigs if twigs is not None else []


def _spread_direction(direction, rng, spread):
    """Internal helper for spread direction.

    Parameters:
        direction: Input value used by this function.
        rng: Input value used by this function.
        spread: Input value used by this function.
    """
    direction = _normalize(direction)
    jitter = (
        rng.uniform(-spread, spread),
        rng.uniform(-spread, spread),
        rng.uniform(-spread, spread),
    )
    return _normalize(_add(direction, jitter))


def _instance_copies(expected_count, rng):
    """Internal helper for instance copies.

    Parameters:
        expected_count: Input value used by this function.
        rng: Input value used by this function.
    """
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
    """Internal helper for lerp.

    Parameters:
        a: Input value used by this function.
        b: Input value used by this function.
        amount: Input value used by this function.
    """
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


# Flower-avoidance parameters for leaf sizing (2026-07):
# Real-world leaf-to-flower ratios are ~3x but in code flowers are
# visually enlarged ~8x, so leaves scaled to match (3.83x for peach)
# would be 60-90cm and completely cover the flowers.  To keep the
# realistic distant-canopy proportion while letting individual flowers
# read visually, leaves within ``FLOWER_AVOIDANCE_FADE_RADIUS`` of a
# flower socket are smoothly shrunk toward ``FLOWER_AVOIDANCE_MIN_SCALE``.
# The smoothstep fade avoids a hard "bald ring" around each flower.
FLOWER_AVOIDANCE_CORE_RADIUS = 0.15  # fully shrunk within this distance
FLOWER_AVOIDANCE_FADE_RADIUS = 0.35  # full size beyond this distance
FLOWER_AVOIDANCE_MIN_SCALE = 0.40    # min size multiplier near a flower


def _flower_avoidance_scale(leaf_position, flower_positions):
    """Return a 0..1 leaf-size multiplier based on distance to nearest flower.

    Leaves inside ``FLOWER_AVOIDANCE_CORE_RADIUS`` of any flower socket
    are scaled down to ``FLOWER_AVOIDANCE_MIN_SCALE`` so the flower
    reads visually; leaves beyond ``FLOWER_AVOIDANCE_FADE_RADIUS`` are
    left at full size.  A smoothstep transition in between avoids a
    visible ring of stunted leaves.

    Parameters:
        leaf_position (tuple): Leaf base position (xyz).
        flower_positions (list[tuple]): All flower socket positions.
    """
    if not flower_positions:
        return 1.0
    min_dist_sq = float("inf")
    for flower_pos in flower_positions:
        dx = leaf_position[0] - flower_pos[0]
        dy = leaf_position[1] - flower_pos[1]
        dz = leaf_position[2] - flower_pos[2]
        dist_sq = dx * dx + dy * dy + dz * dz
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
    distance = min_dist_sq ** 0.5
    if distance >= FLOWER_AVOIDANCE_FADE_RADIUS:
        return 1.0
    if distance <= FLOWER_AVOIDANCE_CORE_RADIUS:
        return FLOWER_AVOIDANCE_MIN_SCALE
    # Smoothstep transition between core and fade radii.
    t = (distance - FLOWER_AVOIDANCE_CORE_RADIUS) / (
        FLOWER_AVOIDANCE_FADE_RADIUS - FLOWER_AVOIDANCE_CORE_RADIUS
    )
    smooth_t = t * t * (3.0 - 2.0 * t)
    return FLOWER_AVOIDANCE_MIN_SCALE + (1.0 - FLOWER_AVOIDANCE_MIN_SCALE) * smooth_t


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
    """Internal helper for stable rng.

    Parameters:
        seed: Input value used by this function.
        identity: Input value used by this function.
    """
    return random.Random(int(stable_unit(seed, identity, "instance") * 2147483647))


# Botanical twig-node positions for solitary/fascicled flowers (peach,
# plum).  Flowers emerge from lateral buds along the twig, not the apex.
# t=0.35/0.55/0.75 spreads 2-3 nodes along the twig length, avoiding the
# very base (looks like a trunk flower) and the very tip (apex is for
# leaves in these species).
_TWIG_FLOWER_NODE_T_VALUES = (0.35, 0.55, 0.75)


# ---------------------------------------------------------------------------
# Flower-state ratios (bud / bloom / wilt) per species and season.
# Ratios are expressed as decimal weights that sum to 1.0.  Flowers are
# assigned a state via weighted random draw from the species-specific
# distribution so the canopy naturally contains all three phases
# simultaneously (early buds, peak blooms, fading flowers).
#
# State morphology (openness / wilt ranges for each state):
#   bud:    openness 0.10-0.28  (closed tight around the center)
#           wilt     0.00-0.08  (fresh, no droop)
#   bloom:  openness species_openness * rng(0.70, 1.0) * index_factor
#           wilt     min(0.15, season_wilt * rng(0.5, 1.0))
#   wilt:   openness 0.22-0.50  (partially open, petals curling inward)
#           wilt     0.55-0.85  (clearly drooping / shriveling)
#
# Plum (Prunus mume, "winter plum") is the only species that blooms in
# two seasons: an early sparse flush in winter (40% buds / 60% bloom,
# no wilt because nothing precedes it) and the peak flush in spring
# (10% buds / 70% bloom / 20% wilt from the winter wave fading).
FLOWER_STATE_RATIOS = {
    # Spring-only species: 2:7:1 (bud:bloom:wilt)
    ("peach", "spring"):  (0.20, 0.70, 0.10),
    ("cherry", "spring"): (0.20, 0.70, 0.10),
    ("pear", "spring"):   (0.20, 0.70, 0.10),
    # Plum spring: 1:7:2 (fewer buds, more fading from winter)
    ("plum", "spring"):   (0.10, 0.70, 0.20),
    # Plum winter: 4:6:0 (early flush, no wilt because it's the first wave)
    ("plum", "winter"):   (0.40, 0.60, 0.00),
}


def _assign_flower_state(species, season, rng):
    """Return the state label for one flower.

    Draws from ``FLOWER_STATE_RATIOS`` for the given species+season via
    a weighted random draw.  Falls back to the legacy ~10% bud behaviour
    for unknown combinations (generic flowers, seasons without a ratio
    entry).

    Parameters:
        species (str|None): Woody species key or None for generic.
        season (str): Season key ("spring"/"summer"/"autumn"/"winter").
        rng (random.Random): Stable per-flower RNG.

    Returns:
        str: ``"bud"``, ``"bloom"``, or ``"wilt"``.
    """
    ratios = FLOWER_STATE_RATIOS.get((species, season)) if species else None
    if ratios is None:
        # No ratio table entry: fall back to season-driven behaviour.
        # Autumn/winter (high profile_wilt) -> all wilted.
        # Summer/spring without species -> legacy ~10% bud / 90% bloom.
        if season in ("autumn", "winter"):
            return "wilt"
        if rng.random() < 0.10:
            return "bud"
        return "bloom"

    draw = rng.random()
    bud_r, bloom_r, wilt_r = ratios
    if draw < bud_r:
        return "bud"
    elif draw < bud_r + bloom_r:
        return "bloom"
    else:
        return "wilt"


def _flower_state_openness(state, local_rng, species_openness,
                           profile_openness, profile_wilt,
                           index=1.0):
    """Return ``(openness, wilt)`` for a given flower state.

    Parameters:
        state (str): ``"bud"``, ``"bloom"``, or ``"wilt"``.
        local_rng (random.Random): Per-flower stable RNG.
        species_openness (float): Species ``WoodyFlowerSpec.openness``
            (baseline openness for fully-bloomed flowers).
        profile_openness (float): Season profile ``flower_openness``.
        profile_wilt (float): Season profile ``flower_wilt``.
        index (float): Basipetal openness index (1.0 for first flower,
            progressively lower for later flowers on the same tip).
    """
    if state == "bud":
        return local_rng.uniform(0.10, 0.28), local_rng.uniform(0.0, 0.08)
    elif state == "bloom":
        openness = min(
            1.0,
            species_openness * profile_openness
            * local_rng.uniform(0.70, 1.0) * max(0.6, index),
        )
        wilt = min(0.15, profile_wilt * local_rng.uniform(0.5, 1.0))
        return openness, wilt
    else:  # wilt
        return local_rng.uniform(0.22, 0.50), local_rng.uniform(0.55, 0.85)


def _place_node_flowers_on_twig(
    twig, twig_index, tip, quota,
    config, profile, woody_flower_spec,
    flowers_out,
):
    """Place flowers on lateral twig nodes (peach, plum pattern).

    Botanical reference (Flora of China):
      - Peach: "buds 2-3 clustered, middle leaf bud, lateral flower
        buds"  ->  flowers emerge from lateral nodes, sessile.
      - Plum:  "flowers 1-3, fascicled"  ->  tight cluster of 1-3
        flowers per node, short pedicels.

    Distributes ``quota`` flowers across 2-3 nodes at t=0.35/0.55/0.75
    along the twig.  Each flower emerges perpendicular to the twig axis
    (radial outward) so flowers read as growing from the twig sides,
    not the apex.  Pedicel length follows the species spec (peach
    nearly sessile, plum short).

    Parameters:
        twig (TwigInstance): Twig carrying the flowers.
        twig_index (int): Index of the twig in the twigs list.
        tip (GrowthTip): Parent growth tip (for source_tip field).
        quota (int): Number of flowers to place on this twig.
        config (FoliageConfig): Provides seed and size multipliers.
        profile (SeasonProfile): Provides flower_size and palette.
        woody_flower_spec (WoodyFlowerSpec): Species-specific flower
            morphology (pedicel_ratio, droop_bias, etc.).
        flowers_out (list): Output list to append FlowerInstance to.
    """
    node_count = min(len(_TWIG_FLOWER_NODE_T_VALUES), max(1, quota))
    flowers_per_node = max(1, quota // node_count)
    remaining = quota
    flower_global_idx = 0
    for node_idx in range(node_count):
        if remaining <= 0:
            break
        node_t = _TWIG_FLOWER_NODE_T_VALUES[node_idx]
        node_pos = twig.point_at(node_t)
        node_flower_count = min(flowers_per_node, remaining)
        for node_flower_idx in range(node_flower_count):
            attachment_id = "twig:{}:flower{}".format(twig_index, flower_global_idx)
            local_rng = _stable_rng(config.seed, attachment_id)
            size = profile.flower_size * config.flower_size_multiplier
            size *= local_rng.uniform(0.80, 1.20)
            size *= woody_flower_spec.size_factor
            # Golden-angle phyllotaxis around the twig axis: each flower
            # on a node gets a radial outward direction so the cluster
            # fans around the twig circumference.
            golden_angle = 2.39996
            angle = flower_global_idx * golden_angle
            side_radius = twig.base_radius * 1.15
            radial_offset = _add(
                _mul(twig.side, math.cos(angle) * side_radius),
                _mul(twig.normal, math.sin(angle) * side_radius),
            )
            flower_position = _add(node_pos, radial_offset)
            # Pedicel: short for peach (sessile), short for plum.
            peduncle_length = (
                size * woody_flower_spec.pedicel_ratio
                * local_rng.uniform(0.80, 1.20)
            )
            azimuth = local_rng.uniform(0.0, 360.0)
            # Outward direction perpendicular to twig axis.
            outward = _normalize(
                _add(
                    _mul(twig.side, math.cos(angle)),
                    _mul(twig.normal, math.sin(angle)),
                )
            )
            # Apply species-specific droop bias (peach neutral, plum neutral).
            droop_bias = woody_flower_spec.droop_bias
            if droop_bias != 0.0:
                world_up = (0.0, 1.0, 0.0)
                outward = _normalize(_add(outward, _mul(world_up, droop_bias)))
            raw_direction = _spread_direction(outward, local_rng, 0.40)
            # Species+season-aware state assignment (2026-07):
            # bud / bloom / wilt per FLOWER_STATE_RATIOS.
            state = _assign_flower_state(
                config.woody_species, config.season, local_rng,
            )
            index_factor = 1.0 - 0.18 * min(flower_global_idx, 3)
            species_openness = getattr(woody_flower_spec, "openness", 1.0)
            flower_openness, flower_wilt = _flower_state_openness(
                state, local_rng, species_openness,
                profile.flower_openness, profile.flower_wilt,
                index=index_factor,
            )
            flowers_out.append(
                FlowerInstance(
                    position=flower_position,
                    direction=raw_direction,
                    azimuth=azimuth,
                    size=size,
                    color_index=local_rng.randrange(len(profile.flower_palette)),
                    openness=flower_openness,
                    wilt=flower_wilt,
                    source_tip=twig.tip_index,
                    attachment_id=attachment_id,
                    asset_id=None,
                    state=FLOWER_STATE_BY_SEASON[config.season],
                    peduncle_length=peduncle_length,
                    species=config.woody_species,
                )
            )
            flower_global_idx += 1
            remaining -= 1


def _place_tip_inflorescence_on_twig(
    twig, twig_index, tip, quota,
    config, profile, woody_flower_spec,
    flowers_out,
):
    """Place flowers at the twig tip in a corymb/umbel (cherry, pear).

    Botanical reference (Flora of China):
      - Cherry: "umbel-like corymb, 3-5 flowers at branch tip, pedicel
        1.5-3cm"  ->  flowers cluster at apex with a central peduncle
        and long drooping pedicels.
      - Pear:   "corymb, 6-9 flowers, mixed bud (flowers + leaves at
        tip), pedicel 3.5-5cm"  ->  same corymb structure, erect
        (non-drooping), more flowers.

    All ``quota`` flowers start at the twig tip; the first flower sits
    at the peduncle tip (forward of the twig apex by peduncle_ratio),
    subsequent flowers fan out on a hemisphere via golden-angle
    phyllotaxis.  Pedicel length and droop follow the species spec.

    Parameters:
        twig (TwigInstance): Twig carrying the flowers.
        twig_index (int): Index of the twig in the twigs list.
        tip (GrowthTip): Parent growth tip (for source_tip field).
        quota (int): Number of flowers to place on this twig.
        config (FoliageConfig): Provides seed and size multipliers.
        profile (SeasonProfile): Provides flower_size and palette.
        woody_flower_spec (WoodyFlowerSpec): Species-specific flower
            morphology (pedicel_ratio, peduncle_ratio, droop_bias).
        flowers_out (list): Output list to append FlowerInstance to.
    """
    twig_tip_pos = twig.tip_position()
    tip_heading = twig.axis
    twig_normal = twig.normal
    for flower_idx in range(quota):
        attachment_id = "twig:{}:flower{}".format(twig_index, flower_idx)
        local_rng = _stable_rng(config.seed, attachment_id)
        size = profile.flower_size * config.flower_size_multiplier
        size *= local_rng.uniform(0.80, 1.20)
        size *= woody_flower_spec.size_factor
        # Start at the twig tip.
        flower_position = twig_tip_pos
        # Central peduncle: extend forward from the twig tip before
        # individual pedicels fan out (corymb structure).
        peduncle_ratio = woody_flower_spec.peduncle_ratio
        if peduncle_ratio > 0.0:
            peduncle_len = (
                size * peduncle_ratio * local_rng.uniform(0.85, 1.15)
            )
            peduncle_tip = _add(flower_position, _mul(tip_heading, peduncle_len))
        else:
            peduncle_tip = flower_position
        # First flower sits at the peduncle tip; subsequent flowers
        # fan out on a hemisphere from there.
        if flower_idx == 0:
            flower_position = peduncle_tip
        else:
            golden_angle = 2.399963
            fan_angle = flower_idx * golden_angle
            fan_radius = size * 0.55 * (0.5 + 0.5 * flower_idx ** 0.5)
            # Perpendicular frame around tip_heading.
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
            # Slight forward offset so flowers don't clip the twig.
            offset = _add(offset, _mul(tip_heading, size * 0.2 * flower_idx))
            flower_position = _add(peduncle_tip, offset)
        # Pedicel length from species spec (cherry long, pear moderate).
        peduncle_length = (
            size * woody_flower_spec.pedicel_ratio
            * local_rng.uniform(0.80, 1.20)
        )
        azimuth = local_rng.uniform(0.0, 360.0)
        # Base direction: along twig axis with outward radial tilt.
        base_direction = _normalize(
            _add(_mul(tip_heading, 0.70), _mul(twig_normal, 0.30))
        )
        # Species-specific droop (cherry droops down, pear faces up).
        droop_bias = woody_flower_spec.droop_bias
        if droop_bias != 0.0:
            world_up = (0.0, 1.0, 0.0)
            base_direction = _normalize(
                _add(base_direction, _mul(world_up, droop_bias))
            )
        raw_direction = _spread_direction(base_direction, local_rng, 0.40)
        # Species+season-aware state assignment (2026-07).
        state = _assign_flower_state(
            config.woody_species, config.season, local_rng,
        )
        index_factor = 1.0 - 0.18 * min(flower_idx, 3)
        species_openness = getattr(woody_flower_spec, "openness", 1.0)
        flower_openness, flower_wilt = _flower_state_openness(
            state, local_rng, species_openness,
            profile.flower_openness, profile.flower_wilt,
            index=index_factor,
        )
        flowers_out.append(
            FlowerInstance(
                position=flower_position,
                direction=raw_direction,
                azimuth=azimuth,
                size=size,
                color_index=local_rng.randrange(len(profile.flower_palette)),
                openness=flower_openness,
                wilt=flower_wilt,
                source_tip=twig.tip_index,
                attachment_id=attachment_id,
                asset_id=None,
                state=FLOWER_STATE_BY_SEASON[config.season],
                peduncle_length=peduncle_length,
                species=config.woody_species,
            )
        )


def _build_twig_for_tip(tip, tip_index, config, leaf_length_for_sizing, profile):
    """Build a TwigInstance growing from a single GrowthTip.

    The twig is a slightly curved tapered cylinder whose base sits at
    ``tip.position`` and whose axis follows ``tip.direction`` (outward
    from the parent branch).  Length and radius are derived from the
    attached leaf length so the twig-to-leaf ratio stays botanical
    even when leaves are visually enlarged.

    Parameters:
        tip (GrowthTip): Parent growth tip the twig grows from.
        tip_index (int): Index of the tip in ``TreeModel.tips``.
        config (FoliageConfig): Provides twig_ratio/length/curvature.
        leaf_length_for_sizing (float): Representative leaf length in
            world units (already includes species scale); used to size
            the twig so the ratio is preserved.
        profile (SeasonProfile): Season profile (currently unused but
            kept for future season-dependent twig morphology).

    Returns:
        TwigInstance|None: A new twig, or None if the tip direction is
            degenerate and no valid frame can be built.
    """
    twig_axis = _normalize(getattr(tip, "direction", (0.0, 1.0, 0.0)))
    # Build an orthonormal frame (axis, side, normal) for tessellation.
    helper = (0.0, 1.0, 0.0)
    if abs(_dot(twig_axis, helper)) > 0.92:
        helper = (1.0, 0.0, 0.0)
    twig_side = _normalize(_cross_vectors(twig_axis, helper))
    twig_normal = _normalize(_cross_vectors(twig_axis, twig_side))

    twig_length = leaf_length_for_sizing * config.twig_length_ratio
    # Diameter ratio is botanical; base_radius = leaf_length * ratio
    # (ratio is already a radius fraction, not a diameter fraction).
    twig_base_radius = leaf_length_for_sizing * config.twig_radius_ratio
    # Taper to ~30% at the tip (botanical: twigs narrow toward apex).
    twig_tip_radius = twig_base_radius * 0.30

    # Random bend direction in the side/normal plane, magnitude scaled
    # by curvature and twig length.  Stable per-tip seed ensures the
    # bend is reproducible across regenerations with the same config.
    twig_rng = _stable_rng(config.seed, "twig:{}".format(tip_index))
    bend_angle = twig_rng.uniform(0.0, 2.0 * math.pi)
    bend_dir = _normalize(
        _add(
            _mul(twig_side, math.cos(bend_angle)),
            _mul(twig_normal, math.sin(bend_angle)),
        )
    )
    # Slight downward bias: blend the random bend direction with world
    # down so twigs tend to droop under gravity (more natural than
    # perfectly symmetric star patterns).
    bend_dir = _normalize(
        _add(_mul(bend_dir, 0.75), _mul((0.0, -1.0, 0.0), 0.25))
    )
    twig_bend_strength = (
        config.twig_curvature * twig_length * twig_rng.uniform(0.55, 1.0)
    )

    return TwigInstance(
        tip_index=tip_index,
        start=tip.position,
        axis=twig_axis,
        side=twig_side,
        normal=twig_normal,
        length=twig_length,
        base_radius=twig_base_radius,
        tip_radius=twig_tip_radius,
        bend_axis=bend_dir,
        bend_strength=twig_bend_strength,
        seed=int(twig_rng.random() * 2147483647),
        leaf_attachment_id="twig:{}".format(tip_index),
    )


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
    # Collect flower socket positions once for leaf flower-avoidance
    # sizing.  Leaves near a flower are smoothly shrunk so the flower
    # reads visually despite the (intentionally enlarged) leaf scale.
    flower_positions = [
        socket.position
        for socket in getattr(tree_model, "attachment_points", ())
        if socket.kind == "flower"
    ]
    for socket in getattr(tree_model, "attachment_points", ()):
        if socket.kind == "leaf":
            leaf_sockets_by_segment.setdefault(socket.segment_index, []).append(socket)

    # --- Twig generation (2026-07) ---
    # When twig_enabled, each GrowthTip grows a visible curved twig and
    # leaves attach to the twig tip (brachyblast / short-shoot pattern)
    # instead of being glued to the main branch bark.  This fills the
    # canopy volume with realistic fine branches whose diameter matches
    # the botanical twig-to-leaf ratio.
    twigs = []
    if config.twig_enabled:
        # Representative leaf length used to size the twig so the
        # twig-to-leaf ratio stays botanical even when leaves are
        # visually enlarged.
        leaf_length_for_sizing = profile.leaf_size * config.leaf_size_multiplier
        if woody_leaf_spec is not None:
            leaf_length_for_sizing *= woody_leaf_spec.leaf_size_factor
        seen_twig_positions = set()
        for tip_index, tip in enumerate(tree_model.tips):
            position_key = tuple(round(v, 4) for v in tip.position)
            if position_key in seen_twig_positions:
                continue
            seen_twig_positions.add(position_key)
            if preset_key != "willow_weeping" and tip.position[1] < canopy_base:
                continue
            if tip.depth < minimum_leaf_depth:
                continue
            twig = _build_twig_for_tip(
                tip, tip_index, config, leaf_length_for_sizing, profile
            )
            if twig is not None:
                twigs.append(twig)

    if config.twig_enabled and twigs and config.twig_leaf_ratio > 0.0:
        # Brachyblast leaf placement: each twig bears a cluster of
        # leaves at its tip, distributed by golden-angle phyllotaxis
        # so they fan out naturally rather than stacking.  The cluster
        # size scales with ``expected_leaf_copies`` so seasons (which
        # vary leaf_density) still affect twig leaf count  -  summer
        # twigs carry more leaves than spring, spring more than winter.
        #
        # Mixed placement (2026-07): only ``twig_leaf_ratio`` fraction
        # of the total leaf budget goes to twigs; the rest goes to the
        # bark-placement block below so the canopy keeps a dense
        # underlay of bark-attached leaves filling gaps between twigs.
        # ratio=1.0 restores the prior all-on-twig behavior; ratio=0.0
        # (or twig_enabled=False) falls through to bark-only placement.
        twig_leaf_budget = int(config.max_leaves * config.twig_leaf_ratio)
        leaves_per_twig = (
            config.leaves_per_cluster
            * config.samples_per_terminal_segment
            * expected_leaf_copies
        )
        twig_leaf_quotas = _fair_capped_quotas(
            [leaves_per_twig] * len(twigs),
            twig_leaf_budget,
            rng,
        )
        for twig_index, twig in enumerate(twigs):
            twig_tip_pos = twig.tip_position()
            tip = tree_model.tips[twig.tip_index]
            for leaf_index in range(twig_leaf_quotas[twig_index]):
                attachment_id = "{}:leaf{}".format(
                    twig.leaf_attachment_id, leaf_index
                )
                local_rng = _stable_rng(config.seed, attachment_id)
                length = profile.leaf_size * config.leaf_size_multiplier
                length *= local_rng.uniform(0.78, 1.22)
                if woody_leaf_spec is not None:
                    length *= woody_leaf_spec.leaf_size_factor
                # Phyllotaxis offset: golden-angle spiral around the
                # twig axis distributes leaves around the twig tip.
                golden_angle = 2.39996
                angle = leaf_index * golden_angle
                offset_radius = twig.base_radius * 1.5 * (
                    0.5 + 0.5 * local_rng.random()
                )
                offset = _add(
                    _mul(twig.side, math.cos(angle) * offset_radius),
                    _mul(twig.normal, math.sin(angle) * offset_radius),
                )
                leaf_position = _add(twig_tip_pos, offset)
                # Flower-avoidance shrink (flowers grow from the same
                # tips, so leaves at twig tips would block them without
                # this).  The shrink keeps the leaf silhouette
                # proportional by scaling length and width together.
                avoidance_scale = _flower_avoidance_scale(
                    leaf_position, flower_positions
                )
                length *= avoidance_scale
                petiole_length = length * local_rng.uniform(0.15, 0.30)
                azimuth = local_rng.uniform(0.0, 360.0)
                if woody_leaf_spec is not None:
                    width = (
                        length / woody_leaf_spec.length_width_ratio
                        * local_rng.uniform(0.82, 1.18)
                    )
                else:
                    width = length * leaf_width_ratio * local_rng.uniform(0.82, 1.18)
                # Leaf direction grows outward from the twig axis with
                # a small upward bias (phototropism) and gravity droop.
                height_ratio = (
                    (leaf_position[1] - canopy_base)
                    / max(tree_height - canopy_base, 1.0e-6)
                )
                height_ratio = max(0.0, min(1.0, height_ratio))
                droop_factor = 0.65 - 0.50 * height_ratio
                droop_factor *= local_rng.uniform(0.80, 1.20)
                vertical_bias = 0.25 * (height_ratio - 0.4)
                outward = _normalize(
                    _add(
                        _add(_mul(twig.axis, 0.45), _mul(twig.normal, 0.45)),
                        (0.0, vertical_bias, 0.0),
                    )
                )
                raw_direction = _spread_direction(
                    outward, local_rng, 0.55 + 0.30 * 0.9
                )
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
                        source_segment=(
                            tip.parent_segment
                            if tip.parent_segment is not None
                            else 0
                        ),
                        attachment_id=attachment_id,
                        asset_id=None,
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

    # Bark-attached leaf placement: leaves attach directly to the main
    # branch bark surface via frustum projection.  Runs in THREE cases:
    #   1. twig_enabled=False  ->  all leaves on bark (legacy behavior,
    #      full max_leaves budget, preserves surface-hugging tests).
    #   2. twig_enabled=True, twig_leaf_ratio<1.0  ->  remaining budget
    #      (max_leaves * (1-ratio)) fills canopy gaps between twigs.
    #   3. twig_enabled=True, twig_leaf_ratio=1.0  ->  skipped (all
    #      leaves already placed on twigs above).
    twig_all_on_twig = (
        config.twig_enabled
        and bool(twigs)
        and config.twig_leaf_ratio >= 1.0
    )
    if not twig_all_on_twig:
        # Bark budget: full max_leaves when no twig leaves were placed
        # (legacy), otherwise the residual after twig leaves took their
        # share.  This keeps the total leaf count bounded by max_leaves
        # regardless of the twig/bark split.
        if config.twig_enabled and twigs and config.twig_leaf_ratio > 0.0:
            bark_leaf_budget = config.max_leaves - int(
                config.max_leaves * config.twig_leaf_ratio
            )
        else:
            bark_leaf_budget = config.max_leaves
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
            bark_leaf_budget,
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
                # Flower-avoidance shrink: leaves within
                # FLOWER_AVOIDANCE_FADE_RADIUS of any flower socket are
                # smoothly shrunk so the flower reads visually despite the
                # enlarged leaf scale.  Both length and width (and the
                # petiole derived from length) shrink together to keep the
                # leaf silhouette proportional.
                avoidance_scale = _flower_avoidance_scale(
                    leaf_position, flower_positions
                )
                length *= avoidance_scale
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
    flower_socket_by_id = dict(
        (socket.id, socket)
        for socket in getattr(tree_model, "attachment_points", ())
        if socket.kind == "flower"
    )

    # --- Botanical flower placement (2026-07) ---
    # When twigs are enabled and a woody species is selected, flowers
    # grow from TWIGS (not main-branch bark) following species-specific
    # morphology (Flora of China / eflora):
    #   - Peach/plum (solitary/fascicled): flowers on twig NODES (along
    #     the twig sides at t=0.35/0.55/0.75), short pedicels.  This
    #     matches the botanical "buds 2-3 clustered, lateral flowers"
    #     pattern: flowers emerge from lateral nodes, not the apex.
    #   - Cherry/pear (corymbose): flowers at twig TIP in an umbel/
    #     corymb, long pedicels fanning from a central peduncle.
    # twig_enabled=False preserves the legacy bark-surface placement
    # (flowers projected onto GrowthTip bark via frustum projection).
    use_twig_flower_path = (
        config.twig_enabled
        and bool(twigs)
        and woody_flower_spec is not None
        and expected_flower_copies > 0.0
    )

    if use_twig_flower_path:
        inflorescence_type = woody_flower_spec.inflorescence
        flowers_per_twig_target = (
            woody_flower_spec.flowers_per_inflorescence * expected_flower_copies
        )
        # _instance_copies handles fractional expected counts via
        # probabilistic rounding (e.g. 0.6 -> 0 or 1 with 60% chance),
        # matching the legacy bark-placement path.  Without this, sparse
        # seasons (plum winter density=0.20 -> 0.6 flowers/twig) would
        # truncate to 0 and produce no flowers at all.
        twig_flower_desired = [
            _instance_copies(flowers_per_twig_target, _stable_rng(config.seed, "twig-flower-quota:{}".format(idx)))
            for idx in range(len(twigs))
        ]
        twig_flower_quotas = _fair_capped_quotas(
            twig_flower_desired,
            config.max_flowers,
            rng,
        )
        for twig_index, twig in enumerate(twigs):
            tip = tree_model.tips[twig.tip_index]
            quota = twig_flower_quotas[twig_index]
            if quota == 0:
                continue

            if inflorescence_type in ("solitary", "fascicled"):
                # --- Node flowers (peach, plum) ---
                # Botanical ref: peach "buds 2-3 clustered, middle leaf
                # bud, lateral flower buds"; plum "flowers 1-3, fascicled".
                # Flowers emerge from lateral nodes along the twig, not
                # the apex.  Distribute 2-3 nodes at t=0.35/0.55/0.75 so
                # flowers spread along the twig length.
                _place_node_flowers_on_twig(
                    twig, twig_index, tip, quota,
                    config, profile, woody_flower_spec,
                    flowers,
                )
            else:
                # --- Tip inflorescence (cherry, pear) ---
                # Botanical ref: cherry "umbel-like corymb, 3-5 flowers
                # at branch tip"; pear "corymb, 6-9 flowers, mixed bud
                # (flowers + leaves at tip)".  All flowers cluster at
                # the twig tip with a central peduncle fanning out.
                _place_tip_inflorescence_on_twig(
                    twig, twig_index, tip, quota,
                    config, profile, woody_flower_spec,
                    flowers,
                )
    else:
        # --- Legacy bark-surface flower placement ---
        # Flowers attach to GrowthTip bark via frustum projection.  Used
        # when twig_enabled=False (preserves original behavior and the
        # willow flower-coverage regression test) or when no woody
        # species is selected (generic procedural flowers).
        flower_sites = []
        desired_flower_counts = []
        seen_tip_positions = set()
        expected_flowers_per_tip = (
            woody_flower_spec.flowers_per_inflorescence * expected_flower_copies
            if woody_flower_spec is not None
            else config.flowers_per_tip * expected_flower_copies
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
                    size *= woody_flower_spec.size_factor
                # The pedicel base (contact point) must lie EXACTLY on the
                # branch bark surface via analytical frustum projection.
                if flower_segment is not None:
                    flower_position = _project_to_branch_surface(socket, flower_segment)
                else:
                    flower_position = tip.position
                socket_tangent = _normalize(getattr(socket, "tangent", tip.direction))
                socket_exposure = float(getattr(socket, "exposure", 1.0))
                openness_boost = 0.88 + 0.12 * socket_exposure
                peduncle_length = size * local_rng.uniform(0.30, 0.60)
                if woody_flower_spec is not None:
                    peduncle_length = size * woody_flower_spec.pedicel_ratio * local_rng.uniform(0.80, 1.20)
                azimuth = local_rng.uniform(0.0, 360.0)
                tip_heading = _normalize(getattr(tip, "direction", socket_tangent))
                socket_normal = _normalize(getattr(socket, "normal", (0.0, 1.0, 0.0)))
                inflorescence = (
                    woody_flower_spec.inflorescence
                    if woody_flower_spec is not None
                    else "racemose"
                )
                peduncle_tip = flower_position
                if inflorescence == "corymbose" and woody_flower_spec is not None:
                    peduncle_ratio = woody_flower_spec.peduncle_ratio
                    if peduncle_ratio > 0.0:
                        peduncle_len = size * peduncle_ratio * local_rng.uniform(0.85, 1.15)
                        peduncle_tip = _add(
                            flower_position,
                            _mul(tip_heading, peduncle_len),
                        )
                    if flower_index == 0:
                        flower_position = peduncle_tip
                if flower_index > 0:
                    if inflorescence == "corymbose":
                        golden_angle = 2.399963
                        fan_angle = flower_index * golden_angle
                        fan_radius = size * 0.55 * (0.5 + 0.5 * flower_index ** 0.5)
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
                        offset = _add(offset, _mul(tip_heading, size * 0.2 * flower_index))
                        flower_position = _add(peduncle_tip, offset)
                    elif inflorescence == "fascicled":
                        golden_angle = 2.399963
                        cluster_angle = flower_index * golden_angle
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
                        offset = _add(offset, _mul(tip_heading, size * 0.08 * flower_index))
                        flower_position = _add(flower_position, offset)
                    else:
                        spacing = size * 0.6 * flower_index
                        flower_position = _add(
                            flower_position, _mul(tip_heading, spacing)
                        )
                base_direction = _normalize(
                    _add(_mul(tip_heading, 0.70), _mul(socket_normal, 0.30))
                )
                droop_bias = woody_flower_spec.droop_bias if woody_flower_spec is not None else 0.0
                if droop_bias != 0.0:
                    world_up = (0.0, 1.0, 0.0)
                    base_direction = _normalize(
                        _add(base_direction, _mul(world_up, droop_bias))
                    )
                raw_direction = _spread_direction(base_direction, local_rng, 0.40)
                # Species+season-aware state assignment (2026-07).
                state = _assign_flower_state(
                    config.woody_species, config.season, local_rng,
                )
                index_factor = (1.0 - 0.18 * min(flower_index, 3)) * openness_boost
                species_openness = getattr(woody_flower_spec, "openness", 1.0)
                flower_openness, flower_wilt = _flower_state_openness(
                    state, local_rng, species_openness,
                    profile.flower_openness, profile.flower_wilt,
                    index=index_factor,
                )
                flowers.append(
                    FlowerInstance(
                        position=flower_position,
                        direction=raw_direction,
                        azimuth=azimuth,
                        size=size,
                        color_index=local_rng.randrange(len(profile.flower_palette)),
                        openness=flower_openness,
                        wilt=flower_wilt,
                        source_tip=tip_index,
                        attachment_id=attachment_id,
                        asset_id=None,
                        state=FLOWER_STATE_BY_SEASON[config.season],
                        peduncle_length=peduncle_length,
                        species=config.woody_species,
                    )
                )

    return FoliageModel(config, profile, leaves, flowers, None, twigs=twigs)
