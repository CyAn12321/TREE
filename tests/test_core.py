from __future__ import division

import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core import TreeConfig, generate_tree, list_presets
from src.maya_mesh import build_mesh_arrays


class TreeGeneratorTests(unittest.TestCase):
    def test_required_parameters_override_preset(self):
        config = TreeConfig.from_preset(
            "broadleaf_round",
            trunk_radius=0.91,
            branch_levels=3,
            branches_per_node=5,
            branch_angle=41.0,
            seed=5,
        )
        model = generate_tree(config)
        self.assertAlmostEqual(model.segments[0].start_radius, 0.91)
        self.assertLessEqual(model.maximum_depth(), 2)
        self.assertEqual(model.config.branches_per_node, 5)
        self.assertEqual(model.config.branch_angle, 41.0)

    def test_branch_count_changes_generated_fork_quantity(self):
        sparse = generate_tree(
            TreeConfig.from_preset(
                "broadleaf_round",
                branch_levels=3,
                branches_per_node=1,
                seed=23,
            )
        )
        dense = generate_tree(
            TreeConfig.from_preset(
                "broadleaf_round",
                branch_levels=3,
                branches_per_node=5,
                seed=23,
            )
        )
        self.assertGreater(len(dense.segments), len(sparse.segments) * 2)
        self.assertGreater(len(dense.tips), len(sparse.tips) * 2)

    def test_internode_density_adds_branches_without_changing_fork_count(self):
        sparse = generate_tree(
            TreeConfig.from_preset(
                "broadleaf_round",
                branch_levels=4,
                branches_per_node=2,
                internode_branch_density=0.0,
                seed=23,
            )
        )
        dense = generate_tree(
            TreeConfig.from_preset(
                "broadleaf_round",
                branch_levels=4,
                branches_per_node=2,
                internode_branch_density=0.8,
                seed=23,
            )
        )
        self.assertGreater(len(dense.segments), len(sparse.segments))
        self.assertGreater(len(dense.tips), len(sparse.tips))

    def test_same_seed_is_reproducible(self):
        first = generate_tree(
            TreeConfig.from_preset("conifer_pyramidal", branch_levels=3, seed=80)
        )
        second = generate_tree(
            TreeConfig.from_preset("conifer_pyramidal", branch_levels=3, seed=80)
        )
        self.assertEqual(first.expanded_string, second.expanded_string)
        self.assertEqual(
            [(segment.start, segment.end) for segment in first.segments],
            [(segment.start, segment.end) for segment in second.segments],
        )

    def test_presets_generate_distinct_shapes(self):
        signatures = set()
        for preset in list_presets():
            config = TreeConfig.from_preset(preset.key, branch_levels=3, seed=12)
            model = generate_tree(config)
            minimum, maximum = model.bounds()
            signatures.add(
                (
                    len(model.segments),
                    round(maximum[0] - minimum[0], 3),
                    round(maximum[1] - minimum[1], 3),
                    round(maximum[2] - minimum[2], 3),
                )
            )
        self.assertEqual(len(signatures), len(list_presets()))

    def test_branch_angle_changes_geometry(self):
        narrow = generate_tree(
            TreeConfig.from_preset(
                "broadleaf_round", branch_levels=3, branch_angle=10.0, seed=7
            )
        )
        wide = generate_tree(
            TreeConfig.from_preset(
                "broadleaf_round", branch_levels=3, branch_angle=50.0, seed=7
            )
        )
        self.assertNotEqual(
            [segment.end for segment in narrow.segments],
            [segment.end for segment in wide.segments],
        )

    def test_topology_and_taper_are_valid(self):
        model = generate_tree(
            TreeConfig.from_preset("willow_weeping", branch_levels=3, seed=4)
        )
        self.assertGreater(len(model.segments), 20)
        for segment in model.segments:
            self.assertNotEqual(segment.start, segment.end)
            self.assertGreater(segment.end_radius, 0.0)
            self.assertGreaterEqual(segment.start_radius, segment.end_radius)
            if segment.parent_index is not None:
                self.assertLess(segment.parent_index, segment.index)

    def test_radius_is_continuous_from_parent_to_child(self):
        model = generate_tree(
            TreeConfig.from_preset("broadleaf_round", branch_levels=4, seed=17)
        )
        for segment in model.segments:
            if segment.parent_index is None:
                continue
            parent = model.segments[segment.parent_index]
            self.assertAlmostEqual(segment.start_radius, parent.end_radius)

    def test_mesh_topology_matches_branch_count(self):
        model = generate_tree(
            TreeConfig.from_preset("columnar_poplar", branch_levels=3, seed=22)
        )
        sides = 7
        rings = 4
        points, counts, connects = build_mesh_arrays(model, sides, rings)
        self.assertEqual(len(points), len(model.segments) * sides * (rings + 1))
        self.assertEqual(len(counts), len(model.segments) * (sides * rings + 2))
        self.assertEqual(
            len(connects),
            len(model.segments) * (sides * rings * 4 + sides * 2),
        )


if __name__ == "__main__":
    unittest.main()
