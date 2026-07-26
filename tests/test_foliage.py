# -*- coding: utf-8 -*-
from __future__ import division

import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core import TreeConfig, generate_tree
from src.foliage import (
    FoliageConfig,
    TwigInstance,
    WOODY_FLOWER_SPECS,
    WOODY_LEAF_SPECS,
    generate_foliage,
    get_season,
)
from src.maya_foliage import (
    build_flower_mesh_groups,
    build_leaf_mesh_groups,
    build_twig_mesh_arrays,
)


class SeasonalFoliageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = generate_tree(
            TreeConfig.from_preset("broadleaf_round", branch_levels=3, seed=31)
        )

    def test_season_profiles_follow_expected_cycle(self):
        spring = get_season("spring")
        summer = get_season("summer")
        autumn = get_season("autumn")
        winter = get_season("winter")
        self.assertGreater(summer.leaf_density, spring.leaf_density)
        self.assertGreater(spring.leaf_density, autumn.leaf_density)
        self.assertGreater(autumn.leaf_density, winter.leaf_density)
        self.assertGreater(spring.flower_density, summer.flower_density)
        self.assertGreater(autumn.flower_wilt, summer.flower_wilt)
        self.assertEqual(winter.flower_density, 0.0)

    def test_foliage_is_reproducible(self):
        first = generate_foliage(
            self.tree,
            FoliageConfig(season="spring", seed=55),
        )
        second = generate_foliage(
            self.tree,
            FoliageConfig(season="spring", seed=55),
        )
        self.assertEqual(
            [(leaf.position, leaf.length) for leaf in first.leaves],
            [(leaf.position, leaf.length) for leaf in second.leaves],
        )
        self.assertEqual(
            [(flower.position, flower.wilt) for flower in first.flowers],
            [(flower.position, flower.wilt) for flower in second.flowers],
        )

    def test_seasons_change_leaf_and_flower_counts(self):
        spring = generate_foliage(self.tree, FoliageConfig(season="spring", seed=8))
        summer = generate_foliage(self.tree, FoliageConfig(season="summer", seed=8))
        winter = generate_foliage(self.tree, FoliageConfig(season="winter", seed=8))
        self.assertGreater(len(summer.leaves), len(spring.leaves))
        self.assertGreater(len(spring.leaves), len(winter.leaves))
        self.assertGreater(len(spring.flowers), len(summer.flowers))
        self.assertEqual(len(winter.flowers), 0)

    def test_size_multipliers_change_geometry_scale(self):
        # twig_enabled=False isolates the size-scaling math from the
        # twig-length feedback loop (twig length depends on leaf_size,
        # which changes leaf position, which changes avoidance scale).
        small = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring",
                leaf_size_multiplier=0.5,
                flower_size_multiplier=0.5,
                seed=19,
                twig_enabled=False,
            ),
        )
        large = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring",
                leaf_size_multiplier=1.5,
                flower_size_multiplier=1.5,
                seed=19,
                twig_enabled=False,
            ),
        )
        self.assertAlmostEqual(large.leaves[0].length, small.leaves[0].length * 3.0)
        self.assertAlmostEqual(large.flowers[0].size, small.flowers[0].size * 3.0)

    def test_leaf_mesh_arrays_have_expected_topology(self):
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=7),
        )
        groups = build_leaf_mesh_groups(foliage_model)
        total_points = sum(len(arrays[0]) for arrays in groups.values())
        total_faces = sum(len(arrays[1]) for arrays in groups.values())
        total_connects = sum(len(arrays[2]) for arrays in groups.values())
        # Each leaf: 3 petiole vertices + 15 blade vertices (5 stations * 3) = 18
        # Each leaf: 1 petiole face + 16 blade faces (4 segs * 2 sides * 2 tris) = 17
        # Each leaf: 3 petiole connects + 48 blade connects = 51
        self.assertEqual(total_points, len(foliage_model.leaves) * 18)
        self.assertEqual(total_faces, len(foliage_model.leaves) * 17)
        self.assertEqual(total_connects, len(foliage_model.leaves) * 51)

    def test_default_broadleaf_forms_a_dense_canopy(self):
        tree = generate_tree(TreeConfig.from_preset("broadleaf_round", seed=17))
        foliage_model = generate_foliage(
            tree,
            FoliageConfig(season="summer", seed=118),
        )
        minimum, maximum = tree.bounds()
        canopy_floor = minimum[1] + (maximum[1] - minimum[1]) * 0.20
        self.assertGreater(len(foliage_model.leaves), 2500)
        self.assertTrue(
            all(leaf.position[1] >= canopy_floor - 0.2 for leaf in foliage_model.leaves)
        )

    def test_foliage_hugs_branch_surface_within_small_jitter(self):
        # Leaves should sit on the branch bark surface (center + radius *
        # normal) with only a tiny natural wiggle (<= 0.2 units), not float
        # inside the wood or in a canopy cloud.  twig_enabled=False keeps
        # the legacy bark-attached leaf placement; with twigs, leaves move
        # to twig tips and the surface-hugging assertion no longer applies.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=44, twig_enabled=False),
        )
        segments_by_index = {s.index: s for s in self.tree.segments}
        sockets_by_id = {
            socket.id: socket
            for socket in self.tree.attachment_points
            if socket.kind == "leaf"
        }
        max_offset = 0.0
        for leaf in foliage_model.leaves:
            socket_id = leaf.attachment_id.split(":copy")[0]
            socket = sockets_by_id.get(socket_id)
            if socket is None:
                continue
            segment = segments_by_index.get(socket.segment_index)
            if segment is None:
                continue
            # Expected surface position = center + radius * normal
            radius = segment.start_radius + (
                segment.end_radius - segment.start_radius
            ) * socket.amount
            normal = socket.normal
            norm_len = (normal[0]**2 + normal[1]**2 + normal[2]**2) ** 0.5
            if norm_len < 1e-6:
                continue
            normal = (normal[0]/norm_len, normal[1]/norm_len, normal[2]/norm_len)
            surface_pos = (
                socket.position[0] + normal[0] * radius,
                socket.position[1] + normal[1] * radius,
                socket.position[2] + normal[2] * radius,
            )
            offset = (
                (leaf.position[0] - surface_pos[0]) ** 2
                + (leaf.position[1] - surface_pos[1]) ** 2
                + (leaf.position[2] - surface_pos[2]) ** 2
            ) ** 0.5
            max_offset = max(max_offset, offset)
        # Broadleaf has no floor clamp, so 0.2 is enough.
        self.assertLess(max_offset, 0.2)

    def test_leaf_cap_is_shared_across_willow_branches(self):
        # twig_enabled=False preserves the legacy per-segment leaf
        # distribution that saturates max_leaves; with twigs, leaves
        # come only from GrowthTips (far fewer sources) so the cap is
        # not reached.
        willow = generate_tree(
            TreeConfig.from_preset("willow_weeping", seed=17)
        )
        foliage_model = generate_foliage(
            willow,
            FoliageConfig(season="summer", seed=118, twig_enabled=False),
        )
        covered_segments = {
            leaf.source_segment for leaf in foliage_model.leaves
        }
        self.assertEqual(len(foliage_model.leaves), 12000)
        self.assertGreater(len(covered_segments), 1000)

    def test_non_round_presets_keep_foliage_anchored_to_branches(self):
        # All presets should keep leaves on the branch bark surface,
        # not floating in a volume cloud away from the branch skeleton.
        # twig_enabled=False keeps the legacy bark-attached placement;
        # with twigs, leaves move to twig tips and this assertion no
        # longer applies.
        for preset_key in (
            "conifer_pyramidal",
            "willow_weeping",
            "columnar_poplar",
        ):
            tree = generate_tree(TreeConfig.from_preset(preset_key, seed=17))
            foliage_model = generate_foliage(
                tree,
                FoliageConfig(season="summer", seed=118, twig_enabled=False),
            )
            segments_by_index = {s.index: s for s in tree.segments}
            sockets_by_id = {
                socket.id: socket
                for socket in tree.attachment_points
                if socket.kind == "leaf"
            }
            max_offset = 0.0
            for leaf in foliage_model.leaves:
                socket_id = leaf.attachment_id.split(":copy")[0]
                socket = sockets_by_id.get(socket_id)
                if socket is None:
                    continue
                segment = segments_by_index.get(socket.segment_index)
                if segment is None:
                    continue
                radius = segment.start_radius + (
                    segment.end_radius - segment.start_radius
                ) * socket.amount
                normal = socket.normal
                norm_len = (normal[0]**2 + normal[1]**2 + normal[2]**2) ** 0.5
                if norm_len < 1e-6:
                    continue
                normal = (normal[0]/norm_len, normal[1]/norm_len, normal[2]/norm_len)
                surface_pos = (
                    socket.position[0] + normal[0] * radius,
                    socket.position[1] + normal[1] * radius,
                    socket.position[2] + normal[2] * radius,
                )
                offset = (
                    (leaf.position[0] - surface_pos[0]) ** 2
                    + (leaf.position[1] - surface_pos[1]) ** 2
                    + (leaf.position[2] - surface_pos[2]) ** 2
                ) ** 0.5
                max_offset = max(max_offset, offset)
            # Willow's floor clamp can add a small Y nudge; allow 0.35.
            self.assertLess(max_offset, 0.35, preset_key)

    def test_willow_keeps_foliage_on_low_drooping_branches(self):
        willow = generate_tree(
            TreeConfig.from_preset("willow_weeping", seed=17)
        )
        foliage_model = generate_foliage(
            willow,
            FoliageConfig(season="summer", seed=118),
        )
        minimum, maximum = willow.bounds()
        # Willow branches naturally droop low; leaves anchored to those
        # branches should still populate the lower quarter of the tree.
        low_floor = minimum[1] + (maximum[1] - minimum[1]) * 0.25
        low_leaves = [
            leaf
            for leaf in foliage_model.leaves
            if leaf.position[1] < low_floor
        ]
        self.assertGreater(len(low_leaves), 50)
        self.assertGreater(
            len({leaf.source_segment for leaf in low_leaves}),
            20,
        )

    def test_spring_willow_flowers_cover_every_eligible_unique_tip(self):
        willow = generate_tree(
            TreeConfig.from_preset("willow_weeping", seed=17)
        )
        foliage_model = generate_foliage(
            willow,
            FoliageConfig(season="spring", seed=118),
        )
        eligible_tip_indices = set()
        seen_positions = set()
        for tip_index, tip in enumerate(willow.tips):
            position_key = tuple(round(value, 4) for value in tip.position)
            if position_key in seen_positions:
                continue
            seen_positions.add(position_key)
            eligible_tip_indices.add(tip_index)
        covered_tip_indices = {
            flower.source_tip for flower in foliage_model.flowers
        }
        self.assertEqual(covered_tip_indices, eligible_tip_indices)

    def test_flower_mesh_arrays_encode_wilted_petals_and_centers(self):
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="autumn",
                flower_density_multiplier=5.0,
                seed=6,
            ),
        )
        self.assertGreater(len(foliage_model.flowers), 0)
        self.assertGreater(foliage_model.flowers[0].wilt, 0.7)
        petal_groups, centers, _ = build_flower_mesh_groups(foliage_model)
        petal_points = sum(len(arrays[0]) for arrays in petal_groups.values())
        petal_faces = sum(len(arrays[1]) for arrays in petal_groups.values())
        self.assertEqual(petal_points, len(foliage_model.flowers) * 20)
        self.assertEqual(petal_faces, len(foliage_model.flowers) * 10)
        # Center arrays: 3 pedicel vertices + 6 octahedron vertices = 9
        # Center faces: 1 pedicel face + 8 octahedron faces = 9
        self.assertEqual(len(centers[0]), len(foliage_model.flowers) * 9)
        self.assertEqual(len(centers[1]), len(foliage_model.flowers) * 9)


