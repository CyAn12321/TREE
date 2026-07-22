from __future__ import division

import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import maya_editing
from src.core import TreeConfig
from src.foliage import FoliageConfig
from src.weather import WeatherConfig


class EditableTreeConfigTests(unittest.TestCase):
    def test_tree_config_round_trips_through_scene_json(self):
        config = TreeConfig.from_preset(
            "willow_weeping",
            trunk_radius=0.62,
            branch_levels=4,
            branches_per_node=5,
            branch_angle=26.0,
            seed=912,
        )
        restored = maya_editing.tree_config_from_json(
            maya_editing.config_to_json(config)
        )
        self.assertEqual(restored.preset_key, config.preset_key)
        self.assertEqual(restored.branches_per_node, 5)
        self.assertAlmostEqual(restored.trunk_radius, 0.62)
        self.assertEqual(restored.branch_tropism, config.branch_tropism)

    def test_foliage_config_round_trips_through_scene_json(self):
        config = FoliageConfig(
            season="autumn",
            leaf_density_multiplier=1.8,
            canopy_spread_multiplier=1.35,
            flower_density_multiplier=0.4,
            seed=77,
        )
        restored = maya_editing.foliage_config_from_json(
            maya_editing.config_to_json(config)
        )
        self.assertEqual(restored.season, "autumn")
        self.assertAlmostEqual(restored.leaf_density_multiplier, 1.8)
        self.assertAlmostEqual(restored.canopy_spread_multiplier, 1.35)

    def test_weather_config_round_trips_through_scene_json(self):
        config = WeatherConfig(
            wind_intensity=0.5,
            rain_intensity=0.2,
            snow_intensity=0.7,
            leaf_fall_intensity=0.4,
            flower_fall_intensity=0.3,
            start_frame=12,
            end_frame=180,
            seed=505,
        )
        restored = maya_editing.weather_config_from_json(
            maya_editing.config_to_json(config)
        )
        self.assertAlmostEqual(restored.wind_intensity, 0.5)
        self.assertAlmostEqual(restored.snow_intensity, 0.7)
        self.assertEqual(restored.start_frame, 12)
        self.assertEqual(restored.end_frame, 180)


if __name__ == "__main__":
    unittest.main()
