# -*- coding: utf-8 -*-
"""Build combined Maya meshes for season-driven leaves and flowers."""

from __future__ import division, print_function

import math
import json
from collections import Counter

from .foliage import (
    FlowerInstance,
    FoliageConfig,
    LeafInstance,
    TwigInstance,
    WOODY_FLOWER_SPECS,
    WOODY_LEAF_SPECS,
    generate_foliage,
)
from .math_utils import (
    add as _add,
    sub as _sub,
    mul as _mul,
    dot as _dot,
    cross as _cross,
    normalize_default as _normalize,
)


# Botanical calyx green  -  the sepal whorl is a leaf-derived structure
# and stays green across all Rosaceae blossoms regardless of petal
# color.  Used as the dedicated sepal material color so the calyx
# reads as a real green base instead of being dyed by the seasonal
# flower-center color (which made blossoms look chrome-wrong).
SEPAL_GREEN_COLOR = (0.18, 0.42, 0.14)


def _orientation(direction, azimuth_degrees):
    """Build an orthonormal frame (forward, side, normal) from a direction.

    Parameters:
        direction (tuple): 3-vector pointing along the organ's length.
        azimuth_degrees (float): Rotation around the forward axis used to
            spin the side/normal pair (controls petal/leaf facing).
    """
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


def _emit_cylinder(points, counts, connects, start, axis, side, normal,
                   length, radius, segments=4, rings=2, taper=0.45):
    """Append a tapered cylinder mesh between two points along ``axis``.

    Used for petioles and pedicels  -  gives them volume and a real silhouette
    instead of the previous flat triangle.  ``segments`` is the radial
    subdivision (4 -> square-prism-ish, 6 -> hexagonal), ``rings`` is the
    number of lengthwise subdivisions (>=2 produces a tapered stem with
    mid-radius interpolation).  ``taper`` is the end radius as a fraction
    of the start radius  -  smaller values produce a more pronounced taper
    (botanically, pedicels narrow toward the receptacle).
    """
    start_radius = float(radius)
    end_radius = float(radius) * float(taper)
    axis_n = _normalize(axis)
    entry_base = len(points)
    # Radial vertex ring at each lengthwise station.
    ring_verts = []
    for ring in range(rings + 1):
        t = float(ring) / float(rings)
        center = _add(start, _mul(axis_n, length * t))
        r = start_radius + (end_radius - start_radius) * t
        ring = []
        for seg in range(segments):
            angle = 2.0 * math.pi * seg / segments
            offset = _add(_mul(side, math.cos(angle) * r), _mul(normal, math.sin(angle) * r))
            ring.append(len(points))
            points.append(_add(center, offset))
        ring_verts.append(ring)
    # Cap the base so the stem looks solid where it meets the branch.
    # Emit the cap as ``segments`` triangles (not one n-gon) so the
    # connects array stays a flat list of ints consistent with counts.
    base_center_idx = len(points)
    points.append(start)
    for seg in range(segments):
        counts.append(3)
        connects.extend((base_center_idx, entry_base + seg, entry_base + (seg + 1) % segments))
    # Side quads (as two triangles each) between consecutive rings.
    for ring in range(rings):
        for seg in range(segments):
            a = ring_verts[ring][seg]
            b = ring_verts[ring][(seg + 1) % segments]
            c = ring_verts[ring + 1][(seg + 1) % segments]
            d = ring_verts[ring + 1][seg]
            counts.append(3)
            connects.extend((a, b, c))
            counts.append(3)
            connects.extend((a, c, d))


# Octahedron triangle fan  -  shared topology for receptacle, ovary, and
# stigma.  Each part emits 6 vertices (axis +/-, side +/-, normal +/-) and
# 8 triangles forming a closed diamond.  Extracted as a helper because
# all three floral-center substructures use the identical fan layout.
_OCTAHEDRON_TRIANGLES = (
    (0, 2, 4), (0, 4, 3), (0, 3, 5), (0, 5, 2),
    (1, 4, 2), (1, 3, 4), (1, 5, 3), (1, 2, 5),
)


def _emit_octahedron(points, counts, connects, center, axis, side, normal,
                     radius, axis_scale=1.0):
    """Append a 6-vertex / 8-face octahedron centered at ``center``.

    The axis-direction poles are scaled by ``axis_scale`` so callers can
    flatten the diamond into a disc (receptacle, axis_scale=0.4) or keep
    it spherical (ovary/stigma, axis_scale=1.0).  Returns nothing  -  the
    points/counts/connects arrays are mutated in place, matching the
    convention of ``_emit_cylinder`` and ``_emit_sepal``.
    """
    base = len(points)
    points.extend((
        _add(center, _mul(axis, radius * axis_scale)),
        _add(center, _mul(axis, -radius * axis_scale)),
        _add(center, _mul(side, radius)),
        _add(center, _mul(side, -radius)),
        _add(center, _mul(normal, radius)),
        _add(center, _mul(normal, -radius)),
    ))
    for triangle in _OCTAHEDRON_TRIANGLES:
        counts.append(3)
        connects.extend(base + index for index in triangle)


def _emit_curved_cylinder(points, counts, connects, start, axis, side, normal,
                          length, base_radius, tip_radius, bend_axis,
                          bend_strength, segments=8, rings=6):
    """Append a curved tapered cylinder between two points along ``axis``.

    Used for twigs (fine shoots).  Unlike ``_emit_cylinder`` (which is
    straight), this variant bends the cylinder sideways along
    ``bend_axis`` by ``bend_strength`` over its length, producing a
    gentle natural arc instead of a stiff straight stick.  Radius
    interpolates from ``base_radius`` at the start to ``tip_radius`` at
    the end (linear taper).  ``segments`` is the radial subdivision
    (8 -> smooth round silhouette for visible twigs; the prior 6 was
    too faceted at the new larger radius), ``rings`` is the lengthwise
    subdivision (>=5 needed to read the curve smoothly).
    """
    axis_n = _normalize(axis)
    bend_axis_n = _normalize(bend_axis)
    entry_base = len(points)
    ring_verts = []
    for ring in range(rings + 1):
        t = float(ring) / float(rings)
        # Forward position along the axis (linear in t).
        forward = _mul(axis_n, length * t)
        # Sideways bend: quadratic in t so the bend starts gently and
        # accumulates toward the tip (cantilever gravity curve).
        bend = _mul(bend_axis_n, bend_strength * t * t)
        center = _add(_add(start, forward), bend)
        # Linear taper from base_radius to tip_radius.
        r = base_radius + (tip_radius - base_radius) * t
        ring = []
        for seg in range(segments):
            angle = 2.0 * math.pi * seg / segments
            offset = _add(
                _mul(side, math.cos(angle) * r),
                _mul(normal, math.sin(angle) * r),
            )
            ring.append(len(points))
            points.append(_add(center, offset))
        ring_verts.append(ring)
    # Cap the base so the twig looks solid where it meets the branch.
    base_center_idx = len(points)
    points.append(start)
    for seg in range(segments):
        counts.append(3)
        connects.extend((
            base_center_idx,
            entry_base + seg,
            entry_base + (seg + 1) % segments,
        ))
    # Side quads (as two triangles each) between consecutive rings.
    for ring in range(rings):
        for seg in range(segments):
            a = ring_verts[ring][seg]
            b = ring_verts[ring][(seg + 1) % segments]
            c = ring_verts[ring + 1][(seg + 1) % segments]
            d = ring_verts[ring + 1][seg]
            counts.append(3)
            connects.extend((a, b, c))
            counts.append(3)
            connects.extend((a, c, d))


def build_twig_mesh_arrays(foliage_model):
    """Return a single mesh-array group containing all twig geometry.

    Each twig is emitted as a curved tapered cylinder using
    ``_emit_curved_cylinder``.  All twigs share the same bark material
    (assigned by the caller via ``_get_bark_shading_group``) so they
    visually blend with the main branches.

    Parameters:
        foliage_model (FoliageModel): Foliage model whose ``twigs`` list
            is to be tessellated.

    Returns:
        dict: Single-entry dict ``{0: (points, counts, connects)}`` so
        the caller can iterate the same way as ``build_leaf_mesh_groups``.
        Returns ``{}`` when there are no twigs.
    """
    points = []
    counts = []
    connects = []
    for twig in foliage_model.twigs:
        _emit_curved_cylinder(
            points, counts, connects,
            start=twig.start,
            axis=twig.axis,
            side=twig.side,
            normal=twig.normal,
            length=twig.length,
            base_radius=twig.base_radius,
            tip_radius=twig.tip_radius,
            bend_axis=twig.bend_axis,
            bend_strength=twig.bend_strength,
            segments=8,
            rings=6,
        )
    if not points:
        return {}
    return {0: (points, counts, connects)}


def _get_twig_shading_group(cmds):
    """Return (or lazily create) the bark shading group for twigs.

    Twigs reuse the main branch bark material so they visually blend
    with the trunk.  ``LSystemTree_Bark_MAT`` is created on demand by
    ``maya_mesh._get_bark_shading_group`` when the tree mesh is built;
    if the foliage is generated standalone (no tree mesh), we recreate
    the same material here so the twigs are not unshaded.
    """
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