class WoodyFlowerTests(unittest.TestCase):
    """Verify species-accurate procedural woody blossoms (peach/cherry/pear/plum)."""

    @classmethod
    def setUpClass(cls):
        cls.tree = generate_tree(
            TreeConfig.from_preset("broadleaf_round", branch_levels=3, seed=31)
        )

    def test_woody_flower_specs_cover_all_species(self):
        self.assertEqual(
            set(WOODY_FLOWER_SPECS.keys()),
            {"peach", "cherry", "pear", "plum", "willow"},
        )
        self.assertEqual(set(WOODY_LEAF_SPECS.keys()), set(WOODY_FLOWER_SPECS.keys()))
        for spec in WOODY_FLOWER_SPECS.values():
            self.assertEqual(spec.petal_count, 5)
            self.assertGreater(spec.petal_ratio, 0.0)
        # Cherry is the only species with the deep signature V-notch.
        self.assertGreater(WOODY_FLOWER_SPECS["cherry"].petal_notch, 0.1)
        # Pear petals are perfectly round with no notch.
        self.assertEqual(WOODY_FLOWER_SPECS["pear"].petal_notch, 0.0)
        # Peach and plum have shallow apical notches (botanically
        # distinct from both cherry's V-notch and pear's round tip).
        for key in ("peach", "plum"):
            notch = WOODY_FLOWER_SPECS[key].petal_notch
            self.assertGreater(notch, 0.0, "{} should have a shallow notch".format(key))
            self.assertLess(
                notch, WOODY_FLOWER_SPECS["cherry"].petal_notch,
                "{} notch should be shallower than cherry".format(key),
            )
        # Pear has the dark-purple center that distinguishes it in the field.
        pear_center = WOODY_FLOWER_SPECS["pear"].center_color
        self.assertLess(max(pear_center), 0.3)

    def test_invalid_woody_species_raises(self):
        with self.assertRaises(ValueError):
            FoliageConfig(season="spring", woody_species="rose")

    def test_woody_species_propagates_to_instances(self):
        for species in ("peach", "cherry", "pear", "plum"):
            foliage_model = generate_foliage(
                self.tree,
                FoliageConfig(season="spring", seed=42, woody_species=species),
            )
            self.assertTrue(foliage_model.flowers)
            self.assertTrue(foliage_model.leaves)
            self.assertTrue(
                all(flower.species == species for flower in foliage_model.flowers)
            )
            self.assertTrue(
                all(leaf.species == species for leaf in foliage_model.leaves)
            )

    def test_woody_species_overrides_season_palette(self):
        base = generate_foliage(self.tree, FoliageConfig(season="spring", seed=42))
        cherry = generate_foliage(
            self.tree,
            FoliageConfig(season="spring", seed=42, woody_species="cherry"),
        )
        # Cherry palette must differ from the generic spring palette.
        self.assertNotEqual(
            cherry.profile.flower_palette,
            base.profile.flower_palette,
        )
        self.assertEqual(
            cherry.profile.flower_palette,
            WOODY_FLOWER_SPECS["cherry"].palette,
        )
        self.assertEqual(
            cherry.profile.center_color,
            WOODY_FLOWER_SPECS["cherry"].center_color,
        )

    def test_cherry_blossoms_emit_v_notched_petals(self):
        """Cherry blossoms emit double-sided V-notched petals.

        With the V-notch support station (2026-07): 11 stations = 12
        cross-sections × 5 verts (edge_l, upper_l, mid, upper_r,
        edge_r) = 60 front verts + 60 back verts = 120 verts/petal.
        Faces per petal: 11 segments × 8 tris (front) + 11 × 8 (back)
        + 11 × 2 (left chain) + 11 × 2 (right chain) + 8 (base cap)
        = 228 faces.  Per flower: 5 petals × 120 = 600 verts, 5 × 228
        = 1140 faces (pedicel moved to sepal arrays).
        """
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="cherry",
                flower_density_multiplier=5.0,
            ),
        )
        self.assertGreater(len(foliage_model.flowers), 0)
        petal_groups, _, _ = build_flower_mesh_groups(foliage_model)
        petal_points = sum(len(a[0]) for a in petal_groups.values())
        petal_faces = sum(len(a[1]) for a in petal_groups.values())
        self.assertEqual(petal_points, len(foliage_model.flowers) * 600)
        self.assertEqual(petal_faces, len(foliage_model.flowers) * 1140)

    def test_non_cherry_woody_species_emit_plain_petals(self):
        """Peach/pear/plum emit double-sided petals with a single tip vertex.

        Peach and plum have shallow apical notches (notch > 0.02),
        which triggers the 11-station support mesh (600 verts / 1140
        faces per flower).  Pear has notch=0.0 and stays at 9 stations
        (500 verts / 940 faces per flower, 2026-07).
        """
        _EXPECTED = {
            "peach": (600, 1140),
            "pear": (500, 940),
            "plum": (600, 1140),
        }
        for species in ("peach", "pear", "plum"):
            foliage_model = generate_foliage(
                self.tree,
                FoliageConfig(
                    season="spring", seed=42, woody_species=species,
                    flower_density_multiplier=5.0,
                ),
            )
            self.assertGreater(len(foliage_model.flowers), 0, species)
            petal_groups, _, _ = build_flower_mesh_groups(foliage_model)
            petal_points = sum(len(a[0]) for a in petal_groups.values())
            petal_faces = sum(len(a[1]) for a in petal_groups.values())
            exp_v, exp_f = _EXPECTED[species]
            self.assertEqual(
                petal_points, len(foliage_model.flowers) * exp_v, species
            )
            self.assertEqual(
                petal_faces, len(foliage_model.flowers) * exp_f, species
            )

    def test_woody_flowers_emit_stamens_in_center_mesh(self):
        """Woody flower center + sepal meshes have the expected topology.

        Peach has 12 stamens (spec.stamen_count=12).  Each stamen is
        split into a filament (17 verts / 24 faces — octagonal cross
        section, segments=8, rings=1) + anther (17 verts / 24 faces)
        = 34 verts / 48 faces per stamen.

        Center mesh per flower (sepals now in a dedicated sepal mesh):
        receptacle (6v/8f) + N stamens (34v/48f each) + pistil
        (ovary 6v/8f + style 9v/12f + stigma 6v/8f = 21v/28f).

        Sepal mesh per flower (2026-07): pedicel cylinder (16v/25f)
        + 5 sepals (8v/6f each = 40v/30f) = 56v/55f.  Sepals are 3-station
        curved quad strips (4 stations × 2 edge verts = 8 verts, 3 segments
        × 2 tris = 6 faces) that arc outward then reflex back.
        """
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="peach",
                flower_density_multiplier=5.0,
            ),
        )
        _, centers, sepals = build_flower_mesh_groups(foliage_model)
        center_points, center_counts, _ = centers
        sepal_points, sepal_counts, _ = sepals
        stamen_count = WOODY_FLOWER_SPECS["peach"].stamen_count
        # Center: receptacle (6v/8f) + stamens (34v/48f each)
        # + pistil (ovary 6v/8f + style 9v/12f + stigma 6v/8f = 21v/28f).
        expected_verts = 6 + stamen_count * 34 + 21
        expected_faces = 8 + stamen_count * 48 + 28
        self.assertEqual(
            len(center_points), len(foliage_model.flowers) * expected_verts
        )
        self.assertEqual(
            len(center_counts), len(foliage_model.flowers) * expected_faces
        )
        # Sepal + pedicel + calyx tube (2026-07):
        # pedicel cylinder (16v/25f) + calyx tube (13v/18f)
        # + 5 curved strips (8v/6f each = 40v/30f) = 69v/73f per flower.
        self.assertEqual(
            len(sepal_points), len(foliage_model.flowers) * 69
        )
        self.assertEqual(
            len(sepal_counts), len(foliage_model.flowers) * 73
        )

    def test_woody_leaf_silhouette_uses_botanical_ratio(self):
        """Peach leaves are narrow (lanceolate), pear leaves are wide (elliptic)."""
        peach = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=7, woody_species="peach"),
        )
        pear = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=7, woody_species="pear"),
        )
        peach_ratio = sum(l.length / l.width for l in peach.leaves) / len(peach.leaves)
        pear_ratio = sum(l.length / l.width for l in pear.leaves) / len(pear.leaves)
        # Peach (lanceolate, ratio 3.5) must be narrower than pear (elliptic, 1.8).
        self.assertGreater(peach_ratio, pear_ratio * 1.5)

    def test_woody_leaf_mesh_emits_subdivided_topology(self):
        """Species-accurate leaves emit a cylindrical petiole + subdivided blade.

        Per leaf: 5-sided petiole cylinder (16 verts / 25 faces: 5 cap
        tris + 2 rings * 5 segs * 2 tris) + 6 blade stations * 3 verts
        (18 verts / 20 faces: 5 quads * 2 tris * 2 sides) = 34 verts /
        45 faces.  The blade is subdivided along the midrib with
        serrated margins so the central vein ridge and sawtooth edges
        are visible under lighting.
        """
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=7, woody_species="cherry"),
        )
        groups = build_leaf_mesh_groups(foliage_model)
        total_points = sum(len(arrays[0]) for arrays in groups.values())
        total_faces = sum(len(arrays[1]) for arrays in groups.values())
        self.assertEqual(total_points, len(foliage_model.leaves) * 34)
        self.assertEqual(total_faces, len(foliage_model.leaves) * 45)

    def test_woody_species_none_preserves_legacy_behavior(self):
        """Default woody_species=None must match the original flower topology."""
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="autumn", seed=6, flower_density_multiplier=5.0,
            ),
        )
        self.assertTrue(foliage_model.flowers)
        self.assertIsNone(foliage_model.flowers[0].species)
        petal_groups, centers, _ = build_flower_mesh_groups(foliage_model)
        petal_points = sum(len(a[0]) for a in petal_groups.values())
        # Legacy 5-petal * 4 verts = 20
        self.assertEqual(petal_points, len(foliage_model.flowers) * 20)

    def test_woody_flowering_seasons_match_real_phenology(self):
        """Species-accurate flowering periods (Flora of China / eflora).

        Peach (P. persica), cherry (P. serrulata) and pear (Pyrus spp.)
        bloom only in spring (Mar-Apr).  Plum (P. mume) is the iconic
        "winter plum"  -  it blooms in late winter (Jan-Feb) through
        early spring (Mar).  No Rosaceae species in this catalog
        produces flowers in summer or autumn, so the foliage generator
        must emit zero blossoms for those seasons regardless of the
        UI's flower_density_multiplier.
        """
        # Phenology declarations on the spec objects themselves.
        for species in ("peach", "cherry", "pear"):
            spec = WOODY_FLOWER_SPECS[species]
            self.assertEqual(
                spec.flowering_seasons, ("spring",),
                "{} should flower only in spring".format(species),
            )
        plum_spec = WOODY_FLOWER_SPECS["plum"]
        self.assertEqual(plum_spec.flowering_seasons, ("winter", "spring"))
        self.assertAlmostEqual(plum_spec.season_flower_density["winter"], 0.20)
        self.assertAlmostEqual(plum_spec.season_flower_wilt["winter"], 0.10)

        # End-to-end: no flowers emitted out of season, even with the
        # density multiplier cranked up.  This is the regression that
        # motivated the fix  -  previously autumn produced wilted
        # blossoms for all four species, which is botanically wrong.
        for species in ("peach", "cherry", "pear", "plum"):
            for season in ("summer", "autumn"):
                foliage_model = generate_foliage(
                    self.tree,
                    FoliageConfig(
                        season=season, seed=42, woody_species=species,
                        flower_density_multiplier=5.0,
                    ),
                )
                self.assertEqual(
                    len(foliage_model.flowers), 0,
                    "{} should have no flowers in {}".format(species, season),
                )

        # Plum is the only species that flowers in winter.  The other
        # three must emit zero blossoms in winter (the season profile's
        # default flower_density=0.0 already enforces this, but the
        # phenology filter makes it explicit and species-aware).
        for species in ("peach", "cherry", "pear"):
            foliage_model = generate_foliage(
                self.tree,
                FoliageConfig(
                    season="winter", seed=42, woody_species=species,
                    flower_density_multiplier=5.0,
                ),
            )
            self.assertEqual(
                len(foliage_model.flowers), 0,
                "{} should have no flowers in winter".format(species),
            )

        # Plum's winter blooms: sparse (density 0.20, ~38% of spring
        # peak) and fresh (wilt 0.10, not the season default 1.0).
        plum_winter = generate_foliage(
            self.tree,
            FoliageConfig(
                season="winter", seed=42, woody_species="plum",
            ),
        )
        self.assertGreater(len(plum_winter.flowers), 0)
        self.assertLess(
            plum_winter.flowers[0].wilt, 0.3,
            "plum winter flowers should be fresh (low wilt), not the "
            "season default 1.0 which assumes dead residue",
        )
        # Plum spring should still bloom (peak), and produce more
        # flowers than winter (early flush).
        plum_spring = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="plum",
            ),
        )
        self.assertGreater(len(plum_spring.flowers), len(plum_winter.flowers))

    def test_leaves_near_flowers_are_shrunk_by_avoidance(self):
        """Leaves within the flower-avoidance radius must be visibly smaller.

        The flower-avoidance feature shrinks leaves near each flower
        socket so the (intentionally enlarged) leaves do not visually
        bury the blossoms.  We verify this by comparing the average
        leaf length of leaves within the avoidance core radius against
        those well outside the fade radius  -  the near-flower leaves
        must be substantially smaller.
        """
        from src.foliage import (
            FLOWER_AVOIDANCE_CORE_RADIUS,
            FLOWER_AVOIDANCE_FADE_RADIUS,
            FLOWER_AVOIDANCE_MIN_SCALE,
            _flower_avoidance_scale,
        )

        # Sanity-check the scale function directly.
        flower_pos = (1.0, 2.0, 3.0)
        self.assertEqual(
            _flower_avoidance_scale(flower_pos, [flower_pos]),
            FLOWER_AVOIDANCE_MIN_SCALE,
        )
        far_pos = (
            flower_pos[0] + FLOWER_AVOIDANCE_FADE_RADIUS + 0.5,
            flower_pos[1],
            flower_pos[2],
        )
        self.assertEqual(_flower_avoidance_scale(far_pos, [flower_pos]), 1.0)
        # Empty flower list -> no avoidance.
        self.assertEqual(_flower_avoidance_scale(flower_pos, []), 1.0)

        # End-to-end: use a woody species so leaf_size_factor is the
        # enlarged real-ratio value (>2.0).  Spring gives the most
        # flowers so the avoidance effect is measurable.  twig_enabled
        # =False keeps leaves on the branch bark next to flowers so
        # the avoidance scaling is actually exercised (with twigs,
        # leaves sit at twig tips far from flowers and avoidance is
        # not triggered).
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="peach",
                twig_enabled=False,
            ),
        )
        flower_positions = [
            (flower.position[0], flower.position[1], flower.position[2])
            for flower in foliage_model.flowers
        ]
        self.assertGreater(len(flower_positions), 0)

        # Classify leaves by distance to nearest flower.
        near_lengths = []
        far_lengths = []
        for leaf in foliage_model.leaves:
            lx, ly, lz = leaf.position
            min_dist = min(
                ((lx - fx) ** 2 + (ly - fy) ** 2 + (lz - fz) ** 2) ** 0.5
                for fx, fy, fz in flower_positions
            )
            # leaf.length is the blade length after all scaling.
            if min_dist <= FLOWER_AVOIDANCE_CORE_RADIUS:
                near_lengths.append(leaf.length)
            elif min_dist >= FLOWER_AVOIDANCE_FADE_RADIUS:
                far_lengths.append(leaf.length)

        # We need enough samples on both sides for a meaningful mean.
        self.assertGreater(
            len(near_lengths), 0,
            "expected at least one leaf near a flower",
        )
        self.assertGreater(
            len(far_lengths), 0,
            "expected at least one leaf far from any flower",
        )
        near_mean = sum(near_lengths) / len(near_lengths)
        far_mean = sum(far_lengths) / len(far_lengths)
        # Near-flower leaves should be substantially smaller than far
        # ones.  The theoretical ratio is FLOWER_AVOIDANCE_MIN_SCALE
        # (0.40) at the very core, but the near bucket includes the
        # smoothstep transition zone so we use a looser threshold.
        self.assertLess(
            near_mean, far_mean * 0.75,
            "near-flower leaves (mean={:.3f}) should be <75% of far "
            "leaves (mean={:.3f})".format(near_mean, far_mean),
        )


