# -*- coding: utf-8 -*-
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
    amount = height * 0.055 * intensity * weight * (primary + detail)
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


def leaf_flutter(point, frame, intensity, attachment_id, seed,
                 leaf_length=1.0, distance_from_petiole=1.0):
    """Per-leaf high-frequency flutter independent of the global wind.

    Each leaf has a unique phase derived from its ``attachment_id`` so
    neighbouring leaves oscillate out of sync  -  the shimmering effect
    seen in real canopies.  The displacement is applied perpendicular
    to the leaf surface (approximated as the Y axis here) and grows
    with ``distance_from_petiole`` (0 at petiole, 1 at tip) so the
    leaf base stays anchored while the tip flutters freely.

    Parameters:
        point: rest position (x, y, z)
        frame: current animation frame
        intensity: wind intensity 0..1
        attachment_id: unique per-leaf identity for phase offset
        seed: global seed for reproducibility
        leaf_length: length of this leaf (scales amplitude)
        distance_from_petiole: normalized 0..1 distance along blade

    Returns:
        Displaced (x, y, z) tuple.
    """
    if intensity <= 0.0:
        return tuple(point)
    # Unique phase per leaf so neighbours don't sync.
    phase = stable_unit(seed, attachment_id, "flutter:phase") * math.pi * 2.0
    # High-frequency flutter: 3-5x the primary wind frequency.
    freq = 0.18 + 0.10 * stable_unit(seed, attachment_id, "flutter:freq")
    # Amplitude: ~10% of leaf length, scaled by distance from petiole
    # (tip flutters most) and wind intensity.
    amp = leaf_length * 0.10 * intensity * distance_from_petiole
    # Two-band flutter: primary oscillation + a faster detail harmonic.
    primary = math.sin(frame * freq + phase)
    detail = 0.4 * math.sin(frame * freq * 2.3 + phase * 1.7)
    displacement = amp * (primary + detail)
    # Apply in XZ plane (perpendicular to the leaf's forward axis).
    twist_phase = stable_unit(seed, attachment_id, "flutter:twist") * math.pi * 2.0
    twist = math.sin(frame * freq * 0.7 + twist_phase) * amp * 0.3
    return (
        point[0] + displacement,
        point[1] + twist * 0.5,
        point[2] + displacement * 0.6 + twist,
    )


def flower_sway(frame, intensity, attachment_id, seed, peduncle_length=0.1):
    """Per-flower rotational sway around the pedicel axis.

    Returns a small angular offset (radians) that should be applied
    as a rotation to the flower instance's transform.  Each flower
    sways independently with a unique phase, simulating the gentle
    rocking of blossoms on their pedicels in a breeze.

    Parameters:
        frame: current animation frame
        intensity: wind intensity 0..1
        attachment_id: unique per-flower identity
        seed: global seed
        peduncle_length: length of the pedicel (longer = more sway)

    Returns:
        (angle_x, angle_z) tuple in radians for transform rotation.
    """
    if intensity <= 0.0:
        return (0.0, 0.0)
    phase = stable_unit(seed, attachment_id, "sway:phase") * math.pi * 2.0
    freq = 0.06 + 0.04 * stable_unit(seed, attachment_id, "sway:freq")
    # Sway amplitude scales with peduncle length (longer stem = more lever).
    amp = 0.08 * intensity * (1.0 + peduncle_length * 3.0)
    angle_x = math.sin(frame * freq + phase) * amp
    angle_z = math.cos(frame * freq * 0.8 + phase * 1.3) * amp * 0.7
    return (angle_x, angle_z)
