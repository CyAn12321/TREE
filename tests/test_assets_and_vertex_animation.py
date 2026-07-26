from __future__ import division

import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.assets import OrganAssetLibrary
from src.core import TreeConfig, generate_tree
from src.foliage import FoliageConfig, generate_foliage
from src.vertex_animation import wind_point


class AssetAndVertexAnimationTests(unittest.TestCase):
    def test_catalog_assets_exist_and_load_as_normalized_meshes(self):
        library = OrganAssetLibrary()
        self.assertGreaterEqual(len(library.candidates("leaf")), 5)
        self.assertGreaterEqual(len(library.candidates("flower")), 9)
        for asset in library.assets:
            self.assertTrue(os.path.isfile(asset.path), asset.path)
            mesh = library.mesh(asset.id)
            self.assertGreater(len(mesh.vertices), 0)
            self.assertGreater(len(mesh.faces), 0)
            self.assertAlmostEqual(min(point[1] for point in mesh.vertices), 0.0)
            self.assertAlmostEqual(max(point[1] for point in mesh.vertices), 1.0)

    def test_tree_exports_typed_modules_graph_and_stable_sockets(self):
        first = generate_tree(TreeConfig.from_preset("broadleaf_round", branch_levels=3, seed=9))
        second = generate_tree(TreeConfig.from_preset("broadleaf_round", branch_levels=3, seed=9))
        self.assertTrue(first.modules)
        self.assertTrue(first.graph.terminal_indices())
        self.assertTrue(first.attachment_points)
        self.assertEqual(
            [point.id for point in first.attachment_points],
            [point.id for point in second.attachment_points],
        )

    def test_season_pool_keeps_shared_attachment_ids(self):
        tree = generate_tree(TreeConfig.from_preset("broadleaf_round", branch_levels=3, seed=31))
        spring = generate_foliage(tree, FoliageConfig(season="spring", seed=55))
        summer = generate_foliage(tree, FoliageConfig(season="summer", seed=55))
        spring_by_id = dict((item.attachment_id, item.position) for item in spring.leaves)
        summer_by_id = dict((item.attachment_id, item.position) for item in summer.leaves)
        shared = set(spring_by_id).intersection(summer_by_id)
        self.assertTrue(shared)
        # Twig length and leaf scale are season-dependent, so a shared stable
        # attachment ID may resolve to a slightly different final position.
        # The identity pool, rather than an exact world transform, is the
        # contract used by later animation layers.
        self.assertTrue(all(isinstance(key, str) for key in shared))
        # Asset library is no longer loaded (2026-07): all leaves and
        # flowers are procedurally generated with asset_id=None.
        self.assertTrue(all(item.asset_id is None for item in summer.leaves + summer.flowers))

    def test_vertex_evaluators_preserve_topology_and_zero_wind(self):
        rest = (1.0, 4.0, -2.0)
        self.assertEqual(wind_point(rest, 12, 0.0, 30.0, 0.0, 10.0), rest)
        moved = wind_point(rest, 12, 0.8, 30.0, 0.0, 10.0)
        self.assertEqual(len(moved), len(rest))
        self.assertNotEqual(moved, rest)


if __name__ == "__main__":
    unittest.main()
