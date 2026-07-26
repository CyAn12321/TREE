# -*- coding: utf-8 -*-
"""Reference wind math for the wind-only animation layer.

Maya playback currently uses ``src.maya_weather`` and a bend deformer.  This
small pure-Python evaluator mirrors the same two-band, height-weighted motion
for tests and for future cache/export tooling.  It does not create particles,
falling organs or snow geometry.
"""

from __future__ import division, print_function

import math


def clamp01(value):
    """Execute the clamp01 operation.

    Parameters:
        value: Input value used by this function.
    """
    return max(0.0, min(1.0, float(value)))


def wind_point(
    point,
    frame,
    intensity,
    direction_degrees,
    minimum_y,
    height,
    phase=0.0,
):
    """Evaluate a deterministic height-weighted wind displacement."""
    if intensity <= 0.0:
        return tuple(point)
    height_weight = clamp01((point[1] - minimum_y) / max(height, 1.0e-6))
    weight = height_weight * height_weight
    radians = math.radians(direction_degrees)
    direction = (math.cos(radians), 0.0, math.sin(radians))
    frequency = 0.018 + 0.036 * intensity
    primary = math.sin(frame * frequency + phase)
    detail = 0.28 * math.sin(frame * frequency * 2.17 + phase * 1.73)
    amount = height * 0.055 * intensity * weight * (primary + detail)
    return (
        point[0] + direction[0] * amount,
        point[1] - abs(amount) * 0.035 * height_weight,
        point[2] + direction[2] * amount,
    )