def build_leaf_mesh_groups(foliage_model):
    """Return one mesh-array group per seasonal leaf color.

    Each leaf is built as a cylindrical petiole (tapered 5-segment prism)
    plus a curved blade subdivided along the midrib.  The petiole base is
    ``leaf.position`` (the contact point on the branch bark) and the
    blade starts at ``position + forward * petiole_length``.

    When ``leaf.species`` names a woody leaf spec (peach/cherry/pear/
    plum), the blade silhouette is shaped after the botanical leaf form
    (lanceolate/ovate/elliptic) and a central midrib is emitted as a
    raised ridge for vein detail.  Species=None preserves the legacy
    generic blade.
    """
    groups = {}
    world_down = (0.0, -1.0, 0.0)
    for leaf in foliage_model.leaves:
        points, counts, connects = groups.setdefault(leaf.color_index, ([], [], []))
        forward, side, normal = _orientation(leaf.direction, leaf.azimuth)
        petiole = float(getattr(leaf, "petiole_length", 0.0))
        contact = leaf.position
        blade_origin = _add(contact, _mul(forward, petiole))
        # Gravity droop: progressive downward bend increasing quadratically
        # from petiole to tip.  Upper-canopy leaves have low droop_factor
        # (nearly flat), lower-canopy leaves droop more heavily.
        droop = float(getattr(leaf, "droop_factor", 0.0))

        spec = WOODY_LEAF_SPECS.get(leaf.species) if leaf.species else None

        # --- Petiole: tapered 5-sided cylinder for a real stem silhouette.
        # Woody species get a hexagonal stem; the legacy generic leaf keeps
        # the original flat-triangle petiole so existing scenes are bit-for-
        # bit identical when no species is selected.
        if spec is not None and petiole > 1.0e-6:
            _emit_cylinder(
                points, counts, connects,
                start=contact, axis=forward, side=side, normal=normal,
                length=petiole, radius=leaf.width * 0.10,
                segments=5, rings=2,
            )
        else:
            base_index = len(points)
            petiole_tip_left = _add(blade_origin, _mul(side, leaf.width * 0.15))
            petiole_tip_right = _add(blade_origin, _mul(side, -leaf.width * 0.15))
            points.extend((contact, petiole_tip_left, petiole_tip_right))
            counts.append(3)
            connects.extend((base_index, base_index + 1, base_index + 2))

        # --- Blade: subdivided along the midrib into N stations.
        # Each station has a left/right edge vertex and a midrib vertex.
        # Curving the midrib vertices along +normal gives the blade a
        # gentle upward arc (cup shape), and offsetting edge vertices by
        # a small -normal curl models the drooping leaf margin.
        #
        # Botanical features (Flora of China):
        # - Leaf margin serration (serrate/double_serrate/aristate) emits
        #   zig-zag edge vertices for sawtooth silhouettes.
        # - Apex type (acuminate/caudate) extends the tip into a sharp
        #   taper; 'caudate' (cherry/plum "caudate tip") is longest.
        # - Base type (wedge/round) controls the base width transition.
        if spec is not None:
            if spec.blade_shape == "lanceolate":
                widest_frac = 0.28
            elif spec.blade_shape == "elliptic":
                widest_frac = 0.45
            else:  # ovate
                widest_frac = 0.34
            # Tip extension by apex type: caudate (caudate tip) is longest,
            # acuminate (acuminate tip) moderate, acute (acute tip) shortest.
            if spec.apex_type == "caudate":
                tip_extend = 0.08 + 0.06 * spec.tip_acuity
            elif spec.apex_type == "acuminate":
                tip_extend = 0.04 + 0.06 * spec.tip_acuity
            else:  # acute
                tip_extend = 0.02 + 0.04 * spec.tip_acuity
            stations = 5  # more stations for smoother serration curves
            arc_height = leaf.length * 0.10  # cup along midrib
            # Per-leaf margin curl variation: some leaves curl more, some less.
            curl_var = float(getattr(leaf, "curl_variation", 1.0))
            margin_curl = leaf.length * 0.04 * curl_var  # edge droop
            # Per-leaf asymmetric lateral bend along midrib.
            blade_curve = float(getattr(leaf, "blade_curve", 0.0))
            # Tip fold: ~15% of leaves have the tip station deflected.
            tip_fold = float(getattr(leaf, "tip_fold", 0.0))
            # Insect damage: collapse edge vertices at 1-2 stations.
            has_damage = bool(getattr(leaf, "has_damage", False))
            # Damage stations: pick 1-2 interior stations (not base/tip).
            damage_stations = set()
            if has_damage:
                # Deterministic from blade_curve sign and curl_var.
                ds = 1 + int(abs(blade_curve) * 3.0) % (stations - 1)
                damage_stations.add(ds)
                if curl_var > 1.2:
                    damage_stations.add(min(ds + 1, stations - 1))
            # Serration: emit zig-zag edge vertices.  ``margin_depth``
            # controls tooth amplitude, count scales with stations.
            serration_depth = leaf.width * spec.margin_depth
            serration_count = stations  # one tooth per station
            # Base taper: wedge base narrows faster than round base.
            base_taper = 0.55 if spec.base_type == "wedge" else 0.85
            # Generate the midrib + edge vertices station by station.
            station_mid = []
            station_left = []
            station_right = []
            for s in range(stations + 1):
                t = float(s) / stations
                # Edge width follows the botanical silhouette: 0 at base,
                # peaks at widest_frac, tapers back to 0 at tip.
                if t < widest_frac:
                    w = (t / widest_frac) if widest_frac > 1.0e-6 else 0.0
                    # Apply base taper so wedge bases narrow faster.
                    if t < 0.2:
                        w *= base_taper + (1.0 - base_taper) * (t / 0.2)
                else:
                    w = (1.0 - t) / (1.0 - widest_frac) if t < 1.0 else 0.0
                half_width = leaf.width * 0.5 * max(0.0, min(1.0, w * 1.05))
                # Serration: zig-zag the edge in/out perpendicular to
                # the midrib.  Skip the base (t=0) and tip (t=1) so the
                # sawtooth only appears along the margin.
                if (spec.margin_type != "entire" and 0 < s < stations
                        and serration_depth > 1.0e-6):
                    # Alternating in/out creates the sawtooth.  For
                    # double_serrate, add a secondary smaller tooth.
                    tooth_phase = 1.0 if s % 2 == 0 else -1.0
                    half_width += tooth_phase * serration_depth * 0.5
                    if spec.margin_type == "double_serrate":
                        half_width += 0.3 * tooth_phase * serration_depth
                    elif spec.margin_type == "aristate":
                        # Aristate (aristate margin): teeth are finer and sharper.
                        half_width += 0.2 * tooth_phase * serration_depth
                # Lengthwise position with optional tip extension.
                fwd_pos = leaf.length * (-0.12 + t * (1.0 + tip_extend))
                # Cup-shaped arc along midrib, peaking at mid-leaf.
                arc = arc_height * math.sin(math.pi * t)
                # Gravity droop: quadratic increase toward the tip.
                gravity_offset = droop * leaf.length * 0.35 * t * t
                # Asymmetric lateral bend: increases quadratically toward tip.
                lateral_offset = blade_curve * leaf.width * 0.25 * t * t
                # Tip fold: deflect the last station(s) downward+forward.
                fold_offset = 0.0
                if tip_fold > 0.0 and t > 0.75:
                    fold_t = (t - 0.75) / 0.25
                    fold_offset = tip_fold * leaf.length * 0.18 * fold_t * fold_t
                station_center = _add(
                    _add(
                        _add(blade_origin, _mul(forward, fwd_pos)),
                        _mul(world_down, gravity_offset + fold_offset),
                    ),
                    _mul(side, lateral_offset),
                )
                station_mid.append(_add(station_center, _mul(normal, arc)))
                edge_arc = arc - margin_curl
                # Insect damage: collapse edge width at damaged stations.
                hw_left = half_width
                hw_right = half_width
                if s in damage_stations:
                    hw_left *= 0.30  # bite taken out of left margin
                if s in damage_stations and len(damage_stations) > 1:
                    hw_right *= 0.45  # smaller bite on right
                station_left.append(_add(
                    _add(station_center, _mul(normal, edge_arc)),
                    _mul(side, hw_left),
                ))
                station_right.append(_add(
                    _add(station_center, _mul(normal, edge_arc)),
                    _mul(side, -hw_right),
                ))
            blade_start = len(points)
            for mid, left, right in zip(station_mid, station_left, station_right):
                points.extend((left, mid, right))
            # Subdivided blade: connect adjacent stations with a strip of
            # quads (each split into 2 triangles) along left & right sides.
            # Midrib ridge: the mid vertices are raised above the edge
            # vertices by ``arc - edge_arc`` and form a visible vein.
            for s in range(stations):
                l0 = blade_start + s * 3
                m0 = l0 + 1
                r0 = l0 + 2
                l1 = blade_start + (s + 1) * 3
                m1 = l1 + 1
                r1 = l1 + 2
                # Left half quad (left0, mid0, mid1, left1).
                counts.extend((3, 3))
                connects.extend((l0, m0, m1))
                connects.extend((l0, m1, l1))
                # Right half quad (mid0, right0, right1, mid1).
                counts.extend((3, 3))
                connects.extend((m0, r0, r1))
                connects.extend((m0, r1, m1))
        else:
            # Generic leaf: upgraded to a 4-station subdivided blade for
            # a smoother, more natural silhouette (was 5 verts / 4 faces).
            # Uses a simple elliptic width profile with gentle arc + droop.
            gen_stations = 4
            gen_widest = 0.38  # widest point along length
            gen_arc = leaf.length * 0.08
            gen_curl = leaf.length * 0.03 * float(getattr(leaf, "curl_variation", 1.0))
            blade_start = len(points)
            for s in range(gen_stations + 1):
                t = float(s) / gen_stations
                # Elliptic width profile: 0 at base, peak at gen_widest, 0 at tip.
                if t < gen_widest:
                    w = t / gen_widest
                else:
                    w = (1.0 - t) / (1.0 - gen_widest) if t < 1.0 else 0.0
                half_w = leaf.width * 0.5 * max(0.0, min(1.0, w))
                fwd_pos = leaf.length * (-0.10 + t * 1.0)
                arc = gen_arc * math.sin(math.pi * t)
                gravity_offset = droop * leaf.length * 0.35 * t * t
                # Slight asymmetric curve per leaf.
                lateral = float(getattr(leaf, "blade_curve", 0.0)) * leaf.width * 0.15 * t * t
                center = _add(
                    _add(
                        _add(blade_origin, _mul(forward, fwd_pos)),
                        _mul(world_down, gravity_offset),
                    ),
                    _mul(side, lateral),
                )
                mid_pt = _add(center, _mul(normal, arc))
                edge_arc = arc - gen_curl
                left_pt = _add(_add(center, _mul(normal, edge_arc)), _mul(side, half_w))
                right_pt = _add(_add(center, _mul(normal, edge_arc)), _mul(side, -half_w))
                points.extend((left_pt, mid_pt, right_pt))
            # Connect stations with triangle strips (same as species path).
            for s in range(gen_stations):
                l0 = blade_start + s * 3
                m0 = l0 + 1
                r0 = l0 + 2
                l1 = blade_start + (s + 1) * 3
                m1 = l1 + 1
                r1 = l1 + 2
                counts.extend((3, 3))
                connects.extend((l0, m0, m1))
                connects.extend((l0, m1, l1))
                counts.extend((3, 3))
                connects.extend((m0, r0, r1))
                connects.extend((m0, r1, m1))
    return groups


def _petal_width_profile(t, shape, claw, notch=0.0):
    """Petal half-width at normalized position t (0=base, 1=tip).

    Botanical shape profiles (Flora of China):
    - 'round' (pear  -  "subrounded"): widest at middle, symmetric.
    - 'obovate' (cherry/plum  -  "obovate"): widest above middle.
    - 'wide_oval' (peach  -  "long-elliptic"): widest near middle, slightly
      broader than round.

    The basal claw (Rosaceae "clawed at base") narrows the petal base where it
    meets the receptacle  -  modeled by scaling width down by (1-claw) for
    the first ~20% of the petal length.

    ``notch`` (2026-07): does NOT affect the width profile.  The V-cleft
    is produced by retracting the tip's mid/upper vertices toward the
    base in ``_emit_subdivided_petal``; the width profile only controls
    the lateral silhouette.  Earlier code scaled ``eval_t`` by
    ``(1.0 - notch)`` which inverted the notch effect  -  deeper notch
    produced WIDER tip (the opposite of botanical reality).
    """
    if shape == "round":
        # Symmetric ellipse centered at t=0.5.  Width follows the true
        # ellipse equation w = b*sqrt(1 - ((t-c)/a)^2) with c=0.5,
        # a=0.5, b=1.0.  This is the mathematically correct ellipse
        # profile  -  rises gently from the base (w=0.6 at t=0.1,
        # vs 0.36 for the parabola 4t(1-t)) and has zero derivative
        # at both endpoints, eliminating the "steep flare" artifact.
        w = 2.0 * math.sqrt(max(0.0, t * (1.0 - t)))
    elif shape == "obovate":
        # Asymmetric sin-based profile with peak above middle (t=0.60),
        # matching the botanical "obovate" (egg-shaped with broad apex).
        # Sin curve gives a smooth early rise from the base followed by
        # a gentle taper toward the tip  -  the derivative is zero at
        # t=0 and t=peak (ascending) and t=1 (descending), eliminating
        # the "sharp ridge" artifact of the previous piecewise approach
        # while rising faster early than the ellipse.
        peak = 0.60
        if t < peak:
            w = math.sin(0.5 * math.pi * t / peak) * 1.05
        else:
            w = math.sin(0.5 * math.pi * (1.0 - t) / (1.0 - peak)) * 1.05
    else:  # 'wide_oval'
        # Same symmetric ellipse as 'round' but slightly broader (b=1.08)
        # to model the peach petal's "wide oval" shape (Flora of China:
        # "petals broadly elliptic").  The true ellipse gives a much
        # smoother base transition than the previous parabola.
        w = 2.0 * math.sqrt(max(0.0, t * (1.0 - t))) * 1.08
    # Petal base transition (2026-07): all profile shapes collapse to w=0
    # at t=0 regardless of shape, so the claw parameter alone cannot
    # produce a non-degenerate root.  Earlier code applied TWO separate
    # mechanisms (blend for t<0.25, claw for t<0.2) whose effects stacked
    # then released at slightly different t  -  creating a "steep
    # concavity + abrupt flare" near t=0.2.
    #
    # Unified approach: a SINGLE smooth blend over t in [0, blend_end]
    # interpolates from a root floor (controlled by claw) to the natural
    # profile width.  Uses smoothstep (ease-in-out) so the derivative is
    # zero at both endpoints  -  this prevents the "spring release"
    # artifact where the width jumps suddenly as the blend ends.
    #
    # Monotonicity guard: when the natural profile width at small t is
    # LESS than base_floor (e.g. obovate at t=0.09 yields w=0.15 < 0.19
    # floor), linear interpolation would produce a DIP below base_floor.
    # We clamp the result to base_floor so width is monotonically
    # non-decreasing from the root.
    blend_end = 0.40
    if t < blend_end:
        linear = t / blend_end
        # Smoothstep: 3t^2 - 2t^3, zero derivative at t=0 and t=1.
        blend = linear * linear * (3.0 - 2.0 * linear)
        # Root floor: claw narrows the base.  claw=0 -> 0.22 floor,
        # claw=0.25 -> 0.22*(1-0.25*0.6) ~= 0.187.  Without the 0.6
        # damping, claw=0.25 would collapse the root to ~0.055 which
        # is too pinched for a real Rosaceae clawed base.
        base_floor = 0.22 * (1.0 - 0.6 * float(claw))
        blended = base_floor * (1.0 - blend) + w * blend
        # Monotonicity guard: never let the blended width drop below
        # the root floor.  Without this, obovate's slow rise near t=0
        # pulls the width below base_floor, creating a visible "dent"
        # at the petal base.
        w = max(blended, base_floor)
    # Tip anti-degeneracy: for round-tipped petals (notch < 0.05),
    # the tip cross-section naturally collapses to w=0, which produces
    # degenerate zero-area triangles.  Clamp to 3% to keep a tiny but
    # non-zero silhouette.
    if t > 0.92 and notch < 0.05:
        w = max(w, 0.03)
    # V-notch width floor (2026-07): for notched petals, the tip must
    # retain a non-zero width so the two edge vertices (which become
    # the V's prong tips) stay laterally separated.  Without this floor,
    # the profile collapses to w=0 at t=1.0 and the edge_l/edge_r verts
    # coincide on the centerline  -  the V-cleft becomes invisible
    # because there is no gap between the prongs.
    #
    # The floor scales with notch depth: deeper notch -> wider prong
    # gap (botanically accurate  -  cherry's deep V has a clearly open
    # cleft, peach's shallow notch has a barely-visible slit).
    if notch > 0.05 and t > 0.85:
        notch_floor = notch * 0.55
        # Smooth blend so the floor doesn't create a hard step at t=0.85
        floor_blend = (t - 0.85) / 0.15
        floor_blend = floor_blend * floor_blend * (3.0 - 2.0 * floor_blend)
        w = w * (1.0 - floor_blend) + max(w, notch_floor) * floor_blend
    return max(0.0, min(1.0, w))


