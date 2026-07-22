from __future__ import division

import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core import TreeConfig, generate_tree
from src.foliage import FoliageConfig, generate_foliage, get_season
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
        self.assertEqual(total_points, len(foliage_model.leaves) * 5)
        self.assertEqual(total_faces, len(foliage_model.leaves) * 4)
        self.assertEqual(total_connects, len(foliage_model.leaves) * 12)

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

    def test_canopy_spread_moves_foliage_away_from_branch_skeleton(self):
        compact = generate_foliage(
            self.tree,
            FoliageConfig(
                season="summer",
                canopy_spread_multiplier=0.0,
                seed=44,
            ),
        )
        fluffy = generate_foliage(
            self.tree,
            FoliageConfig(
                season="summer",
                canopy_spread_multiplier=1.5,
                seed=44,
            ),
        )
        compact_x = max(leaf.position[0] for leaf in compact.leaves) - min(
            leaf.position[0] for leaf in compact.leaves
        )
        fluffy_x = max(leaf.position[0] for leaf in fluffy.leaves) - min(
            leaf.position[0] for leaf in fluffy.leaves
        )
        compact_z = max(leaf.position[2] for leaf in compact.leaves) - min(
            leaf.position[2] for leaf in compact.leaves
        )
        fluffy_z = max(leaf.position[2] for leaf in fluffy.leaves) - min(
            leaf.position[2] for leaf in fluffy.leaves
        )
        self.assertGreater(fluffy_x, compact_x + 1.0)
        self.assertGreater(fluffy_z, compact_z + 1.0)

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

    def test_non_round_presets_form_volume_around_their_branch_skeletons(self):
        for preset_key in (
            "conifer_pyramidal",
            "willow_weeping",
            "columnar_poplar",
        ):
            tree = generate_tree(TreeConfig.from_preset(preset_key, seed=17))
            compact = generate_foliage(
                tree,
                FoliageConfig(
                    season="summer",
                    canopy_spread_multiplier=0.0,
                    seed=118,
                ),
            )
            fluffy = generate_foliage(
                tree,
                FoliageConfig(
                    season="summer",
                    canopy_spread_multiplier=1.0,
                    seed=118,
                ),
            )
            compact_x = max(leaf.position[0] for leaf in compact.leaves) - min(
                leaf.position[0] for leaf in compact.leaves
            )
            fluffy_x = max(leaf.position[0] for leaf in fluffy.leaves) - min(
                leaf.position[0] for leaf in fluffy.leaves
            )
            compact_z = max(leaf.position[2] for leaf in compact.leaves) - min(
                leaf.position[2] for leaf in compact.leaves
            )
            fluffy_z = max(leaf.position[2] for leaf in fluffy.leaves) - min(
                leaf.position[2] for leaf in fluffy.leaves
            )
            self.assertGreater(fluffy_x, compact_x + 1.0, preset_key)
            self.assertGreater(fluffy_z, compact_z + 1.0, preset_key)

    def test_willow_keeps_foliage_on_low_drooping_branches(self):
        willow = generate_tree(
            TreeConfig.from_preset("willow_weeping", seed=17)
        )
        foliage_model = generate_foliage(
            willow,
            FoliageConfig(season="summer", seed=118),
        )
        minimum, maximum = willow.bounds()
        former_canopy_floor = minimum[1] + (maximum[1] - minimum[1]) * 0.12
        low_leaves = [
            leaf
            for leaf in foliage_model.leaves
            if leaf.position[1] < former_canopy_floor
        ]
        self.assertGreater(len(low_leaves), 500)
        self.assertGreater(
            len({leaf.source_segment for leaf in low_leaves}),
            100,
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
        petal_groups, centers = build_flower_mesh_groups(foliage_model)
        petal_points = sum(len(arrays[0]) for arrays in petal_groups.values())
        petal_faces = sum(len(arrays[1]) for arrays in petal_groups.values())
        self.assertEqual(petal_points, len(foliage_model.flowers) * 20)
        self.assertEqual(petal_faces, len(foliage_model.flowers) * 10)
        self.assertEqual(len(centers[0]), len(foliage_model.flowers) * 6)
        self.assertEqual(len(centers[1]), len(foliage_model.flowers) * 8)


if __name__ == "__main__":
    unittest.main()
