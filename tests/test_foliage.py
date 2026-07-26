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
    WOODY_FLOWER_SPECS,
    WOODY_LEAF_SPECS,
    generate_foliage,
    get_season,
)
from src.maya_foliage import build_flower_mesh_groups, build_leaf_mesh_groups


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
        small = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring",
                leaf_size_multiplier=0.5,
                flower_size_multiplier=0.5,
                seed=19,
            ),
        )
        large = generate_foliage(
            self.tree,
            FoliageConfig(
                season="spring",
                leaf_size_multiplier=1.5,
                flower_size_multiplier=1.5,
                seed=19,
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
        # inside the wood or in a canopy cloud.
        foliage_model = generate_foliage(
            self.tree,
            FoliageConfig(season="summer", seed=44),
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
        willow = generate_tree(
            TreeConfig.from_preset("willow_weeping", seed=17)
        )
        foliage_model = generate_foliage(
            willow,
            FoliageConfig(season="summer", seed=118),
        )
        covered_segments = {
            leaf.source_segment for leaf in foliage_model.leaves
        }
        self.assertEqual(len(foliage_model.leaves), 12000)
        self.assertGreater(len(covered_segments), 1000)

    def test_non_round_presets_keep_foliage_anchored_to_branches(self):
        # All presets should keep leaves on the branch bark surface,
        # not floating in a volume cloud away from the branch skeleton.
        for preset_key in (
            "conifer_pyramidal",
            "willow_weeping",
            "columnar_poplar",
        ):
            tree = generate_tree(TreeConfig.from_preset(preset_key, seed=17))
            foliage_model = generate_foliage(
                tree,
                FoliageConfig(season="summer", seed=118),
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

    def test_woody_flower_specs_cover_four_species(self):
        self.assertEqual(
            set(WOODY_FLOWER_SPECS.keys()),
            {"peach", "cherry", "pear", "plum"},
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


if __name__ == "__main__":
    unittest.main()