def _emit_subdivided_petal(points, counts, connects,
                           petal_base, target, petal_side,
                           petal_length, petal_width, notch, shape, claw,
                           wave_periods_override=None, wave_amp_scale=1.0,
                           crease_station=-1, crease_depth=0.0,
                           tip_deflect=0.0):
    r"""Emit a rounded-edge, double-sided petal mesh using a 5-vertex cross-section loft.

    Each cross-section has 5 vertices arranged in an arc so the petal
    surface is domed (not flat) and the edges curl downward naturally,
    producing a rounded silhouette instead of a sharp paper-cutout edge:

        edge_l  upper_l  mid  upper_r  edge_r
           \      |      |      |      /
            \_____ _____|_____ _____/
                  cup arc (mid highest, edges lowest)

    The edge vertices are offset along ``-petal_normal`` (downward curl)
    so the margin rolls under slightly  -  a hallmark of real Rosaceae
    petals whose edges are never knife-sharp.

    Botanical features:
    - Species-specific width profile drives half-width at each station.
    - Cup-shaped arc along petal normal gives blade curvature.
    - Edge wave modulates ONLY the edge vertices (not the interior) so
      the margin ripples while the petal surface stays smooth.
    - Cherry V-notch splits the tip into two vertices with a cleft.
    - Basal claw narrows the base where it meets the receptacle.

    Per-petal naturalism parameters:
    - ``wave_periods_override``: vary the margin wave frequency per petal.
    - ``wave_amp_scale``: scale the margin wave amplitude per petal.
    - ``crease_station``: station index (1-8) where a longitudinal fold
      crease is applied (-1 = no crease).
    - ``crease_depth``: depth of the crease as fraction of arc height.
    - ``tip_deflect``: lateral deflection of the petal tip (asymmetric).

    9 stations x 5 vertices = 45 front verts + 45 back = 90 verts/petal.
    Double-sided thickness (~2% of length) with edge stitching + base
    cap closes the volume.
    """
    petal_normal = _normalize(_cross(target, petal_side))
    # Cup depth: mid vertex bows upward, edges curl downward.  18% of
    # length for the mid arc; edge curl is 40% of that (downward).
    arc = petal_length * 0.18
    edge_curl = arc * 0.40  # edges curl DOWN by this much relative to mid
    # Edge wave (margin undulation): sinusoidal modulation applied ONLY
    # to the edge vertices (edge_l, edge_r).  Interior vertices (upper_l,
    # mid, upper_r) are not modulated so the petal surface stays smooth
    # while the margin ripples.  Per-petal variation in frequency/amplitude.
    wave_periods = wave_periods_override if wave_periods_override is not None else 2.0
    wave_amp = petal_width * 0.10 * wave_amp_scale
    # Petal thickness (~2% of length).
    thickness = petal_length * 0.02

    # 9 stations = 10 cross-sections.  More stations give smoother
    # curvature along the cup and a cleaner tip taper.
    # When a V-notch is present (cherry), add extra stations near the
    # tip so polySmooth (Catmull-Clark, divisions=2) preserves the
    # notched silhouette instead of averaging it into a flat tip.
    # Without these support stations, the notch exists only at t=1.0
    # and has no close neighbour to anchor the subdivision.
    stations = 9
    if notch > 0.02:
        stations = 11
    front_start = len(points)

    # --- Generate STATIONS+1 cross-sections along the petal length.
    # Each cross-section has 5 vertices: (edge_l, upper_l, mid, upper_r, edge_r)
    #   - mid: centerline, highest (arc * sin(pi*t) along +normal)
    #   - upper_l/r: at +/-half_w*0.55, height = mid - 0.35*edge_curl
    #   - edge_l/r: at +/-half_w, height = mid - edge_curl (downward curl)
    # The edge wave modulates half_w for edge vertices only.
    sections = []  # list of (el, ul, mi, ur, er) index tuples
    for s in range(stations + 1):
        t = float(s) / stations
        w_raw = _petal_width_profile(t, shape, claw, notch)
        base_half_w = petal_width * 0.5 * w_raw * 1.15
        # Edge wave: cosine undulation modulated by a sin(π·t) envelope
        # so that the wave fades to zero at both t=0 (petal base) and
        # t=1 (petal tip).  Without the envelope, cos(0)=1.0 pushes
        # edge vertices outward at the root while interior vertices
        # stay on the center line (base_half_w=0)  -  producing a
        # "bowtie" pinch that visually narrows the petal base (2026-07).
        raw_wave = math.cos(2.0 * math.pi * wave_periods * t) * wave_amp
        wave = raw_wave * math.sin(math.pi * t)
        edge_half_w = base_half_w + wave
        upper_half_w = base_half_w * 0.55  # interior, no wave
        pos = _add(petal_base, _mul(target, petal_length * t))
        mid_height = arc * math.sin(math.pi * t)
        # Longitudinal crease: a sharp downward fold at one station,
        # creating a visible vein-like ridge.  Applied as a localized
        # dip in the mid vertex height at the crease station.
        if crease_station >= 0 and s == crease_station:
            mid_height -= arc * crease_depth
        # Tip deflection: the last station's mid vertex is offset
        # laterally so the petal tip curves asymmetrically.
        lateral_tip = 0.0
        if tip_deflect != 0.0 and t > 0.7:
            deflect_t = (t - 0.7) / 0.3
            lateral_tip = tip_deflect * petal_width * 0.3 * deflect_t
        # Spoon-shaped dish (spoon-shaped depression): mid stays at the cup arc height
        # while upper verts sit BELOW mid by edge_curl * 0.55.  This
        # forms a longitudinal groove along the petal centerline  - 
        # petals read as a spoon/dish instead of a flat plate.  Edge
        # verts curl further down (edge_curl * 1.4) to roll the margin
        # under, the hallmark of real Rosaceae petals whose edges are
        # never knife-sharp.
        upper_height = mid_height - edge_curl * 0.55
        edge_height = mid_height - edge_curl * 1.4
        mid = _add(_add(pos, _mul(petal_normal, mid_height)),
                   _mul(petal_side, lateral_tip))
        upper_l = _add(_add(pos, _mul(petal_normal, upper_height)),
                        _mul(petal_side, upper_half_w + lateral_tip * 0.5))
        upper_r = _add(_add(pos, _mul(petal_normal, upper_height)),
                        _mul(petal_side, -upper_half_w + lateral_tip * 0.5))
        edge_l = _add(_add(pos, _mul(petal_normal, edge_height)),
                       _mul(petal_side, edge_half_w + lateral_tip * 0.3))
        edge_r = _add(_add(pos, _mul(petal_normal, edge_height)),
                       _mul(petal_side, -edge_half_w + lateral_tip * 0.3))
        eli, uli, mi, uri, eri = (len(points), len(points) + 1, len(points) + 2,
                                    len(points) + 3, len(points) + 4)
        points.extend((edge_l, upper_l, mid, upper_r, edge_r))
        sections.append((eli, uli, mi, uri, eri))

    # Cherry V-notch: split the tip into TWO prongs by retracting only
    # the centerline vertices (mid + upper_l/r) toward the base, while
    # leaving edge_l/r at their original tip positions.  This produces
    # a true V-shaped cleft  -  the two edge vertices become the prong
    # tips, the mid vertex becomes the V base.
    #
    # Earlier code retracted ALL 5 tip vertices (including edges), which
    # just truncated the petal tip instead of splitting it.  From any
    # viewing angle the result looked like a flat cut, not a cleft.
    has_notch = notch > 0.0
    if has_notch:
        tip_section = sections[-1]
        tip_pos = _add(petal_base, _mul(target, petal_length))
        notch_depth = petal_length * notch
        # Retract ONLY the centerline verts: (edge_l, upper_l, mid, upper_r, edge_r)
        #   edge_l/r  -  stay at tip_pos (prong tips)
        #   upper_l/r  -  retract 40% (shallow V shoulders)
        #   mid        -  retract 100% (deepest, V base)
        # The two prong tips (edge_l, edge_r) stay separated laterally
        # by the tip cross-section's natural width, producing a visible
        # V-cleft between them.
        for idx_offset, pull_frac in [
            (1, 0.40),  # upper_l  -  shallow shoulder
            (2, 1.00),  # mid  -  deepest, forms the V base
            (3, 0.40),  # upper_r  -  shallow shoulder
        ]:
            idx = tip_section[idx_offset]
            points[idx] = _add(tip_pos, _mul(target, -notch_depth * pull_frac))

    # --- Front faces: 4 quads between consecutive 5-vertex cross-sections.
    # Quads: (edge_l, upper_l) x2, (upper_l, mid) x2, (mid, upper_r) x2,
    # (upper_r, edge_r) x2  -  each split into 2 triangles = 8 tris/segment.
    for s in range(stations):
        el0, ul0, m0, ur0, er0 = sections[s]
        el1, ul1, m1, ur1, er1 = sections[s + 1]
        # Quad 1: edge_l -> upper_l
        counts.extend((3, 3))
        connects.extend((el0, ul0, ul1))
        connects.extend((el0, ul1, el1))
        # Quad 2: upper_l -> mid
        counts.extend((3, 3))
        connects.extend((ul0, m0, m1))
        connects.extend((ul0, m1, ul1))
        # Quad 3: mid -> upper_r
        counts.extend((3, 3))
        connects.extend((m0, ur0, ur1))
        connects.extend((m0, ur1, m1))
        # Quad 4: upper_r -> edge_r
        counts.extend((3, 3))
        connects.extend((ur0, er0, er1))
        connects.extend((ur0, er1, ur1))

    front_count = len(points) - front_start

    # --- Back layer: duplicate front verts offset by -thickness.
    back_offset = _mul(petal_normal, -thickness)
    for i in range(front_start, front_start + front_count):
        points.append(_add(points[i], back_offset))

    def back_idx(front_index):
        return front_index + front_count

    # Back faces: same topology, reversed winding.
    for s in range(stations):
        el0, ul0, m0, ur0, er0 = sections[s]
        el1, ul1, m1, ur1, er1 = sections[s + 1]
        bel0, bul0, bm0, bur0, ber0 = (back_idx(el0), back_idx(ul0), back_idx(m0),
                                         back_idx(ur0), back_idx(er0))
        bel1, bul1, bm1, bur1, ber1 = (back_idx(el1), back_idx(ul1), back_idx(m1),
                                         back_idx(ur1), back_idx(er1))
        counts.extend((3, 3))
        connects.extend((bel0, bul1, bul0))
        connects.extend((bel0, bel1, bul1))
        counts.extend((3, 3))
        connects.extend((bul0, bm1, bm0))
        connects.extend((bul0, bul1, bm1))
        counts.extend((3, 3))
        connects.extend((bm0, bur1, bur0))
        connects.extend((bm0, bm1, bur1))
        counts.extend((3, 3))
        connects.extend((bur0, ber1, ber0))
        connects.extend((bur0, bur1, ber1))

    # --- Edge stitching: connect front & back edge chains (left edge
    # and right edge) so the petal is a closed volume.
    front_left_chain = [s[0] for s in sections]   # edge_l chain
    front_right_chain = [s[4] for s in sections]  # edge_r chain
    for chain in (front_left_chain, front_right_chain):
        for i in range(len(chain) - 1):
            f0 = chain[i]
            f1 = chain[i + 1]
            b0 = back_idx(f0)
            b1 = back_idx(f1)
            counts.extend((3, 3))
            connects.extend((f0, f1, b1))
            connects.extend((f0, b1, b0))

    # Base cap: close the base cross-section rim.
    base_section = sections[0]
    base_verts = list(base_section)  # 5 front verts
    base_back = [back_idx(v) for v in base_verts]
    # Triangulate the front base as a fan from mid, then stitch each
    # edge to its back counterpart.
    el_b, ul_b, m_b, ur_b, er_b = base_section
    # Front fan: mid connects to all 4 edge verts (2 tris for left, 2 for right).
    counts.extend((3, 3, 3, 3))
    connects.extend((m_b, ul_b, el_b))
    connects.extend((m_b, el_b, er_b))  # spans across via mid
    connects.extend((m_b, er_b, ur_b))
    connects.extend((m_b, ur_b, ul_b))
    # Back fan (reversed).
    bel_bb, bul_bb, bm_bb, bur_bb, ber_bb = base_back
    counts.extend((3, 3, 3, 3))
    connects.extend((bm_bb, bel_bb, bul_bb))
    connects.extend((bm_bb, bul_bb, ber_bb))
    connects.extend((bm_bb, ber_bb, bur_bb))
    connects.extend((bm_bb, bur_bb, bel_bb))


def _emit_sepal(points, counts, connects, flower_origin, axis, side, normal,
                sepal_radius, sepal_length):
    """Emit a 5-sided reflexed calyx ring at the flower base.

    Each sepal is a curved quad strip (3 stations x 2 edge verts = 6
    verts / 4 faces) following an outward-then-backward arc, so the
    sepal reads as a small leaf-like flap hugging the receptacle and
    curving down toward the pedicel  -  NOT a flat stiff triangle
    poking sideways like a thorn.

    Rosaceae flowers have 5 sepals forming a valvate calyx tube; many
    Prunus species (cherry, plum) characteristically have reflexed
    sepals ("reflexed sepals") that angle away from the petal whorl.  The
    curve here is a quadratic blend: t=0 at receptacle rim, t=0.5 at
    the widest flare, t=1 reflexed back toward the pedicel.

    Written to a dedicated array so the calyx can receive a green
    material distinct from the yellow/orange flower center.
    """
    sepal_count = 5
    sepal_axis = _mul(axis, -1.0)  # backward toward pedicel
    # 3 stations along the sepal length: base (t=0), mid flare (t=0.5),
    # reflexed tip (t=1).  Each station has 2 verts (outer, inner) so
    # the sepal has real width along its length, not a 1D spike.
    stations = 3
    for i in range(sepal_count):
        angle = 2.0 * math.pi * i / sepal_count
        radial = _normalize(
            _add(_mul(side, math.cos(angle)), _mul(normal, math.sin(angle)))
        )
        # Per-station center curve.  Radial component grows then shrinks
        # (flare out, then reflex back); backward component grows
        # monotonically (gentle downward curl).  This produces the
        # natural calyx arc instead of a straight sideways spike.
        station_verts = []
        for s in range(stations + 1):
            t = float(s) / stations
            # Radial flare: peaks at t=0.5 (sin curve), so the sepal
            # bulges outward in the middle and tucks back at the tip.
            radial_factor = math.sin(math.pi * t) * 0.8 + 0.2
            # Backward reflex: grows as t^2 so the tip curls down more
            # than the base  -  botanically the sepal tip reflexes away
            # from the petal whorl while the base hugs the receptacle.
            back_factor = t * t
            radial_pos = sepal_radius + sepal_length * 0.35 * radial_factor
            back_pos = sepal_length * 0.55 * back_factor
            center = _add(
                _add(flower_origin, _mul(radial, radial_pos)),
                _mul(sepal_axis, back_pos),
            )
            # Sepal half-width: tapers from base to tip so the sepal is
            # a leaf-shaped flap, widest at base, narrowing at tip.
            half_w = sepal_radius * 0.45 * (1.0 - t * 0.7)
            outer = _add(center, _mul(radial, half_w))
            inner = _add(center, _mul(radial, -half_w))
            station_verts.append((outer, inner))
        # Emit quad strip between consecutive stations: each segment
        # is 1 quad (2 tris) connecting (outer_s, inner_s, inner_s+1,
        # outer_s+1).  3 segments = 6 verts / 6 tris... but we share
        # verts between segments, so total = 4 stations x 2 = 8 verts,
        # 3 segments x 2 tris = 6 faces.
        base_idx = len(points)
        for outer, inner in station_verts:
            points.extend((outer, inner))
        for s in range(stations):
            o0 = base_idx + s * 2
            i0 = o0 + 1
            o1 = base_idx + (s + 1) * 2
            i1 = o1 + 1
            counts.extend((3, 3))
            connects.extend((o0, i0, i1))
            connects.extend((o0, i1, o1))


