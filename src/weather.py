"""Pure-Python weather configuration and scene planning."""

from __future__ import division, print_function


class WeatherConfig(object):
    def __init__(
        self,
        wind_intensity=0.0,
        rain_intensity=0.0,
        snow_intensity=0.0,
        leaf_fall_intensity=0.0,
        flower_fall_intensity=0.0,
        wind_direction_degrees=25.0,
        start_frame=1,
        end_frame=240,
        seed=211,
        frames_per_second=24.0,
        max_falling_leaves=1800,
        max_falling_flowers=900,
    ):
        self.wind_intensity = float(wind_intensity)
        self.rain_intensity = float(rain_intensity)
        self.snow_intensity = float(snow_intensity)
        self.leaf_fall_intensity = float(leaf_fall_intensity)
        self.flower_fall_intensity = float(flower_fall_intensity)
        self.wind_direction_degrees = float(wind_direction_degrees)
        self.start_frame = int(start_frame)
        self.end_frame = int(end_frame)
        self.seed = int(seed)
        self.frames_per_second = float(frames_per_second)
        self.max_falling_leaves = int(max_falling_leaves)
        self.max_falling_flowers = int(max_falling_flowers)
        self.validate()

    def validate(self):
        for name in (
            "wind_intensity",
            "rain_intensity",
            "snow_intensity",
            "leaf_fall_intensity",
            "flower_fall_intensity",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError("{} must be between 0 and 1".format(name))
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame")
        if self.frames_per_second <= 0.0:
            raise ValueError("frames_per_second must be positive")
        if self.max_falling_leaves < 0 or self.max_falling_flowers < 0:
            raise ValueError("falling particle limits cannot be negative")

    def any_effect_enabled(self):
        return any(
            value > 0.0
            for value in (
                self.wind_intensity,
                self.rain_intensity,
                self.snow_intensity,
                self.leaf_fall_intensity,
                self.flower_fall_intensity,
            )
        )


class WeatherPlan(object):
    def __init__(self, config, bounds, values):
        self.config = config
        self.minimum_bounds, self.maximum_bounds = bounds
        self.values = dict(values)

    def __getitem__(self, key):
        return self.values[key]


def _combined_bounds(tree_model, foliage_model=None):
    minimum, maximum = tree_model.bounds()
    points = []
    if foliage_model:
        points.extend(leaf.position for leaf in foliage_model.leaves)
        points.extend(flower.position for flower in foliage_model.flowers)
    if not points:
        return minimum, maximum
    return (
        tuple(
            min(minimum[axis], min(point[axis] for point in points))
            for axis in range(3)
        ),
        tuple(
            max(maximum[axis], max(point[axis] for point in points))
            for axis in range(3)
        ),
    )


def build_weather_plan(tree_model, foliage_model=None, config=None):
    """Map normalized UI strengths to bounded Maya scene parameters."""
    config = config or WeatherConfig(seed=tree_model.config.seed + 211)
    minimum, maximum = _combined_bounds(tree_model, foliage_model)
    tree_minimum, unused_tree_maximum = tree_model.bounds()
    size = tuple(maximum[axis] - minimum[axis] for axis in range(3))
    center = tuple((minimum[axis] + maximum[axis]) * 0.5 for axis in range(3))
    duration_frames = config.end_frame - config.start_frame + 1
    duration_seconds = duration_frames / config.frames_per_second
    leaf_count = len(foliage_model.leaves) if foliage_model else 0
    flower_count = len(foliage_model.flowers) if foliage_model else 0
    falling_leaf_count = min(
        config.max_falling_leaves,
        int(round(leaf_count * 0.34 * config.leaf_fall_intensity)),
    )
    falling_flower_count = min(
        config.max_falling_flowers,
        int(round(flower_count * 0.72 * config.flower_fall_intensity)),
    )
    values = {
        "center": center,
        "size": size,
        "ground_y": tree_minimum[1],
        "height": max(size[1], 0.1),
        "wind_curvature": 0.16 * config.wind_intensity,
        "wind_frequency": 0.045 + 0.085 * config.wind_intensity,
        "rain_rate": int(round(950.0 * config.rain_intensity)),
        "rain_pool_count": int(round(420.0 * config.rain_intensity)),
        "rain_speed": 14.0 + 20.0 * config.rain_intensity,
        "snow_rate": int(round(620.0 * config.snow_intensity)),
        "snow_pool_count": int(round(360.0 * config.snow_intensity)),
        "snow_speed": 1.5 + 3.0 * config.snow_intensity,
        "snow_blend": config.snow_intensity,
        "snow_displacement": max(size[1] * 0.018, 0.08) * config.snow_intensity,
        "snow_accumulation_end": min(
            config.end_frame,
            config.start_frame + max(24, int(round(duration_frames * 0.42))),
        ),
        "falling_leaf_count": falling_leaf_count,
        "falling_flower_count": falling_flower_count,
        "leaf_fall_rate": (
            falling_leaf_count / duration_seconds if duration_seconds else 0.0
        ),
        "flower_fall_rate": (
            falling_flower_count / duration_seconds if duration_seconds else 0.0
        ),
        "emitter_height": maximum[1] + max(1.5, size[1] * 0.10),
        "canopy_floor": minimum[1] + size[1] * 0.24,
    }
    return WeatherPlan(config, (minimum, maximum), values)
