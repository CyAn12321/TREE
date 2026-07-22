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
from src.vertex_animation import precipitation_center


class WeatherPlanTests(unittest.TestCase):
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

    def test_zero_strength_disables_all_weather_outputs(self):
        config = WeatherConfig()
        plan = build_weather_plan(self.tree, self.foliage, config)
        self.assertFalse(config.any_effect_enabled())
        self.assertEqual(plan["wind_curvature"], 0.0)
        self.assertEqual(plan["rain_rate"], 0)
        self.assertEqual(plan["snow_rate"], 0)
        self.assertEqual(plan["snow_blend"], 0.0)
        self.assertEqual(plan["falling_leaf_count"], 0)
        self.assertEqual(plan["falling_flower_count"], 0)

    def test_intensity_monotonically_increases_effect_parameters(self):
        weak = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(
                wind_intensity=0.2,
                rain_intensity=0.2,
                snow_intensity=0.2,
                leaf_fall_intensity=0.2,
                flower_fall_intensity=0.2,
            ),
        )
        strong = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(
                wind_intensity=0.9,
                rain_intensity=0.9,
                snow_intensity=0.9,
                leaf_fall_intensity=0.9,
                flower_fall_intensity=0.9,
            ),
        )
        for key in (
            "wind_curvature",
            "rain_rate",
            "rain_speed",
            "snow_rate",
            "snow_speed",
            "snow_blend",
            "falling_leaf_count",
            "falling_flower_count",
        ):
            self.assertGreater(strong[key], weak[key])

    def test_snow_accumulates_before_the_animation_finishes(self):
        config = WeatherConfig(
            snow_intensity=0.8,
            start_frame=10,
            end_frame=250,
        )
        plan = build_weather_plan(self.tree, self.foliage, config)
        self.assertGreater(plan["snow_accumulation_end"], config.start_frame)
        self.assertLess(plan["snow_accumulation_end"], config.end_frame)

    def test_particle_limits_are_respected(self):
        plan = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(
                leaf_fall_intensity=1.0,
                flower_fall_intensity=1.0,
                max_falling_leaves=12,
                max_falling_flowers=7,
            ),
        )
        self.assertLessEqual(plan["falling_leaf_count"], 12)
        self.assertLessEqual(plan["falling_flower_count"], 7)

    def test_weather_bounds_include_every_foliage_instance(self):
        plan = build_weather_plan(self.tree, self.foliage, WeatherConfig())
        minimum = plan.minimum_bounds
        maximum = plan.maximum_bounds
        for instance in self.foliage.leaves + self.foliage.flowers:
            for axis in range(3):
                self.assertGreaterEqual(instance.position[axis], minimum[axis])
                self.assertLessEqual(instance.position[axis], maximum[axis])

    def test_invalid_intensity_and_frame_range_are_rejected(self):
        with self.assertRaises(ValueError):
            WeatherConfig(wind_intensity=1.1)
        with self.assertRaises(ValueError):
            WeatherConfig(start_frame=20, end_frame=20)

    def test_fixed_precipitation_pool_moves_and_stays_above_ground(self):
        plan = build_weather_plan(
            self.tree,
            self.foliage,
            WeatherConfig(rain_intensity=0.8, snow_intensity=0.8),
        )
        first = precipitation_center("rain", 3, 1, plan, 9)
        later = precipitation_center("rain", 3, 24, plan, 9)
        self.assertNotEqual(first, later)
        for kind in ("rain", "snow"):
            for frame in range(1, 241, 11):
                point = precipitation_center(kind, 7, frame, plan, 9)
                self.assertGreaterEqual(point[1], plan["ground_y"])
                self.assertLessEqual(point[1], plan["emitter_height"])


if __name__ == "__main__":
    unittest.main()