def build_flower_mesh_groups(foliage_model):
    """Return petal meshes per color plus a shared flower-center mesh.

    Each flower is built as a pedicel (cylindrical tapered stem from the
    bark contact point) plus a flower head (petals + center).  The
    pedicel base is ``flower.position`` (the contact point on the branch
    bark) and the flower head starts at ``position + forward *
    peduncle_length``.

    When ``flower.species`` names a woody flower spec (peach/cherry/pear/
    plum), petals are emitted as subdivided curved surfaces with a
    parabolic width profile and longitudinal vein ridges, the pedicel
    becomes a 5-sided tapered cylinder, and the flower center gains a
    ring of stamens for botanical accuracy.  Cherry blossoms emit the
    signature V-notched petal tip.  Species=None preserves the legacy
    5-petal flat flower used by existing scenes and tests.

    Returns ``(petal_groups, center_arrays, sepal_arrays)``.  Sepals
    are emitted to a dedicated array so the calyx can receive a green
    material distinct from the yellow/orange flower center  -  botanically
    the calyx is a leaf-derived green structure regardless of petal
    color.  Generic (non-woody) flowers skip sepals, so ``sepal_arrays``
    stays empty for the legacy path.
    """
    petal_groups = {}
    center_points = []
    center_counts = []
    center_connects = []
    sepal_points = []
    sepal_counts = []
    sepal_connects = []
    world_down = (0.0, -1.0, 0.0)

    for flower in foliage_model.flowers:
        points, counts, connects = petal_groups.setdefault(
            flower.color_index,
            ([], [], []),
        )
        axis, side, normal = _orientation(flower.direction, flower.azimuth)
        peduncle = float(getattr(flower, "peduncle_length", 0.0))
        flower_origin = _add(flower.position, _mul(axis, peduncle))
        petal_length = flower.size * (1.0 - 0.25 * flower.wilt)

        spec = WOODY_FLOWER_SPECS.get(flower.species) if flower.species else None
        if spec is not None:
            petal_count = spec.petal_count
            petal_width = petal_length / spec.petal_ratio * (1.0 - 0.42 * flower.wilt)
            notch = spec.petal_notch
            petal_shape = spec.petal_shape
            petal_claw = spec.petal_claw
            detail = True
        else:
            petal_count = 5
            petal_width = flower.size * 0.44 * (1.0 - 0.42 * flower.wilt)
            notch = 0.0
            petal_shape = "round"
            petal_claw = 0.0
            detail = False

        # Pedicel: woody species get a real cylindrical stem whose length
        # follows the botanical pedicel_ratio.  The pedicel is emitted
        # into the sepal arrays below (not here) so it receives the green
        # calyx material instead of the petal color (2026-07).

        for petal_index in range(petal_count):
            radians = 2.0 * math.pi * petal_index / float(petal_count)
            radial = _normalize(
                _add(
                    _mul(side, math.cos(radians)),
                    _mul(normal, math.sin(radians)),
                )
            )
            target = _normalize(
                _add(
                    _add(
                        _mul(radial, flower.openness * 0.72),
                        _mul(axis, 0.45),
                    ),
                    _mul(world_down, flower.wilt * 1.05),
                )
            )
            petal_side = _cross(target, axis)
            if _dot(petal_side, petal_side) <= 1.0e-9:
                petal_side = side
            petal_side = _normalize(petal_side)
            # Petal base sits on the receptacle rim.  The radial offset
            # (0.22 * flower.size) matches the enlarged receptacle
            # radius (center_radius = 0.22) so 5 petals root on the rim
            # and spread outward+upward at ~35 deg tilt, reducing the
            # horizontal-plane overlap that occurs when petals lie flat.
            petal_base = _add(flower_origin, _mul(radial, flower.size * 0.22))

            if detail:
                # Per-petal naturalism variation derived deterministically
                # from petal_index so each petal in the flower differs slightly.
                _golden = 2.399963  # golden angle in radians
                _phase = petal_index * _golden
                _wave_per = 1.5 + 1.0 * abs(math.sin(_phase * 1.3))
                _wave_amp = 0.7 + 0.6 * abs(math.cos(_phase * 0.7))
                _crease_st = 2 + (petal_index * 3) % 6  # station 2-7
                _crease_dep = 0.25 + 0.20 * abs(math.sin(_phase * 2.1))
                _tip_def = 0.4 * math.sin(_phase * 1.7)  # -0.4..+0.4
                _emit_subdivided_petal(
                    points, counts, connects,
                    petal_base, target, petal_side,
                    petal_length, petal_width, notch,
                    petal_shape, petal_claw,
                    wave_periods_override=_wave_per,
                    wave_amp_scale=_wave_amp,
                    crease_station=_crease_st,
                    crease_depth=_crease_dep,
                    tip_deflect=_tip_def,
                )
            else:
                # Legacy 4-vert / 2-face flat petal.
                base_index = len(points)
                petal_tip = _add(petal_base, _mul(target, petal_length))
                middle = _add(petal_base, _mul(target, petal_length * 0.48))
                left = _add(middle, _mul(petal_side, petal_width * 0.5))
                right = _add(middle, _mul(petal_side, -petal_width * 0.5))
                points.extend((petal_base, left, petal_tip, right))
                counts.extend((3, 3))
                connects.extend(
                    (
                        base_index, base_index + 1, base_index + 2,
                        base_index, base_index + 2, base_index + 3,
                    )
                )

        # Flower center (shared mesh across all flowers of this color).
        # Receptacle radius enlarged to 0.22 so 5 petals root on the rim
        # with enough circumferential spacing to avoid mid-blade overlap.
        center_base = len(center_points)
        center_radius = flower.size * 0.22
        if spec is None:
            # Legacy pedicel triangle in the center mesh.
            pedicel_tip_left = _add(flower_origin, _mul(side, flower.size * 0.08))
            pedicel_tip_right = _add(flower_origin, _mul(side, -flower.size * 0.08))
            center_points.extend(
                (flower.position, pedicel_tip_left, pedicel_tip_right)
            )
            center_counts.append(3)
            center_connects.extend(
                (center_base, center_base + 1, center_base + 2)
            )
            center_oct_base = center_base + 3
        else:
            center_oct_base = center_base
            # Pedicel (2026-07): emitted into sepal arrays so the stem
            # renders with the green calyx material instead of the petal
            # color.  Botanically, the pedicel is a vegetative structure
            # (same tissue as the calyx), not part of the petal whorl.
            if spec is not None and peduncle > 1.0e-6:
                pedicel_radius = flower.size * spec.pedicel_thickness
                _emit_cylinder(
                    sepal_points, sepal_counts, sepal_connects,
                    start=flower.position, axis=axis, side=side, normal=normal,
                    length=peduncle, radius=pedicel_radius,
                    segments=5, rings=2, taper=0.35,
                )
            # Calyx tube (萼筒, hypanthium): a short bell-shaped cylinder
            # that forms the visible base of the flower between the
            # pedicel and the receptacle.  In cherry and plum blossoms
            # the hypanthium is a prominent green cup; in peach it is
            # shorter and hairy; in pear it tapers smoothly.  Emitted
            # to the sepal arrays so it renders with the green calyx
            # material (2026-07).
            #
            # The tube extends from flower_origin backward along -axis
            # (toward the pedicel), with end_radius smaller than
            # start_radius to create the bell shape.
            calyx_length = flower.size * 0.10
            calyx_start_radius = flower.size * 0.12
            calyx_end_radius = flower.size * 0.06
            _emit_cylinder(
                sepal_points, sepal_counts, sepal_connects,
                start=flower_origin,
                axis=_mul(axis, -1.0),  # backward toward pedicel
                side=side, normal=normal,
                length=calyx_length,
                radius=calyx_start_radius,
                segments=6, rings=1,
            )
            # Manually taper the far end by moving the last ring of
            # vertices inward.  _emit_cylinder only supports linear
            # taper through its `taper` parameter (end_radius =
            # radius * taper), but we want a bell curve: wider at
            # petal end, narrower at pedicel end.  Since we can't
            # set taper < 1.0 to widen the end, we emit with
            # start_radius and then scale the far ring.
            # _emit_cylinder(segments=6, rings=1) emits 2 rings of 6
            # verts + 1 cap center = 13 verts.  Ring 0 is at the
            # start (flower_origin), ring 1 is at the far end.
            # Indices: ring 0 = [base+0..base+5], ring 1 = [base+6..base+11].
            cylinder_base = len(sepal_points) - 13
            if cylinder_base >= 0:
                far_ring_center = _add(flower_origin, _mul(_mul(axis, -1.0), calyx_length))
                for ri in range(6):
                    fi = cylinder_base + 6 + ri  # far ring vertex index
                    if fi < len(sepal_points):
                        direction = _sub(sepal_points[fi], far_ring_center)
                        sepal_points[fi] = _add(
                            far_ring_center,
                            _mul(_normalize(direction), calyx_end_radius),
                        )
            # Sepals: 5 reflexed calyx quads at the flower base, written
            # to a dedicated sepal array so they can receive a green
            # material distinct from the yellow/orange flower center.
            # sepal_radius reduced to 0.14 (was 0.26)  -  the calyx is a
            # small green flap at the blossom base, not a prominent petal-
            # sized structure (2026-07).
            _emit_sepal(
                sepal_points, sepal_counts, sepal_connects,
                flower_origin, axis, side, normal,
                sepal_radius=flower.size * 0.14,
                sepal_length=flower.size * 0.14,
            )
        # Flattened octahedral floral disc (receptacle).
        # The axis-direction poles are compressed to 40% so the
        # receptacle reads as a disc/dome rather than a sphere  - 
        # botanically the receptacle is a flattened structure.
        _emit_octahedron(
            center_points, center_counts, center_connects,
            center=flower_origin, axis=axis, side=side, normal=normal,
            radius=center_radius, axis_scale=0.4,
        )

        # Stamens: woody species get a ring of two-segment stamen
        # columns around the receptacle.  Each stamen is split into a
        # thin filament (the stalk) + a thicker tapered anther cap (the
        # pollen-bearing head)  -  botanically accurate ("filament" + "anther")
        # and gives each stamen a visible head silhouette instead of a
        # uniform toothpick.  Stamen count follows the botanical spec
        # (peach ~30, pear 20-30, plum/cherry "numerous"); we render a
        # representative subset for performance.
        if spec is not None:
            stamen_count = spec.stamen_count
            stamen_length = flower.size * 0.22
            stamen_radius = flower.size * 0.018
            # Filament occupies the lower 70% of the stamen, anther the
            # upper 30%.  Anther is ~2x thicker than the filament and
            # tapers to a rounded tip so it reads as a pollen head.
            filament_length = stamen_length * 0.70
            anther_length = stamen_length * 0.30
            anther_radius = stamen_radius * 4.0
            # Deterministic per-stamen variation (2026-07): each stamen
            # receives a small angle jitter, length scale, and tilt
            # variation so the ring reads as organic rather than
            # mechanically regular.  Derived from the stamen index via
            # sinusoidal hashing  -  no RNG needed.
            _golden = 2.399963  # golden angle in radians
            for stamen_index in range(stamen_count):
                _seed = stamen_index * _golden
                # Angle jitter: ±0.12 rad (~±7°) displacement from the
                # uniform angular position.
                _angle_jitter = 0.12 * math.sin(_seed * 3.7)
                # Length scale: 0.85-1.15x variation so stamens are not
                # all the same height.
                _len_scale = 0.85 + 0.30 * abs(math.cos(_seed * 2.1))
                # Tilt variation: blend factor between axis-aligned and
                # radial so each stamen tilts slightly more erect or
                # more spread out.  0.52-0.68 range.
                _tilt_jitter = 0.08 * math.sin(_seed * 5.3)
                angle = 2.0 * math.pi * stamen_index / stamen_count + _angle_jitter
                radial_dir = _normalize(
                    _add(_mul(side, math.cos(angle)), _mul(normal, math.sin(angle)))
                )
                stamen_start = _add(
                    flower_origin, _mul(radial_dir, center_radius * 0.7)
                )
                # Tilt the stamen by varying the axis/radial blend ratio.
                _axis_blend = 0.6 + _tilt_jitter
                stamen_axis = _normalize(
                    _add(_mul(axis, _axis_blend), _mul(radial_dir, 0.4))
                )
                stamen_side = _normalize(_cross(stamen_axis, radial_dir))
                if _dot(stamen_side, stamen_side) <= 1.0e-9:
                    stamen_side = side
                stamen_normal = _normalize(_cross(stamen_axis, stamen_side))
                # Apply per-stamen length variation to both filament
                # and anther so the stamen scales proportionally.
                _fil_len = filament_length * _len_scale
                _ant_len = anther_length * _len_scale
                # Filament: thin stalk from receptacle to anther base.
                # segments=8 (octagonal cross-section) reads as round
                # in the viewport  -  segments=4 produced a square-prism
                # filament that looked like a flat diamond under view.
                _emit_cylinder(
                    center_points, center_counts, center_connects,
                    start=stamen_start, axis=stamen_axis,
                    side=stamen_side, normal=stamen_normal,
                    length=_fil_len, radius=stamen_radius,
                    segments=8, rings=1,
                )
                # Anther: thicker tapered cap sitting on the filament
                # tip  -  the pollen head.  segments=8 + taper=0.3 makes
                # the anther read as a rounded lobed head instead of
                # the previous diamond pyramid (segments=4, taper=0.5
                # produced a flat square pyramid).  taper=0.3 keeps
                # more volume at the tip so the anther is egg-shaped,
                # botanically closer to a real pollen sac.
                anther_start = _add(
                    stamen_start, _mul(stamen_axis, _fil_len)
                )
                _emit_cylinder(
                    center_points, center_counts, center_connects,
                    start=anther_start, axis=stamen_axis,
                    side=stamen_side, normal=stamen_normal,
                    length=_ant_len, radius=anther_radius,
                    segments=8, rings=1, taper=0.3,
                )

            # Pistil (pistil): the central female reproductive organ,
            # sitting at the flower center and rising slightly above the
            # stamens so the stigma can receive pollen.  Composed of
            # three parts (Flora of China, eflora):
            #   - Ovary (ovary): enlarged base housing the ovules  -  a
            #     small octahedron at the receptacle center.
            #   - Style (style): slender stalk elevating the stigma  -  a
            #     thin cylinder rising from the ovary top.
            #   - Stigma (stigma): pollen-receiving head  -  a small rounded
            #     octahedron at the style tip, slightly swollen.
            ovary_radius = flower.size * 0.05
            ovary_center = _add(flower_origin, _mul(axis, ovary_radius * 0.3))
            # Ovary: octahedron (8 tris).
            _emit_octahedron(
                center_points, center_counts, center_connects,
                center=ovary_center, axis=axis, side=side, normal=normal,
                radius=ovary_radius,
            )
            # Style: thin cylinder rising from ovary top.
            style_length = flower.size * 0.18
            style_radius = flower.size * 0.012
            style_start = _add(ovary_center, _mul(axis, ovary_radius))
            _emit_cylinder(
                center_points, center_counts, center_connects,
                start=style_start, axis=axis, side=side, normal=normal,
                length=style_length, radius=style_radius,
                segments=4, rings=1,
            )
            # Stigma: small swollen octahedron at the style tip.
            stigma_radius = flower.size * 0.035
            stigma_center = _add(style_start, _mul(axis, style_length))
            _emit_octahedron(
                center_points, center_counts, center_connects,
                center=stigma_center, axis=axis, side=side, normal=normal,
                radius=stigma_radius,
            )

    return (
        petal_groups,
        (center_points, center_counts, center_connects),
        (sepal_points, sepal_counts, sepal_connects),
    )