class TwigGenerationTests(unittest.TestCase):
    """Dedicated tests for the visible twig (fine shoot) system.

    These tests cover the twig-enabled path of ``generate_foliage``:
    one curved twig per GrowthTip, leaves at twig tips, botanical
    radius ratio, and the twig mesh topology.  The legacy per-segment
    leaf path is covered by the surface-hugging tests above (which
    pass ``twig_enabled=False``).
    """

    @classmethod
    def setUpClass(cls):
        cls.tree = generate_tree(
            TreeConfig.from_preset("broadleaf_round", branch_levels=3, seed=31)
        )

    def test_twig_enabled_produces_twig_instances(self):
        # Default config has twig_enabled=True; verify twigs are built.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=44),
        )
        self.assertGreater(len(foliage_model.twigs), 0)
        for twig in foliage_model.twigs:
            self.assertIsInstance(twig, TwigInstance)
            # Twig base must sit at a GrowthTip position.
            self.assertEqual(len(twig.start), 3)
            # Twig length and radii must be positive.
            self.assertGreater(twig.length, 0.0)
            self.assertGreater(twig.base_radius, 0.0)
            self.assertGreater(twig.tip_radius, 0.0)
            # Tip radius is tapered (smaller than base).
            self.assertLess(twig.tip_radius, twig.base_radius)

    def test_twig_disabled_produces_no_twigs(self):
        # twig_enabled=False restores the legacy behavior: no twigs.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=44, twig_enabled=False),
        )
        self.assertEqual(len(foliage_model.twigs), 0)

    def test_twig_count_matches_eligible_growth_tips(self):
        # Each eligible GrowthTip grows exactly one twig.  Compute the
        # expected count by replicating the canopy_base + depth filter.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=44),
        )
        minimum_bounds, maximum_bounds = self.tree.bounds()
        tree_height = maximum_bounds[1] - minimum_bounds[1]
        canopy_base = minimum_bounds[1] + tree_height * 0.18
        maximum_depth = self.tree.maximum_depth()
        minimum_leaf_depth = max(0, maximum_depth - 2)
        seen = set()
        expected = 0
        for tip in self.tree.tips:
            key = tuple(round(v, 4) for v in tip.position)
            if key in seen:
                continue
            seen.add(key)
            if tip.position[1] < canopy_base:
                continue
            if tip.depth < minimum_leaf_depth:
                continue
            expected += 1
        self.assertEqual(len(foliage_model.twigs), expected)

    def test_twig_radius_matches_botanical_ratio(self):
        # Twig base radius = leaf_length * twig_radius_ratio.  With the
        # default ratio 0.035 (visible default, 2026-07), verify the
        # actual ratio on generated twigs stays within tolerance of the
        # configured value.
        config = FoliageConfig(
            season="spring", seed=42, woody_species="peach",
            twig_enabled=True, twig_radius_ratio=0.035,
        )
        foliage_model = generate_foliage(self.tree, config)
        self.assertGreater(len(foliage_model.twigs), 0)
        # Representative leaf length used to size twigs.
        profile = get_season("spring")
        leaf_length = profile.leaf_size * config.leaf_size_multiplier
        leaf_length *= WOODY_LEAF_SPECS["peach"].leaf_size_factor
        for twig in foliage_model.twigs:
            ratio = twig.base_radius / leaf_length
            self.assertAlmostEqual(ratio, 0.035, places=3)

    def test_twig_leaf_attachment_ids_differ_from_legacy(self):
        # Twig leaves use "twig:N:leafM" ids; legacy leaves use
        # "leaf:...:copyN".  With the default twig_leaf_ratio=0.7,
        # verify BOTH attachment kinds coexist (mixed placement):
        # the majority on twigs, the remainder on bark.  ratio=1.0
        # is exercised by the dedicated all-on-twig test below.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=44, twig_enabled=True),
        )
        twig_leaf_count = sum(
            1 for leaf in foliage_model.leaves
            if leaf.attachment_id.startswith("twig:")
        )
        bark_leaf_count = len(foliage_model.leaves) - twig_leaf_count
        self.assertGreater(twig_leaf_count, 0)
        self.assertGreater(bark_leaf_count, 0)

    def test_twig_leaf_ratio_one_places_all_leaves_on_twigs(self):
        # twig_leaf_ratio=1.0 restores the prior all-on-twig behavior:
        # every leaf carries a "twig:" attachment id and no leaf sits
        # on the main branch bark.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="summer", seed=44,
                twig_enabled=True, twig_leaf_ratio=1.0,
            ),
        )
        twig_leaf_count = sum(
            1 for leaf in foliage_model.leaves
            if leaf.attachment_id.startswith("twig:")
        )
        self.assertEqual(twig_leaf_count, len(foliage_model.leaves))

    def test_twig_leaf_ratio_zero_places_all_leaves_on_bark(self):
        # twig_leaf_ratio=0.0 with twig_enabled=True: twigs are still
        # generated (visible fine shoots) but NO leaves attach to them;
        # all leaves go to the bark-placement path.  This decouples
        # twig visibility from leaf placement.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="summer", seed=44,
                twig_enabled=True, twig_leaf_ratio=0.0,
            ),
        )
        # Twigs exist (visibility is independent of leaf placement).
        self.assertGreater(len(foliage_model.twigs), 0)
        # No leaf carries a twig: prefix; all are bark-attached.
        twig_leaf_count = sum(
            1 for leaf in foliage_model.leaves
            if leaf.attachment_id.startswith("twig:")
        )
        self.assertEqual(twig_leaf_count, 0)

    def test_twig_mesh_arrays_have_expected_topology(self):
        # Each twig: (rings+1) rings * segments vertices + 1 base cap
        # vertex = 7*8+1 = 57 vertices.  Faces: segments base cap
        # triangles + rings*segments*2 side triangles = 8 + 6*8*2 = 104.
        # Connects: 3 * faces = 312.  (Updated 2026-07: segments 6->8,
        # rings 4->6 for smoother visible twigs at the larger radius.)
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=44),
        )
        arrays = build_twig_mesh_arrays(foliage_model)
        self.assertIn(0, arrays)
        points, counts, connects = arrays[0]
        twig_count = len(foliage_model.twigs)
        self.assertEqual(len(points), twig_count * 57)
        self.assertEqual(len(counts), twig_count * 104)
        self.assertEqual(len(connects), twig_count * 312)

    def test_twigs_reproducible_with_same_seed(self):
        # Same seed must produce identical twig geometry.
        first = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=77),
        )
        second = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=77),
        )
        self.assertEqual(
            [(t.start, t.length, t.base_radius) for t in first.twigs],
            [(t.start, t.length, t.base_radius) for t in second.twigs],
        )

    def test_twig_curvature_affects_tip_position(self):
        # Non-zero curvature should offset the tip sideways from the
        # straight-axis endpoint.  Verify the tip is NOT at
        # start + axis * length.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=44, twig_curvature=0.5),
        )
        for twig in foliage_model.twigs:
            straight_tip = (
                twig.start[0] + twig.axis[0] * twig.length,
                twig.start[1] + twig.axis[1] * twig.length,
                twig.start[2] + twig.axis[2] * twig.length,
            )
            actual_tip = twig.tip_position()
            # The bend should move the tip away from the straight-line
            # endpoint by roughly bend_strength (curvature * length).
            offset = (
                (actual_tip[0] - straight_tip[0]) ** 2
                + (actual_tip[1] - straight_tip[1]) ** 2
                + (actual_tip[2] - straight_tip[2]) ** 2
            ) ** 0.5
            self.assertGreater(offset, 0.0)


