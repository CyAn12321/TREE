from __future__ import division

import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core import TreeConfig, generate_tree
from src.foliage import FoliageConfig, generate_foliage
from src.weather import WeatherConfig, build_weather_plan


class WindPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = generate_tree(
            TreeConfig.from_preset(
                "broadleaf_round",
                branch_levels=3,
                seed=52,
            )
        )
        cls.foliage = generate_foliage(
            cls.tree,
            FoliageConfig(season="summer", seed=153),
        )

    def test_zero_wind_disables_animation(self):
        config = WeatherConfig(wind_intensity=0.0)
        plan = build_weather_plan(self.tree, self.foliage, config)
        self.assertFalse(config.any_effect_enabled())
        self.assertFalse(config.has_wind())
        self.assertEqual(plan["wind_amplitude_degrees"], 0.0)

    def test_wind_strength_increases_sway_amplitude_and_frequency(self):
        weak = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(wind_intensity=0.2),
        )
        strong = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(wind_intensity=0.9),
        )
        self.assertGreater(
            strong["wind_amplitude_degrees"],
            weak["wind_amplitude_degrees"],
        )
        self.assertGreater(
            strong["wind_frequency"],
            weak["wind_frequency"],
        )

    def test_wind_plan_bounds_include_foliage_and_twigs(self):
        plan = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(wind_intensity=0.5),
        )
        minimum = plan.minimum_bounds
        maximum = plan.maximum_bounds
        points = []
        points.extend(leaf.position for leaf in self.foliage.leaves)
        points.extend(flower.position for flower in self.foliage.flowers)
        for twig in self.foliage.twigs:
            points.extend((twig.start, twig.tip_position()))
        for point in points:
            for axis in range(3):
                self.assertGreaterEqual(point[axis], minimum[axis])
                self.assertLessEqual(point[axis], maximum[axis])

    def test_invalid_wind_intensity_and_frame_range_are_rejected(self):
        with self.assertRaises(ValueError):
            WeatherConfig(wind_intensity=1.1)
        with self.assertRaises(ValueError):
            WeatherConfig(start_frame=20, end_frame=20)

    def test_falling_organ_settings_enable_animation(self):
        config = WeatherConfig(
            leaf_fall_intensity=1.0,
            flower_fall_intensity=1.0,
        )
        self.assertTrue(config.any_effect_enabled())
        self.assertTrue(config.has_falling_organs())
        plan = build_weather_plan(self.tree, self.foliage, config)
        self.assertEqual(plan["wind_amplitude_degrees"], 0.0)
        self.assertGreater(plan["falling_leaf_count"], 0)
        self.assertGreater(plan["falling_flower_count"], 0)

    def test_falling_particle_counts_follow_intensity(self):
        weak = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(
                leaf_fall_intensity=0.2,
                flower_fall_intensity=0.2,
            ),
        )
        strong = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(
                leaf_fall_intensity=0.8,
                flower_fall_intensity=0.8,
            ),
        )
        self.assertGreaterEqual(
            strong["falling_leaf_count"],
            weak["falling_leaf_count"],
        )
        self.assertGreaterEqual(
            strong["falling_flower_count"],
            weak["falling_flower_count"],
        )
        self.assertLessEqual(strong["falling_leaf_count"], 240 // 4)
        self.assertLessEqual(strong["falling_flower_count"], 240 // 6)


if __name__ == "__main__":
    unittest.main()
