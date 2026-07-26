"""Deterministic fixed-topology vertex animation evaluators.

Every function maps rest vertices to new positions.  It never creates or
deletes topology during playback, which makes the result cache-friendly.
"""

from __future__ import division, print_function

import math

from .assets import stable_unit


def clamp01(value):
    return max(0.0, min(1.0, float(value)))


def accumulation(frame, start_frame, end_frame):
    if end_frame <= start_frame:
        return 1.0 if frame >= end_frame else 0.0
    return clamp01((frame - start_frame) / float(end_frame - start_frame))


def wind_point(point, frame, intensity, direction_degrees, minimum_y, height,
               phase=0.0):
    """Two-band analytic wind; displacement grows quadratically with height."""
    if intensity <= 0.0:
        return tuple(point)
    height_weight = clamp01((point[1] - minimum_y) / max(height, 1.0e-6))
    weight = height_weight * height_weight
    radians = math.radians(direction_degrees)
    direction = (math.cos(radians), 0.0, math.sin(radians))
    primary = math.sin(frame * (0.045 + 0.085 * intensity) + phase)
    detail = 0.32 * math.sin(frame * (0.104 + 0.12 * intensity) + phase * 1.71)
    amount = height * 0.12 * intensity * weight * (primary + detail)
    return (
        point[0] + direction[0] * amount,
        point[1] - abs(amount) * 0.035 * height_weight,
        point[2] + direction[2] * amount,
    )


def precipitation_center(kind, index, frame, plan, seed):
    """Loop one rain/snow element through a fixed bounding volume."""
    center = plan["center"]
    size = plan["size"]
    start = plan.config.start_frame
    x = center[0] + (stable_unit(seed, index, kind + ":x") - 0.5) * max(size[0] * 1.35, 3.0)
    z = center[2] + (stable_unit(seed, index, kind + ":z") - 0.5) * max(size[2] * 1.35, 3.0)
    phase = stable_unit(seed, index, kind + ":phase")
    speed = plan["rain_speed"] if kind == "rain" else plan["snow_speed"]
    fall_height = max(1.0, plan["emitter_height"] - plan["ground_y"])
    elapsed_seconds = max(0.0, frame - start) / plan.config.frames_per_second
    travelled = (phase * fall_height + elapsed_seconds * speed) % fall_height
    y = plan["emitter_height"] - travelled
    if kind == "snow":
        x += math.sin(frame * 0.055 + phase * 12.0) * (0.25 + plan.config.wind_intensity)
        z += math.cos(frame * 0.041 + phase * 9.0) * 0.18
    return (x, y, z)


def falling_origin(instance, index, frame, plan, kind, seed):
    """Move a detached organ from its original tree socket in a repeatable arc."""
    start = plan.config.start_frame
    duration = max(1.0, plan.config.end_frame - start + 1.0)
    delay = stable_unit(seed, instance.attachment_id, kind + ":delay") * duration * 0.55
    local_time = max(0.0, frame - start - delay)
    progress = min(1.0, local_time / (duration * 0.45))
    phase = stable_unit(seed, instance.attachment_id, kind + ":phase") * math.pi * 2.0
    fall_distance = max(0.0, instance.position[1] - plan["ground_y"])
    sway = math.sin(progress * math.pi * 5.0 + phase) * plan["height"] * 0.025
    wind_radians = math.radians(plan.config.wind_direction_degrees)
    drift = progress * progress * plan["height"] * 0.16 * (0.3 + plan.config.wind_intensity)
    return (
        instance.position[0] + math.cos(wind_radians) * drift + sway,
        max(plan["ground_y"], instance.position[1] - fall_distance * progress * progress),
        instance.position[2] + math.sin(wind_radians) * drift + sway * 0.45,
    )