class TwigFlowerPlacementTests(unittest.TestCase):
    """Verify botanical flower-on-twig placement (2026-07).

    When twig_enabled=True and a woody species is selected, flowers must
    grow from twigs following species-specific morphology:
      - Peach/plum (solitary/fascicled): flowers on twig NODES (along
        the sides at t=0.35/0.55/0.75), not the apex.
      - Cherry/pear (corymbose): flowers at twig TIP in an umbel/corymb.
    twig_enabled=False preserves the legacy bark-surface placement.
    """

    @classmethod
    def setUpClass(cls):
        cls.tree = generate_tree(
            TreeConfig.from_preset("broadleaf_round", branch_levels=3, seed=31)
        )

    def test_flowers_attach_to_twigs_when_enabled(self):
        # With twigs enabled, flowers must carry "twig:" attachment ids
        # (not the legacy "flower:...:copyN" bark ids).  This confirms
        # the new botanical path is exercised.
        for species in ("peach", "cherry", "pear", "plum"):
            foliage_model = generate_foliage(
                self.tree,
                FoliageConfig(
                    season="spring", seed=42, woody_species=species,
                    flower_density_multiplier=3.0,
                ),
            )
            self.assertGreater(len(foliage_model.flowers), 0, species)
            for flower in foliage_model.flowers:
                self.assertTrue(
                    flower.attachment_id.startswith("twig:"),
                    "{} flower should attach to twig, got {}".format(
                        species, flower.attachment_id
                    ),
                )

    def test_twig_disabled_preserves_bark_flower_attachment(self):
        # twig_enabled=False: flowers keep the legacy "flower:...:copyN"
        # bark-surface attachment ids (regression guard for the willow
        # flower-coverage test path).
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="peach",
                flower_density_multiplier=3.0,
                twig_enabled=False,
            ),
        )
        self.assertGreater(len(foliage_model.flowers), 0)
        for flower in foliage_model.flowers:
            self.assertTrue(
                flower.attachment_id.startswith("flower:"),
                "twig-disabled flower should attach to bark, got {}".format(
                    flower.attachment_id
                ),
            )

    def test_peach_flowers_grow_from_twig_nodes_not_apex(self):
        # Peach (solitary): flowers emerge from lateral nodes at
        # t=0.35/0.55/0.75, NOT from the twig apex (t=1.0).  Verify by
        # checking that flower positions are NOT clustered at the tip
        # endpoint  -  at least one flower sits at a node position
        # closer to the base than the apex.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="peach",
                flower_density_multiplier=5.0,
            ),
        )
        self.assertGreater(len(foliage_model.flowers), 0)
        # Build a set of twig tip positions for comparison.
        twig_tip_positions = set()
        for twig in foliage_model.twigs:
            tip = twig.tip_position()
            twig_tip_positions.add(
                tuple(round(value, 3) for value in tip)
            )
        # At least one flower should NOT be at a twig tip (it's on a
        # lateral node instead).
        node_flower_count = 0
        for flower in foliage_model.flowers:
            flower_key = tuple(round(value, 3) for value in flower.position)
            if flower_key not in twig_tip_positions:
                node_flower_count += 1
        self.assertGreater(
            node_flower_count, 0,
            "peach flowers should include node-placed (not all at tips)",
        )

    def test_cherry_flowers_cluster_at_twig_tips(self):
        # Cherry (corymbose): flowers cluster at the twig tip in an
        # umbel.  Verify the majority of flowers sit NEAR a twig tip
        # (within the corymb radius), unlike peach which spreads along
        # lateral nodes.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="cherry",
                flower_density_multiplier=5.0,
            ),
        )
        self.assertGreater(len(foliage_model.flowers), 0)
        tip_positions = [twig.tip_position() for twig in foliage_model.twigs]
        near_tip_count = 0
        for flower in foliage_model.flowers:
            for tip_pos in tip_positions:
                distance = (
                    (flower.position[0] - tip_pos[0]) ** 2
                    + (flower.position[1] - tip_pos[1]) ** 2
                    + (flower.position[2] - tip_pos[2]) ** 2
                ) ** 0.5
                # Cherry corymb: peduncle_ratio=0.35 (forward) +
                # pedicel_ratio=0.55 (radial) + fan_radius up to ~0.55*size
                # = total up to ~1.45*size from the tip.  Use 2.5x size
                # as the "near tip" threshold to capture the full corymb
                # fan-out without being so loose that node-placed peach
                # flowers would also pass.
                if distance < flower.size * 2.5:
                    near_tip_count += 1
                    break
        # At least 40% of cherry flowers should be near a tip.  The
        # threshold is deliberately below 50% because the corymb fan-out
        # plus peduncle forward extension can push some flowers past the
        # 2.5x threshold, and we only need to distinguish from peach's
        # node-spread pattern (where most flowers are far from any tip).
        self.assertGreater(
            near_tip_count, len(foliage_model.flowers) * 2 // 5,
            "cherry flowers should cluster near twig tips",
        )

    def test_node_flower_count_scales_with_density(self):
        # Higher flower_density_multiplier should produce more flowers
        # on twigs (the new path respects the density budget just like
        # the legacy path).
        sparse = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="peach",
                flower_density_multiplier=1.0,
            ),
        )
        dense = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring", seed=42, woody_species="peach",
                flower_density_multiplier=5.0,
            ),
        )
        self.assertGreater(len(dense.flowers), len(sparse.flowers))

    def test_flower_placement_is_reproducible(self):
        # Same seed -> identical flower positions (stable RNG contract).
        first = generate_foliage(
            self.tree,
            FoliageConfig(season="spring", seed=42, woody_species="cherry"),
        )
        second = generate_foliage(
            self.tree,
            FoliageConfig(season="spring", seed=42, woody_species="cherry"),
        )
        self.assertEqual(
            [(f.position, f.size) for f in first.flowers],
            [(f.position, f.size) for f in second.flowers],
        )


if __name__ == "__main__":
    unittest.main()