def build_asset_mesh_groups(foliage_model, kind):
    """Build combined arrays from the licensed OBJ organ catalog.

    Only instances whose ``asset_id`` is set are processed.  Instances
    without an asset_id are left for the procedural fallback so they are
    never silently dropped.

    The OBJ geometry is offset from the bark contact point
    (``instance.position``) by the petiole/peduncle length along the
    instance's forward direction, so the organ blade/head starts at the
    end of the stem just like the procedural meshes.
    """
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
        stem_length = float(
            getattr(instance, "petiole_length", 0.0)
            if kind == "leaf"
            else getattr(instance, "peduncle_length", 0.0)
        )
        origin = _add(instance.position, _mul(forward, stem_length))
        base_index = len(points)
        for x_value, y_value, z_value in mesh.vertices:
            point = _add(
                origin,
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


def _procedural_leaf_groups_for_orphans(foliage_model):
    """Procedural leaf meshes for instances that have no OBJ asset_id."""
    orphan_model = _PrototypeFoliageModel(
        foliage_model.profile,
        leaves=[leaf for leaf in foliage_model.leaves if not leaf.asset_id],
    )
    if not orphan_model.leaves:
        return {}
    return build_leaf_mesh_groups(orphan_model)


def _procedural_flower_groups_for_orphans(foliage_model):
    """Procedural flower meshes for instances that have no OBJ asset_id."""
    orphan_model = _PrototypeFoliageModel(
        foliage_model.profile,
        flowers=[f for f in foliage_model.flowers if not f.asset_id],
    )
    if not orphan_model.flowers:
        return {}, ([], [], []), ([], [], [])
    petal_groups, center_arrays, sepal_arrays = build_flower_mesh_groups(orphan_model)
    return petal_groups, center_arrays, sepal_arrays


def _material(cmds, name, color, translucent=False):
    """Lambert material for foliage/flowers.

    ``translucent=True`` raises transparency from 0.02 (depth-sort
    hack) to 0.18 and adds ambientColor  -  together they simulate the
    subsurface-scattering look of real petals (light shining through
    the thin blade produces a soft pink-white edge glow).  Full SSS
    (misss_fast_simple_x) is heavier and only shows in renders; this
    lambert-based approach is visible in the viewport immediately.
    """
    if not cmds.objExists(name):
        name = cmds.shadingNode("lambert", asShader=True, name=name)
        cmds.setAttr(name + ".color", color[0], color[1], color[2], type="double3")
        cmds.setAttr(name + ".diffuse", 0.88)
        if translucent:
            # Petal SSS approximation: 18% transparency lets back-light
            # bleed through the blade; a warm ambient brightens the
            # silhouette so the petal edge reads as glowing-pink instead
            # of opaque plastic.  Values tuned for viewport visibility.
            cmds.setAttr(name + ".transparency", 0.18, 0.18, 0.18, type="double3")
            ambient = tuple(min(1.0, c + 0.18) for c in color)
            cmds.setAttr(name + ".ambientColor",
                         ambient[0], ambient[1], ambient[2], type="double3")
        else:
            # Tiny transparency triggers Maya's transparency sort, which
            # renders foliage AFTER opaque branches.  Combined with
            # polygonOffset on the mesh shape, this makes leaves/flowers
            # always win the depth test against branches they penetrate -
            # the standard game-engine trick for foliage-on-bark clipping.
            cmds.setAttr(name + ".transparency", 0.02, 0.02, 0.02, type="double3")
    else:
        # Lambert already exists (leftover from an incomplete cleanup).
        # Update its color ONLY when the ``.color`` plug is NOT already
        # driven by a condition node (two-sided leaf setup).  If it IS
        # connected, ``_material_two_sided_leaf`` will update the
        # condition node's colorIfTrue/colorIfFalse instead.
        color_source = cmds.listConnections(
            name + ".color", source=True, destination=False
        )
        if not color_source:
            try:
                cmds.setAttr(
                    name + ".color", color[0], color[1], color[2], type="double3"
                )
            except RuntimeError:
                pass
    # shading_group must be computed AFTER the ``if`` block above because
    # ``cmds.shadingNode`` may return a different name (Maya auto-renames
    # on conflict).  Previously ``shading_group = name + "SG"`` was set
    # BEFORE the rename, causing the SG name to mismatch the lambert.
    shading_group = name + "SG"
    if not cmds.objExists(shading_group):
        shading_group = cmds.sets(
            renderable=True,
            noSurfaceShader=True,
            empty=True,
            name=shading_group,
        )
        # Force this shading group to render after opaque geometry so
        # foliage depth bias takes effect against branch meshes.
        if cmds.attributeQuery("compMode", node=shading_group, exists=True):
            cmds.setAttr(shading_group + ".compMode", 1)
    # Always connect the lambert to the shading group, even when the SG
    # already exists from a previous (incompletely cleaned) tree.  If
    # the old SG stayed behind because ``delete_last`` / scene cleanup
    # did not remove it, the new lambert would be orphaned and the mesh
    # would render with the default gray lambert ("no color").
    cmds.connectAttr(
        name + ".outColor",
        shading_group + ".surfaceShader",
        force=True,
    )
    return shading_group


def _material_two_sided_leaf(cmds, name, front_color, back_color=None):
    """Lambert material with distinct front/back colors for leaves.

    Real leaves are darker and glossier on the adaxial (upper) surface
    and lighter/matte on the abaxial (lower) surface.  This is achieved
    with a Maya ``condition`` node that switches the lambert color based
    on the face normal direction (flipped normals = back face).

    Falls back to plain ``_material`` if the condition network cannot
    be created (e.g. missing node type on older Maya versions).
    """
    if back_color is None:
        # Default back color: 30% lighter toward yellow-green.
        back_color = tuple(
            min(1.0, c * 0.7 + 0.25) for c in front_color
        )
    shading_group = _material(cmds, name, front_color)
    condition_name = name + "_FaceSwitch"
    sampler_name = name + "_Sampler"
    # Create the condition node and samplerInfo only once, but always
    # re-connect the condition to the lambert and update the colors.
    # If the condition node survived from a previous build but the
    # lambert was deleted and recreated (because ``delete_foliage_nodes``
    # removed the lambert but not the locked condition node), the old
    # condition-to-lambert connection is dangling.  Without re-connecting,
    # the new lambert renders with its default ``setAttr`` color (which
    # may be stale from a different season) or the condition node's
    # default black - the user sees "no color".
    if not cmds.objExists(condition_name):
        try:
            condition = cmds.shadingNode(
                "condition", asUtility=True, name=condition_name
            )
            sampler = cmds.shadingNode(
                "samplerInfo", asUtility=True, name=sampler_name
            )
            cmds.connectAttr(
                sampler + ".flippedNormal", condition + ".firstTerm", force=True
            )
            cmds.setAttr(condition + ".secondTerm", 0.5)
            cmds.setAttr(condition + ".operation", 2)  # Greater than
        except Exception:
            return shading_group
    # Always re-connect the condition output to the lambert color.
    # This is safe even when the connection already exists (force=True
    # is a no-op on an identical connection) and essential when the
    # lambert was recreated but the condition node survived.
    if cmds.objExists(condition_name):
        # Check whether the samplerInfo still exists.  If a previous
        # cleanup deleted the sampler but left the condition behind,
        # ``firstTerm`` is dangling and the condition outputs default
        # black  -  the user sees "no color".  Recreate the sampler in
        # that case so the two-sided shading actually works.
        if not cmds.objExists(sampler_name):
            try:
                sampler = cmds.shadingNode(
                    "samplerInfo", asUtility=True, name=sampler_name
                )
                cmds.connectAttr(
                    sampler + ".flippedNormal",
                    condition_name + ".firstTerm",
                    force=True,
                )
            except Exception:
                pass
        try:
            shaders = cmds.listConnections(
                shading_group + ".surfaceShader", source=True
            ) or []
            if shaders:
                cmds.connectAttr(
                    condition_name + ".outColor",
                    shaders[0] + ".color",
                    force=True,
                )
            cmds.setAttr(
                condition_name + ".colorIfTrue",
                back_color[0], back_color[1], back_color[2],
                type="double3",
            )
            cmds.setAttr(
                condition_name + ".colorIfFalse",
                front_color[0], front_color[1], front_color[2],
                type="double3",
            )
        except RuntimeError:
            # When a leftover wind expression triggers "parse error"
            # during DG evaluation, the ``setAttr`` for ``colorIfTrue``
            # / ``colorIfFalse`` raises RuntimeError and the condition
            # node stays at default black.  Nothing useful to log here
            # since the symptom (colorless render) is self-evident.
            pass
    return shading_group


def _create_vein_texture_file(cmds, kind, species=None):
    """Create a procedural vein texture file for leaves/flowers.

    Generates a small PNG with the leaf midrib, secondary veins and
    petal radiating veins using Python's built-in imaging library, then
    loads it as a Maya file texture.  Returns the file path or None if
    PIL is unavailable  -  the caller falls back to plain lambert in
    that case.

    The texture is designed as a tileable UV pattern: the midrib runs
    vertically along U=0.5, secondary veins branch out at ~45 deg on a
    128x128 canvas.  For petals, the pattern is radial from the base.

    Cached: the PNG is only generated once per (kind, species) per
    project  -  subsequent calls reuse the existing file on disk.  This
    saves the PIL draw + file write overhead (~30-50ms) on every
    material creation after the first.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    import os
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "textures")
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
    suffix = "_{}".format(species) if species else ""
    tex_path = os.path.join(assets_dir, "{}_vein{}.png".format(kind, suffix))
    # Cache hit: reuse the existing PNG instead of regenerating it.
    # The vein pattern is deterministic for a given (kind, species),
    # so regeneration would produce identical bytes.
    if os.path.exists(tex_path):
        return tex_path

    size = 128
    image = Image.new("L", (size, size), 255)  # white background
    draw = ImageDraw.Draw(image)

    if kind == "leaf":
        # Midrib: vertical line down the center (U=0.5, V=0..1).
        draw.line([(size // 2, 0), (size // 2, size)], fill=80, width=3)
        # Secondary veins: pairs of diagonal lines branching off the
        # midrib at ~45 deg, at 4 stations along the leaf length.
        for station in range(1, 5):
            y = int(size * station / 5.0)
            # Left vein
            draw.line(
                [(size // 2, y), (size // 8, y + size // 6)],
                fill=120, width=1,
            )
            # Right vein
            draw.line(
                [(size // 2, y), (size * 7 // 8, y + size // 6)],
                fill=120, width=1,
            )
        # Tertiary veins: finer mesh between secondary veins (only for
        # species with prominent venation like cherry/pear).
        if species in ("cherry", "pear"):
            for station in range(1, 8):
                y = int(size * station / 8.0)
                draw.line(
                    [(size // 4, y), (size // 2, y + size // 10)],
                    fill=160, width=1,
                )
                draw.line(
                    [(size // 2, y), (size * 3 // 4, y + size // 10)],
                    fill=160, width=1,
                )
    else:  # flower petal
        # Radial veins from base (bottom center) toward tip (top center).
        cx, cy = size // 2, size - 1
        for angle_deg in range(-30, 31, 10):
            angle = math.radians(angle_deg - 90)  # -90 = straight up
            x2 = int(cx + math.cos(angle) * size * 0.9)
            y2 = int(cy + math.sin(angle) * size * 0.9)
            draw.line([(cx, cy), (x2, y2)], fill=100, width=1)
        # Subtle petal edge darkening for depth.
        draw.rectangle([(0, 0), (size - 1, 4)], fill=200)
        draw.rectangle([(0, size - 5), (size - 1, size - 1)], fill=200)

    # Write the PNG (cache miss path only  -  early return above handles
    # cache hits).  Persisting to disk means subsequent runs in the
    # same project skip PIL entirely.
    image.save(tex_path)
    return tex_path


def _material_with_veins(cmds, name, color, kind=None, species=None,
                        two_sided=False):
    """Lambert material with an optional procedural vein bump map.

    For woody leaves/flowers, a small vein texture is generated and
    connected to the bump channel so the midrib and secondary veins
    catch light naturally.  Falls back to plain ``_material`` if the
    texture cannot be created (PIL missing).

    For flowers, the translucent variant is used so light bleeds
    through the thin blade  -  the SSS approximation that gives real
    blossoms their characteristic pink-white edge glow.

    ``two_sided=True`` builds a condition + samplerInfo network so the
    leaf shows distinct front/back colors (dark adaxial, light abaxial).
    The bump is connected to the lambert's normalCamera AFTER the
    condition is wired to ``.color``  -  order matters because both
    connections touch the lambert, and ``force=True`` on normalCamera
    must not sever the color connection.

    Parameters:
        cmds: Maya cmds module.
        name (str): Base name for the material and helper nodes.
        color (tuple): Front-face (adaxial) color.
        kind (str|None): "leaf" or "flower"  -  selects vein texture
            pattern.  None skips vein creation.
        species (str|None): Woody species key for species-specific vein
            patterns (cherry/peach/pear/plum).
        two_sided (bool): When True, build a two-sided condition network
            so front/back faces show different colors.  Used for woody
            leaves; petals use the translucent single-sided path.
    """
    # Petals use the translucent variant so light bleeds through the
    # thin blade  -  the SSS approximation that gives real blossoms
    # their characteristic pink-white edge glow.
    is_petal = kind == "flower"
    # Two-sided leaves use the condition network for front/back colors;
    # otherwise (petals) the lambert color is set directly.
    if two_sided:
        base_sg = _material_two_sided_leaf(cmds, name, color)
    else:
        base_sg = _material(cmds, name, color, translucent=is_petal)
    if kind is None:
        return base_sg

    tex_path = _create_vein_texture_file(cmds, kind, species)
    if tex_path is None:
        return base_sg

    # Create a file texture node and bump2d node only once per material.
    file_node_name = name + "VeinFile"
    bump_node_name = name + "VeinBump"
    if not cmds.objExists(file_node_name):
        file_node = cmds.shadingNode("file", asTexture=True, name=file_node_name)
        cmds.setAttr(file_node + ".fileTextureName", tex_path, type="string")
        # colorSpace defaults to sRGB  -  no need to set it explicitly.
        cmds.setAttr(file_node + ".filterType", 0)  # no filter, keep veins crisp
        # Maya's file node does not own wrap flags directly  -  they live
        # on the companion place2dTexture node that Maya auto-creates
        # (or we create it explicitly here) and connects.  Enable U/V
        # wrap so the vein texture tiles cleanly across leaf UVs.
        place_node = cmds.shadingNode(
            "place2dTexture", asUtility=True,
            name=file_node_name + "Place",
        )
        cmds.setAttr(place_node + ".wrapU", 1)
        cmds.setAttr(place_node + ".wrapV", 1)
        cmds.setAttr(place_node + ".repeatUV", 1, 1)
        cmds.connectAttr(place_node + ".outUV", file_node + ".uvCoord", force=True)
        cmds.connectAttr(place_node + ".outUvFilterSize", file_node + ".uvFilterSize", force=True)

        bump_node = cmds.shadingNode("bump2d", asUtility=True, name=bump_node_name)
        cmds.setAttr(bump_node + ".bumpDepth", 0.4)
        cmds.setAttr(bump_node + ".bumpInterp", 0)  # tangent space normals

        cmds.connectAttr(file_node + ".outAlpha", bump_node + ".bumpValue", force=True)
        # Connect bump output to the lambert's normalCamera.
        # ``cmds.sets(sg, query=True)`` returns SET MEMBERS (meshes),
        # NOT the shader - connecting to a mesh's ``.normalCamera``
        # fails and ``force=True`` severs the lambert's existing
        # ``.color`` connection from the condition node, turning
        # flowers colorless.  Use ``listConnections(sg.surfaceShader)``
        # to find the actual lambert.
        #
        # NOTE: when ``two_sided=True``, the lambert's ``.color`` is
        # already driven by the condition node's ``outColor``.  Connecting
        # ``bump.outNormal`` to ``lambert.normalCamera`` is a DIFFERENT
        # plug, so ``force=True`` here does NOT sever the color
        # connection  -  this was the root cause of the previous "black
        # leaf" bug: the duplicate vein-bump code block in
        # ``create_foliage_in_maya`` re-implemented this logic and
        # accidentally broke the condition network.  Consolidating here
        # ensures the bump is wired exactly once, after the condition.
        shaders = cmds.listConnections(
            base_sg + ".surfaceShader", source=True
        ) or []
        if shaders:
            cmds.connectAttr(
                bump_node + ".outNormal",
                shaders[0] + ".normalCamera",
                force=True,
            )

    # NOTE: A petal base->tip ramp gradient was attempted but removed  - 
    # MFnMesh.create() produces procedural meshes WITHOUT UV coordinates,
    # so the ramp texture sampled to default and turned flowers black.
    # Restoring the gradient would require authoring UVs per-petal.  The
    # solid species color from _material is used instead.
    return base_sg


def _set_bool_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="bool")
    cmds.setAttr(node + "." + attr, bool(value))


def _set_string_attr(cmds, node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, dataType="string")
    cmds.setAttr(node + "." + attr, value, type="string")


def _create_mesh(cmds, om, arrays, name, parent, shading_group, smooth_level=0,
                 generate_uvs=False, depth_bias=-0.5):
    """Create a Maya mesh from raw point/count/connect arrays.

    ``smooth_level`` applies ``polySmoothFace`` subdivisions after
    creation  -  woody leaves/flowers use level 1-2 to soften the faceted
    procedural silhouette into organic curves.  The smoothing is
    applied before the shader/depth setup so polygonOffset and
    castsShadows apply to the final smoothed shape.

    ``generate_uvs`` triggers automatic planar UV projection after mesh
    creation so that vein bump maps and petal gradient ramps sample
    correctly instead of falling back to a default value.

    ``depth_bias`` controls the polygonOffset value applied to the
    mesh shape.  More negative = closer to camera = renders in front.
    Default -0.5 is the standard foliage bias; flowers use a more
    negative value (e.g. -1.0) so they always render in front of
    leaves at the same depth, preventing leaves from occluding
    blossoms  -  the standard game-engine depth-bias trick for
    foreground hero objects.
    """
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
    # Generate UVs for vein bump maps and petal gradient ramps.
    # Planar projection along the best-fit axis gives clean 0-1 UVs
    # for the mostly-flat leaf/petal geometry.
    if generate_uvs:
        try:
            # NOTE: ``intelligentMode`` is NOT a valid flag for
            # cmds.polyProjection in Maya  -  passing it raises
            # "parse error: 标志'intelligentMode'无效" which is the
            # exact symptom users see in the script editor.  The flag
            # only exists on the MEL polyProjection command form with
            # a different signature.  Use the minimal Planar projection
            # with construction history disabled.
            cmds.polyProjection(
                transform, type="Planar",
                ch=False,
            )
        except Exception:
            # UV generation is cosmetic  -  never fail mesh creation.
            pass
    # Mesh smoothing via ``polySmooth`` for woody foliage.
    # This applies Catmull-Clark-style subdivision to the actual mesh
    # geometry, increasing face count but producing smooth organic
    # curves visible in BOTH viewport and renders.
    #
    # Previously this used ``displayMeshSmoothLevel`` (OpenSubdiv render-
    # time smoothing), but that attribute is missing on many Maya
    # versions and silently no-ops.  ``polySmooth`` modifies the
    # geometry directly so it works on every Maya version.
    #
    # NOTE: the Maya command is ``polySmooth``; ``polySmoothFace`` is the
    # DEPENDENCY NODE TYPE created by the command, not a command itself.
    # Using ``cmds.polySmoothFace(...)`` raises
    # "module 'maya.cmds' has no attribute 'polySmoothFace'".
    #
    # FLAG COMPATIBILITY: ``polySmooth`` flags vary significantly across
    # Maya versions.  ``keepMapBorder`` raised "标志无效" on the user's
    # Maya version.  To guarantee cross-version compatibility we use the
    # MINIMAL flag set  -  only ``divisions`` and ``ch``  -  and rely on
    # Maya's sensible defaults for border/hard-edge/UV preservation.
    # Adding version-specific flags would require try/except per flag,
    # which is fragile and noisy.  The minimal form works everywhere.
    #
    # ``polySmooth`` operates on the current face selection.  For a
    # freshly-created MFnMesh the selection is empty, so we must
    # explicitly select all faces of the mesh first.
    #   level 1: gentle rounding of hard edges (~4x faces)
    #   level 2: smooth organic curves (~16x faces, used for petals/leaves)
    if smooth_level > 0:
        try:
            # Select all faces of the mesh so polySmooth has a target.
            cmds.select(shape + ".f[0:]", replace=True)
            # Minimal flag set for maximum Maya version compatibility.
            # divisions: subdivision level (1 or 2)
            # ch=False: no construction history (clean mesh, no dependency node)
            cmds.polySmooth(
                divisions=smooth_level,
                ch=False,
            )
            cmds.select(clear=True)
            # After polySmooth the shape path may have changed  -  re-query.
            shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        except Exception:
            # Smoothing is a cosmetic enhancement  -  never fail mesh
            # creation if polySmooth fails for any reason.
            cmds.select(clear=True)
    cmds.setAttr(shape + ".doubleSided", True)
    # Foliage/flower meshes are thin organs; disabling self-shadowing
    # avoids ugly dark patches on petals and leaves caused by nearby
    # instances casting shadows onto each other.  Note the Maya attribute
    # is spelled "castsShadows" (with an 's'), not "castShadows".
    if cmds.attributeQuery("castsShadows", node=shape, exists=True):
        cmds.setAttr(shape + ".castsShadows", False)
    if cmds.attributeQuery("receiveShadows", node=shape, exists=True):
        cmds.setAttr(shape + ".receiveShadows", False)
    # Shader-side penetration fix: pull foliage depth toward the camera
    # so leaves/flowers always render in front of branches they
    # geometrically penetrate.  This replaces expensive per-vertex
    # collision detection with a cheap render-state tweak  -  the standard
    # approach used by game engines and SpeedTree-style foliage.
    #   - polygonOffset: biases the depth test so foliage wins ties
    #     against branch geometry at the same depth.  ``depth_bias``
    #     lets the caller push flowers further forward than leaves so
    #     blossoms are never occluded by nearby leaves.
    #   - oppositeZ: renders back faces with reversed depth so internal
    #     faces don't fight front faces.
    if cmds.attributeQuery("polygonOffset", node=shape, exists=True):
        # Negative bias = closer to camera = renders in front.
        cmds.setAttr(shape + ".polygonOffset", depth_bias)
    if cmds.attributeQuery("oppositeZ", node=shape, exists=True):
        cmds.setAttr(shape + ".oppositeZ", True)
    # Smooth and unify face normals so every triangle is lit consistently.
    # Without this, inverted-winding faces appear dark even with
    # doubleSided enabled, producing fake "shadow" patches.
    try:
        cmds.polySoftEdge(shape, angle=180, ch=False)
        cmds.polyNormal(shape, normalMode=1, ch=False)  # 1 = conform normals
    except Exception:
        pass
    # Assign the shading group at the SHAPE level (not transform) and
    # explicitly cover ALL faces.  Previously this used
    # ``cmds.sets(transform, edit=True, forceElement=shading_group)``
    # which assigns at the transform level.  When the mesh has been
    # through construction-history operations (``polySoftEdge`` /
    # ``polyNormal`` above), some faces can lose their SG association
    # and fall back to ``initialShadingGroup``  -  the user sees a
    # "partially grey, partially coloured" leaf.  Assigning the shape
    # with ``forceElement`` forces every face onto the target SG.
    cmds.sets(shape, edit=True, forceElement=shading_group)
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
    """Create one seasonal organ using the same geometry as attached organs.

    Parameters:
        foliage_model (FoliageModel): Provides palette, average sizes and
            species info used to build a representative prototype.
        kind (str): "leaf" or "flower"  -  selects which organ to build.
        parent (str): Maya parent transform for the prototype node.
        name (str): Maya node name for the prototype transform.
    """
    try:
        import maya.api.OpenMaya as om
        import maya.cmds as cmds
    except ImportError:
        # ``raise X from Y`` is Python 3+ syntax  -  Maya's Python 2.7
        # raises SyntaxError at import ("parse error").  Plain raise is
        # the 2.7-compatible form.
        raise RuntimeError("This function must run inside Maya")

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
    average_peduncle = sum(
        flower.peduncle_length for flower in foliage_model.flowers
    ) / len(foliage_model.flowers)
    # Read woody_species from the foliage config so the prototype
    # emits species-accurate geometry (cherry V-notch, stamen count,
    # pedicel ratio, etc.).  Without this, build_flower_mesh_groups
    # falls back to the legacy generic flower even when the user
    # selected a woody species.
    woody_species = getattr(
        getattr(foliage_model, "config", None), "woody_species", None
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
        peduncle_length=average_peduncle,
        species=woody_species,
    )
    prototype_model = _PrototypeFoliageModel(
        profile,
        flowers=[prototype_flower],
    )
    petal_groups, center_arrays, sepal_arrays = build_flower_mesh_groups(prototype_model)
    petal_material_name = name + "_Petal_MAT"
    center_material_name = name + "_Center_MAT"
    sepal_material_name = name + "_Sepal_MAT"
    # Woody species get vein-bump materials + OpenSubdiv smoothing so
    # the prototype renders with the same quality as attached organs.
    # Non-woody prototypes keep plain lambert so the weather particle
    # fallback path is unchanged.
    #
    # Color separation (botanically accurate):
    # - Petals: species palette (pink/white) with translucent SSS.
    # - Center (receptacle + stamens + pistil): species center_color  - 
    #   peach orange, cherry yellow, pear dark-purple, plum yellow.
    #   Previously this used profile.center_color (seasonal), which
    #   ignored the species-specific anther/stigma coloring entirely.
    # - Sepals: dedicated green  -  the calyx is a leaf-derived green
    #   structure regardless of petal color, so dyeing it with the
    #   seasonal center_color made blossoms look wrong.
    if woody_species:
        spec = WOODY_FLOWER_SPECS.get(woody_species)
        petal_sg = _material_with_veins(
            cmds,
            petal_material_name,
            profile.flower_palette[color_index],
            kind="flower", species=woody_species,
        )
        center_color = spec.center_color if spec is not None else profile.center_color
        center_sg = _material(
            cmds,
            center_material_name,
            center_color,
        )
        sepal_color_val = spec.pedicel_color if spec else SEPAL_GREEN_COLOR
        sepal_sg = _material(
            cmds,
            sepal_material_name,
            sepal_color_val,
        )
        smooth = 2
    else:
        petal_sg = _material(
            cmds,
            petal_material_name,
            profile.flower_palette[color_index],
        )
        center_sg = _material(
            cmds,
            center_material_name,
            profile.center_color,
        )
        sepal_sg = None
        smooth = 0
    petal_mesh = _create_mesh(
        cmds,
        om,
        petal_groups[color_index],
        name + "_Petals",
        parent,
        petal_sg,
        smooth_level=smooth,
    )
    center_mesh = _create_mesh(
        cmds,
        om,
        center_arrays,
        name + "_Center",
        parent,
        center_sg,
        smooth_level=smooth,
    )
    # Sepal mesh: only created when the sepal array has geometry (woody
    # path).  Skipping an empty array avoids Maya creating a degenerate
    # mesh that pollutes the prototype with stray verts.
    sepal_mesh = None
    if sepal_arrays[0]:
        sepal_mesh = _create_mesh(
            cmds,
            om,
            sepal_arrays,
            name + "_Sepals",
            parent,
            sepal_sg,
            smooth_level=smooth,
        )
    # polyUnite with explicit if/else instead of *args unpacking  - 
    # *unpacking in function calls is Python 3.5+ only, but Maya
    # 2018/2019 ships Python 2.7 and raises SyntaxError ("parse error")
    # on this syntax at import time.
    if sepal_mesh:
        prototype = cmds.polyUnite(
            petal_mesh, center_mesh, sepal_mesh,
            constructionHistory=False, name=name,
        )[0]
    else:
        prototype = cmds.polyUnite(
            petal_mesh, center_mesh,
            constructionHistory=False, name=name,
        )[0]
    cmds.parent(prototype, parent)
    cmds.setAttr(prototype + ".visibility", False)
    material_list = [
        petal_material_name,
        petal_sg,
        center_material_name,
        center_sg,
    ]
    if sepal_sg is not None:
        material_list.extend([sepal_material_name, sepal_sg])
    return prototype, material_list


def _flower_instance_state(flower):
    """Return ``"bud"``, ``"bloom"``, or ``"wilt"`` from existing openness/wilt.

    Uses the same morphological thresholds that ``_flower_state_openness``
    produces in the pure-Python layer:
      - wilt >= 0.40  ->  ``"wilt"``  (wilt state: 0.55-0.85)
      - openness < 0.30  ->  ``"bud"``   (bud state: 0.10-0.28)
      - otherwise  ->  ``"bloom"``

    These ranges are non-overlapping by construction so every flower
    maps to exactly one state.
    """
    if flower.wilt >= 0.40:
        return "wilt"
    if flower.openness < 0.30:
        return "bud"
    return "bloom"


def _build_flower_instances(cmds, om, model, parent, name):
    """Create woody flower prototypes and instance them to every flower.

    Instead of merging every flower's geometry into one giant mesh
    (the legacy path), this builds up to THREE high-precision prototypes
    per color_index  -  one each for bud, bloom, and wilt states  -  and
    uses Maya ``cmds.instance()`` to copy each prototype to its matching
    flowers.  Benefits:

    - Geometry cost is O(3) in color count (at most 3 prototypes per
      color, N cheap transforms) instead of O(N) merged vertices.
    - Each state prototype bakes the state's characteristic openness
      and wilt into the petal geometry: buds stay tightly closed,
      blooms fan wide open, and wilted petals droop and curl.
    - Per-flower size variation is handled by uniform scale on the
      instance transform (``flower.size / avg_size``).

    The prototype's local frame is +Y=forward, -Z=side, -X=normal
    (the canonical orientation produced by ``direction=(0,1,0),
    azimuth=0``).  Each instance's world matrix maps that frame onto
    the flower's actual ``(forward, rotated_side, rotated_normal)``
    from ``_orientation``.

    Returns ``(instance_transforms, prototype_nodes)``.
    """
    woody_species = getattr(
        getattr(model, "config", None), "woody_species", None
    )
    procedural_flowers = [f for f in model.flowers if not f.asset_id]
    if not woody_species or not procedural_flowers:
        return [], []

    # Group procedural flowers by (color_index, state) so each
    # morphological state (bud / bloom / wilt) gets its own prototype
    # with the state's characteristic openness/wilt baked into the
    # petal geometry.  A single per-color prototype silently averaged
    # away the per-state variation (2026-07 fix).
    by_color_state = {}
    for flower in procedural_flowers:
        state = _flower_instance_state(flower)
        by_color_state.setdefault((flower.color_index, state), []).append(flower)

    instances = []
    prototypes = []
    for (color_index, state), flowers in by_color_state.items():
        avg_size = sum(f.size for f in flowers) / len(flowers)
        avg_openness = sum(f.openness for f in flowers) / len(flowers)
        avg_wilt = sum(f.wilt for f in flowers) / len(flowers)
        avg_peduncle = sum(f.peduncle_length for f in flowers) / len(flowers)
        prototype_flower = FlowerInstance(
            position=(0.0, 0.0, 0.0),
            direction=(0.0, 1.0, 0.0),
            azimuth=0.0,
            size=avg_size,
            color_index=color_index,
            openness=avg_openness,
            wilt=avg_wilt,
            source_tip=-1,
            peduncle_length=avg_peduncle,
            species=woody_species,
        )
        proto_model = _PrototypeFoliageModel(
            model.profile, flowers=[prototype_flower],
        )
        petal_groups, center_arrays, sepal_arrays = build_flower_mesh_groups(proto_model)

        # Materials: woody petals get vein bump + species color; the
        # center (receptacle + stamens + pistil) uses the species
        # center_color (peach orange, cherry yellow, pear dark-purple,
        # plum yellow)  -  previously this used profile.center_color
        # (seasonal), which ignored species-specific anther/stigma
        # coloring.  Sepals get a dedicated green material because the
        # calyx is a leaf-derived green structure regardless of petal
        # color.
        # Include season_key in the prototype material base so each
        # season gets fresh materials.  Previously the base was
        # ``{name}_FlowerProto_{color_index}`` (no season) so materials
        # were reused across seasons  -  ``_material``'s color-update
        # fix handles the reuse case, but fresh-per-season is cleaner
        # and avoids stale vein-texture connections from a deleted
        # prototype.
        season_key = model.profile.key
        proto_base = "{}_{}_FlowerProto_{}_{:02d}".format(
            name, season_key, state, color_index,
        )
        spec = WOODY_FLOWER_SPECS.get(woody_species)
        petal_sg = _material_with_veins(
            cmds,
            proto_base + "_Petal_MAT",
            model.profile.flower_palette[color_index],
            kind="flower", species=woody_species,
        )
        center_color = spec.center_color if spec is not None else model.profile.center_color
        center_sg = _material(
            cmds,
            proto_base + "_Center_MAT",
            center_color,
        )
        sepal_color_val = spec.pedicel_color if spec else SEPAL_GREEN_COLOR
        sepal_sg = _material(
            cmds,
            proto_base + "_Sepal_MAT",
            sepal_color_val,
        )
        # smooth_level=1 applies one round of Catmull-Clark subdivision
        # to the prototype petals for smoother organic curvature.
        # Reduced from 2 (2026-07) per user request to lower the flower
        # mesh subdivision level.  Affordable because there is only one
        # prototype per color_index, and all instances share the
        # prototype's geometry via cmds.instance()  -  zero extra cost.
        #
        # depth_bias=-1.0 pushes flower meshes closer to the camera than
        # leaves (default -0.5) so blossoms are never occluded by nearby
        # leaves at the same depth  -  the standard hero-object depth
        # bias trick.  All three flower sub-meshes (petals/center/
        # sepals) use the same bias so the blossom reads as one unit.
        petal_mesh = _create_mesh(
            cmds, om, petal_groups[color_index],
            proto_base + "_Petals", parent, petal_sg, smooth_level=1,
            generate_uvs=True, depth_bias=-1.0,
        )
        center_mesh = _create_mesh(
            cmds, om, center_arrays,
            proto_base + "_Center", parent, center_sg, smooth_level=1,
            depth_bias=-1.0,
        )
        sepal_mesh = None
        if sepal_arrays[0]:
            sepal_mesh = _create_mesh(
                cmds, om, sepal_arrays,
                proto_base + "_Sepals", parent, sepal_sg, smooth_level=1,
                depth_bias=-1.0,
            )
        # Guard against petal/center failing to create  -  polyUnite on
        # None inputs would raise and abort the whole foliage build.
        if not petal_mesh or not center_mesh:
            continue
        # polyUnite with explicit if/else  -  *args unpacking is
        # Python 3.5+ only and breaks Maya's Python 2.7 at import.
        if sepal_mesh:
            prototype = cmds.polyUnite(
                petal_mesh, center_mesh, sepal_mesh,
                constructionHistory=False, name=proto_base,
            )[0]
        else:
            prototype = cmds.polyUnite(
                petal_mesh, center_mesh,
                constructionHistory=False, name=proto_base,
            )[0]
        cmds.parent(prototype, parent)
        # polyUnite creates a fresh shape that does NOT inherit the
        # per-shape polygonOffset set on the petal/center/sepal sub-
        # meshes above.  Re-apply the flower depth bias on the united
        # prototype so all flower instances render in front of leaves
        # (instances share the prototype's shape, so this single set
        # covers every flower instance).
        proto_shape = cmds.listRelatives(prototype, shapes=True, fullPath=True)
        if proto_shape:
            proto_shape = proto_shape[0]
            if cmds.attributeQuery("polygonOffset", node=proto_shape, exists=True):
                cmds.setAttr(proto_shape + ".polygonOffset", -1.0)
            if cmds.attributeQuery("castsShadows", node=proto_shape, exists=True):
                cmds.setAttr(proto_shape + ".castsShadows", False)
            if cmds.attributeQuery("receiveShadows", node=proto_shape, exists=True):
                cmds.setAttr(proto_shape + ".receiveShadows", False)
        # CRITICAL: the prototype is hidden so it does not render at
        # the origin, but Maya instances INHERIT the source visibility
        #  -  every instance created from a hidden prototype is also
        # hidden.  We re-enable visibility per-instance below.
        cmds.setAttr(prototype + ".visibility", False)
        prototypes.append(prototype)

        # Instance the prototype to every flower in this (color,state) group.
        instance_group = cmds.group(
            empty=True, name=proto_base + "_Instances", parent=parent,
        )

        # PERFORMANCE: original loop issued 4 cmds calls per flower
        # (instance, parent, xform, setAttr)  ->  4*N cmds round-trips
        # that dominated spring-scene runtime (N can reach ~300 with
        # flower_density=0.52).  Refactored into 4 batched phases
        # (unchanged from the single-prototype-per-color era  -  the
        # same batching works for the per-state group sizes).
        #   Phase 1: N cmds.instance (unavoidable  -  no batch API)
        #   Phase 2: 1 cmds.parent (list form, N -> 1 call)
        #   Phase 3: N OpenMaya MFnTransform.set (~5-10x faster than
        #            cmds.xform; falls back to cmds.xform on any error)
        #   Phase 4: N cmds.setAttr (visibility; cheap, kept as loop)
        # Net: 2N+1 cmds calls + N om calls, vs original 4N cmds calls.

        # Phase 1  -  create all instances (inherit prototype's parent).
        new_instances = []
        for i in range(len(flowers)):
            inst = cmds.instance(
                prototype, name="{}_Inst_{:04d}".format(proto_base, i),
            )[0]
            new_instances.append(inst)
            instances.append(inst)

        if not new_instances:
            continue

        # Phase 2  -  batch-parent every instance to instance_group.
        # Use list form (not *args)  -  PEP 448 *unpacking is Python 3.5+
        # and breaks Maya's Python 2.7 at import time. cmds.parent with
        # a list parents all objects in one DG update.
        cmds.parent(new_instances, instance_group)

        # Phase 3  -  set each instance's world matrix.
        # OpenMaya MFnTransform.set(MTransformationMatrix, kWorld) is
        # functionally identical to cmds.xform(worldSpace=True, matrix=m)
        # but bypasses the cmds wrapper layer.  Wrapped in try/except so
        # any API mismatch (older Maya, non-transform node) transparently
        # falls back to the original cmds.xform path.
        for inst, flower in zip(new_instances, flowers):
            forward, rotated_side, rotated_normal = _orientation(
                flower.direction, flower.azimuth,
            )
            # Uniform scale compensates for per-flower size variation.
            # peduncle_length scales with size (same pedicel_ratio), so
            # scaling the whole prototype geometry is botanically correct.
            s = flower.size / avg_size if avg_size > 1.0e-9 else 1.0
            px, py, pz = flower.position
            # World matrix (row-major, row-vector convention):
            #   row 0 = s * -rotated_normal   (prototype +X -> -normal)
            #   row 1 = s * forward           (prototype +Y -> forward)
            #   row 2 = s * -rotated_side     (prototype +Z -> -side)
            #   row 3 = flower.position
            # This maps the prototype's canonical frame onto the
            # flower's actual (forward, side, normal) frame.
            matrix = [
                s * -rotated_normal[0], s * -rotated_normal[1], s * -rotated_normal[2], 0.0,
                s * forward[0],         s * forward[1],         s * forward[2],         0.0,
                s * -rotated_side[0],   s * -rotated_side[1],   s * -rotated_side[2],   0.0,
                px,                     py,                     pz,                     1.0,
            ]
            try:
                # OpenMaya 2.0 fast path.  MMatrix is row-major (same
                # layout as cmds.xform's matrix arg), and MFnTransform.set
                # with kWorld space converts the world matrix to local
                # using the parent's worldInverseMatrix  -  exactly what
                # cmds.xform(worldSpace=True) does internally.
                sel_list = om.MSelectionList()
                sel_list.add(inst)
                transform_fn = om.MFnTransform(sel_list.getDagPath(0))
                transform_fn.set(
                    om.MTransformationMatrix(om.MMatrix(matrix)),
                    om.MSpace.kWorld,
                )
            except Exception:
                # Fallback  -  preserve original behavior if the
                # OpenMaya path fails (e.g. inst is not a transform
                # node, or API version mismatch on older Maya).
                cmds.xform(inst, worldSpace=True, matrix=matrix)

        # Phase 4  -  re-enable visibility.
        # prototype is hidden so instances inherit visibility=False;
        # each instance must be explicitly re-enabled.  cmds.setAttr is
        # cheap (no DG propagation for visibility), so the loop overhead
        # is negligible vs Phase 1/3.
        for inst in new_instances:
            cmds.setAttr(inst + ".visibility", True)

    return instances, prototypes


def _diagnose_scene_state(cmds):
    """Scan the scene for nodes that may cause 'parse error' during foliage build.

    The most common cause of Maya's 'parse error / 解析错误' that still
    allows the tree to generate is a leftover ``expression`` node whose
    body references an already-deleted bend deformer.  When the DG
    re-evaluates (e.g. during material creation or shading group
    assignment), Maya's expression parser raises the error.

    This function logs the count and names of:
      - Orphaned ``*_WindExpression`` nodes
      - Any expression nodes whose targets no longer exist
      - Orphaned ``condition`` / ``samplerInfo`` nodes from a previous
        two-sided leaf material that was incompletely cleaned up

    Call this at the START of ``create_foliage_in_maya`` so the script
    editor shows the scene state before any new nodes are created.
    """
    # 1. Wind expression nodes (the #1 cause of 'parse error').
    wind_exprs = cmds.ls("*_WindExpression", type="expression") or []
    # Orphaned WindExpression nodes reference deleted deformers and
    # cause 'parse error' on DG evaluation.  Callers can detect them
    # via the returned 'wind_expressions' list and clean up with
    # maya_weather.delete_weather_nodes() or
    # maya_editing.cleanup_orphaned_lsystem_nodes().
    # 2. Any expression node whose body references a non-existent node.
    all_exprs = cmds.ls(type="expression") or []
    broken_exprs = []
    for expr in all_exprs:
        try:
            body = cmds.getAttr(expr + ".expression") or ""
        except (RuntimeError, ValueError):
            broken_exprs.append((expr, "<unreadable body>"))
            continue
        # Heuristic: if the body contains a node reference, check that
        # at least one referenced plug still exists.  Expression bodies
        # look like 'node.attr = ...'; extract the node name before '.'.
        import re as _re
        refs = _re.findall(r"([\w|]+)\.\w+\s*=", body)
        for ref in refs:
            # Skip built-in keywords (frame, time, etc.).
            if ref in ("frame", "time", "playbackSpeed"):
                continue
            # Refs may contain '|path|' - take the last segment.
            short = ref.split("|")[-1]
            if not cmds.objExists(short):
                broken_exprs.append((expr, short))
                break
    if broken_exprs:
        # Broken expression nodes reference missing targets and will
        # raise 'parse error' on evaluation.  Callers can detect them
        # via the returned 'broken_expressions' list.
        pass
    # 3. Orphaned condition/samplerInfo nodes (from two-sided leaf cleanup).
    orphan_conditions = []
    for cond in cmds.ls(type="condition") or []:
        conns = cmds.listConnections(cond, source=True, destination=False) or []
        # A healthy condition node is connected to a lambert.  If it has
        # NO downstream shader connection, it's an orphan.
        downstream = cmds.listConnections(cond, source=False, destination=True) or []
        if not downstream:
            orphan_conditions.append(cond)
    if orphan_conditions:
        # Orphaned condition nodes have no downstream shader and may
        # hold stale color values.  Callers can detect them via the
        # returned 'orphan_conditions' list.
        pass
    return {
        "wind_expressions": wind_exprs,
        "broken_expressions": broken_exprs,
        "orphan_conditions": orphan_conditions,
    }


def create_foliage_in_maya(
    tree_model,
    config=None,
    parent_root=None,
    name="LSystemTree",
):
    """Create the full foliage layer (leaves + flowers) as Maya meshes.

    Parameters:
        tree_model (TreeModel): Tree to dress with leaves and flowers.
        config (FoliageConfig|None): Foliage configuration.  Defaults to
            ``FoliageConfig(seed=tree_model.config.seed + 101)``.
        parent_root (str|None): Maya transform under which the foliage
            group is parented.  None places it at world root.
        name (str): Maya node name prefix for the foliage group and
            child meshes.
    """
    try:
        import maya.api.OpenMaya as om
        import maya.cmds as cmds
    except ImportError:
        # ``raise X from Y`` is Python 3+ syntax  -  Maya's Python 2.7
        # raises SyntaxError at import ("parse error").  Plain raise is
        # the 2.7-compatible form.
        raise RuntimeError("This function must run inside Maya")

    # Pre-flight diagnostic: detect any orphaned expression/condition
    # nodes that could cause 'parse error' during the build.  The
    # returned dict is available for callers but not logged.
    try:
        _diagnose_scene_state(cmds)
    except Exception:
        pass

    config = config or FoliageConfig(seed=tree_model.config.seed + 101)

    try:
        model = generate_foliage(tree_model, config)
    except Exception:
        raise

    group = cmds.group(empty=True, name=name + "_Foliage", parent=parent_root)
    _set_bool_attr(cmds, group, "lsystemFoliageManaged", True)
    meshes = []
    leaf_meshes = []
    flower_meshes = []
    twig_meshes = []
    season_key = model.profile.key

    # --- Phase 0: Twig mesh (visible fine shoots, 2026-07) ---
    # When twig generation is enabled, each GrowthTip grows a visible
    # curved twig that carries leaves at its tip.  The twig mesh reuses
    # the main branch bark material so it visually blends with the
    # trunk.  Built before leaves so leaves (Phase 1) render in front.
    if getattr(config, "twig_enabled", False) and model.twigs:
        try:
            twig_arrays = build_twig_mesh_arrays(model)
        except Exception:
            twig_arrays = {}
        if twig_arrays:
            twig_shading_group = _get_twig_shading_group(cmds)
            for color_index, arrays in twig_arrays.items():
                mesh = _create_mesh(
                    cmds,
                    om,
                    arrays,
                    "{}_Twigs".format(name),
                    group,
                    twig_shading_group,
                    smooth_level=0,
                    generate_uvs=False,
                )
                if mesh:
                    meshes.append(mesh)
                    twig_meshes.append(mesh)

    # --- Phase 1: Leaf mesh groups (procedural only, 2026-07) ---
    # All leaves are procedurally generated; the OBJ organ catalog is
    # no longer loaded.  build_asset_mesh_groups would return {} since
    # every leaf now has asset_id=None.
    woody_species = getattr(config, "woody_species", None)
    leaf_smooth = 0
    try:
        leaf_groups = build_leaf_mesh_groups(model)
        if not leaf_groups:
            # Empty groups can happen when there are zero leaves.
            leaf_groups = {}
    except Exception:
        raise

    for color_index, arrays in leaf_groups.items():
        if woody_species:
            # Woody leaves get vein bump mapping for realistic venation
            # detail.  Single-sided lambert renders correctly in all
            # viewport modes.
            mat_name = "LSystemLeaf_{}_{:02d}_MAT".format(season_key, color_index)
            front_color = model.profile.leaf_palette[color_index]
            if woody_species:
                leaf_spec = WOODY_LEAF_SPECS.get(woody_species)
                if leaf_spec:
                    shift = leaf_spec.leaf_color_shift
                    front_color = tuple(
                        max(0.0, min(1.0, c + s))
                        for c, s in zip(front_color, shift)
                    )
            shading_group = _material_with_veins(
                cmds,
                mat_name,
                front_color,
                kind="leaf", species=woody_species,
                two_sided=False,
            )
            smooth_level = leaf_smooth
        else:
            shading_group = _material(
                cmds,
                "LSystemLeaf_{}_{:02d}_MAT".format(season_key, color_index),
                model.profile.leaf_palette[color_index],
            )
            smooth_level = 0
        mesh = _create_mesh(
            cmds,
            om,
            arrays,
            "{}_Leaves_{:02d}".format(name, color_index),
            group,
            shading_group,
            smooth_level=smooth_level,
            generate_uvs=bool(woody_species),
        )
        if mesh:
            meshes.append(mesh)
            leaf_meshes.append(mesh)

    # --- Phase 2: Flower mesh groups (procedural only, 2026-07) ---
    # All flowers are procedurally generated; the OBJ organ catalog is
    # no longer loaded.  build_asset_mesh_groups would return {} since
    # every flower now has asset_id=None.
    if woody_species:
        try:
            flower_instances, _flower_protos = _build_flower_instances(
                cmds, om, model, group, name,
            )
        except Exception:
            flower_instances, _flower_protos = [], []
        if flower_instances:
            flower_meshes.extend(flower_instances)
            meshes.extend(flower_instances)
        center_mesh = None
    else:
        # Legacy merged-geometry path for non-woody flowers: every
        # flower's geometry is concatenated into one big mesh per
        # color.  Preserved for tests and backward compatibility.
        petal_groups, center_arrays, _ = build_flower_mesh_groups(model)
        for color_index, arrays in petal_groups.items():
            shading_group = _material(
                cmds,
                "LSystemFlower_{}_{:02d}_MAT".format(season_key, color_index),
                model.profile.flower_palette[color_index],
            )
            mesh = _create_mesh(
                cmds, om, arrays,
                "{}_Flowers_{:02d}".format(name, color_index),
                group, shading_group, smooth_level=0,
                depth_bias=-1.0,
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
            smooth_level=0,
            depth_bias=-1.0,
        )
        if center_mesh:
            meshes.append(center_mesh)

    # --- Phase 3: Metadata attributes ---
    try:
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
        _set_string_attr(
            cmds,
            group,
            "foliageConfigJson",
            json.dumps(dict(config.__dict__), sort_keys=True),
        )
    except Exception:
        pass

    return {
        "group": group,
        "meshes": meshes,
        "leaf_meshes": leaf_meshes,
        "flower_meshes": flower_meshes,
        "twig_meshes": twig_meshes,
        "flower_center_mesh": center_mesh,
        "model": model,
    }
