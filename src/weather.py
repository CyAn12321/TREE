"""Pure-Python planning for wind sway and falling foliage.

The Maya animation layer combines a deterministic bend-deformer wind layer
with optional falling-leaf and falling-flower particle layers.

Rain and snow constructor arguments are accepted for scene-file compatibility
but remain inactive; leaf and flower fall intensities are part of the current
animation plan.
"""

from __future__ import division, print_function


class WeatherConfig(object):
    """Configuration for wind and falling-organ animation layers."""

    def __init__(
        self,
        wind_intensity=0.0,
        wind_direction_degrees=25.0,
        start_frame=1,
        end_frame=240,
        seed=211,
        frames_per_second=24.0,
        # Rain and snow remain reserved for backward-compatible scene JSON;
        # falling leaves and flowers are supported by the current Maya layer.
        rain_intensity=0.0,
        snow_intensity=0.0,
        leaf_fall_intensity=0.0,
        flower_fall_intensity=0.0,
        # Conservative defaults keep Maya's playback cache manageable.
        max_falling_leaves=600,
        max_falling_flowers=300,
    ):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            wind_intensity: Input value used by this function.
            wind_direction_degrees: Input value used by this function.
            start_frame: Input value used by this function.
            end_frame: Input value used by this function.
            seed: Input value used by this function.
            frames_per_second: Input value used by this function.
            rain_intensity: Input value used by this function.
            snow_intensity: Input value used by this function.
            leaf_fall_intensity: Input value used by this function.
            flower_fall_intensity: Input value used by this function.
            max_falling_leaves: Input value used by this function.
            max_falling_flowers: Input value used by this function.
        """
        self.wind_intensity = float(wind_intensity)
        self.wind_direction_degrees = float(wind_direction_degrees)
        self.start_frame = int(start_frame)
        self.end_frame = int(end_frame)
        self.seed = int(seed)
        self.frames_per_second = float(frames_per_second)

        # Rain and snow are retained only for backward-compatible JSON round
        # trips.  No rain or snow node is created by the current layer.
        self.rain_intensity = float(rain_intensity)
        self.snow_intensity = float(snow_intensity)
        self.leaf_fall_intensity = float(leaf_fall_intensity)
        self.flower_fall_intensity = float(flower_fall_intensity)
        self.max_falling_leaves = int(max_falling_leaves)
        self.max_falling_flowers = int(max_falling_flowers)
        self.validate()

    def validate(self):
        """Validate the current configuration and raise ValueError for invalid input.
        """
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
        """Return whether any currently supported animation should be built."""
        return self.has_wind() or self.has_falling_organs()

    def has_wind(self):
        """Execute the has wind operation.
        """
        return self.wind_intensity > 0.0

    def has_falling_organs(self):
        """Execute the has falling organs operation.
        """
        return (
            self.leaf_fall_intensity > 0.0
            or self.flower_fall_intensity > 0.0
        )


class WeatherPlan(object):
    def __init__(self, config, bounds, values):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            config: Input value used by this function.
            bounds: Input value used by this function.
            values: Input value used by this function.
        """
        self.config = config
        self.minimum_bounds, self.maximum_bounds = bounds
        self.values = dict(values)

    def __getitem__(self, key):
        """Internal helper for  getitem  .

        Parameters:
            key: Input value used by this function.
        """
        return self.values[key]


def _combined_bounds(tree_model, foliage_model=None):
    """Internal helper for combined bounds.

    Parameters:
        tree_model: Input value used by this function.
        foliage_model: Input value used by this function.
    """
    minimum, maximum = tree_model.bounds()
    points = []
    if foliage_model:
        points.extend(leaf.position for leaf in foliage_model.leaves)
        points.extend(flower.position for flower in foliage_model.flowers)
        for twig in getattr(foliage_model, "twigs", ()):
            points.append(twig.start)
            points.append(twig.tip_position())
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
    """Map wind and falling-organ settings to bounded Maya parameters."""
    config = config or WeatherConfig(seed=tree_model.config.seed + 211)
    minimum, maximum = _combined_bounds(tree_model, foliage_model)
    tree_minimum, unused_tree_maximum = tree_model.bounds()
    size = tuple(maximum[axis] - minimum[axis] for axis in range(3))
    center = tuple((minimum[axis] + maximum[axis]) * 0.5 for axis in range(3))
    intensity = config.wind_intensity
    primary_frequency = 0.018 + 0.036 * intensity
    duration_frames = config.end_frame - config.start_frame + 1
    duration_seconds = duration_frames / config.frames_per_second
    leaf_count = len(foliage_model.leaves) if foliage_model else 0
    flower_count = len(foliage_model.flowers) if foliage_model else 0
    falling_leaf_count = min(
        config.max_falling_leaves,
        int(round(leaf_count * 0.18 * config.leaf_fall_intensity)),
        max(1, duration_frames // 4),
    )
    falling_flower_count = min(
        config.max_falling_flowers,
        int(round(flower_count * 0.36 * config.flower_fall_intensity)),
        max(1, duration_frames // 6),
    )
    values = {
        "center": center,
        "size": size,
        "ground_y": tree_minimum[1],
        "height": max(size[1], 0.1),
        # Bend deformer curvature is expressed as degrees in Maya.  The
        # amplitude is deliberately visible at the default UI value while
        # remaining bounded at full strength.
        "wind_amplitude_degrees": 13.0 * intensity,
        "wind_frequency": primary_frequency,
        "wind_phase": (config.seed % 360) * 0.017453292519943295,
        # Maya's positive bend curvature is opposite to the UI's intuitive
        # "wind blows toward this angle" convention.
        "wind_curvature_sign": -1.0,
        "wind_low_bound": 0.0,
        "wind_high_bound": 1.0,
        "falling_leaf_count": falling_leaf_count,
        "falling_flower_count": falling_flower_count,
        "leaf_fall_rate": (
            falling_leaf_count / duration_seconds if duration_seconds else 0.0
        ),
        "flower_fall_rate": (
            falling_flower_count / duration_seconds if duration_seconds else 0.0
        ),
    }
    return WeatherPlan(config, (minimum, maximum), values)
