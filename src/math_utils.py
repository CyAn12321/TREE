# -*- coding: utf-8 -*-
"""Shared vector math and stable hashing utilities.

Centralizes the small tuple-based 3D vector operations (_add/_sub/_mul/
_dot/_cross/_length/_normalize) and the stable_unit deterministic hash
that were previously duplicated across core.py, foliage.py,
maya_foliage.py, maya_mesh.py and assets.py.

Two normalize behaviours coexist intentionally:
- ``normalize_strict`` raises ValueError on zero vectors (used by
  core.py / maya_mesh.py where a zero normal indicates a bug).
- ``normalize_default`` returns (0,1,0) on zero vectors (used by
  foliage.py / maya_foliage.py where degenerate inputs are expected
  and silently fall back to world-up).
"""


import math
import hashlib
import binascii


EPSILON = 1.0e-9


def stable_unit(seed, identity, channel="default"):
    """Return a stable pseudo-random float in [0, 1) without global RNG.

    Uses sha256(seed|identity|channel) so the same inputs always yield
    the same value across runs and across Python versions.  Used for
    deterministic per-organ jitter so scenes are reproducible from seed.

    Parameters:
        seed (int): Numeric seed (typically the tree/flower seed).
        identity (str|float): Per-instance identifier (e.g. position key).
        channel (str): Optional channel name to derive independent streams.
    """
    payload = "{}|{}|{}".format(int(seed), identity, channel).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    integer = int(binascii.hexlify(digest[:8]), 16)
    return integer / float((1 << 64) - 1)


def add(a, b):
    """Return element-wise a + b.

    Parameters:
        a (tuple): 3-vector (x, y, z).
        b (tuple): 3-vector (x, y, z).
    """
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    """Return element-wise a - b.

    Parameters:
        a (tuple): 3-vector (x, y, z).
        b (tuple): 3-vector (x, y, z).
    """
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(vector, scalar):
    """Return vector * scalar.

    Parameters:
        vector (tuple): 3-vector (x, y, z).
        scalar (float): Scaling factor.
    """
    return tuple(component * scalar for component in vector)


def dot(a, b):
    """Return dot product of a and b.

    Parameters:
        a (tuple): 3-vector.
        b (tuple): 3-vector.
    """
    return sum(a[index] * b[index] for index in range(3))


def cross(a, b):
    """Return cross product a x b.

    Parameters:
        a (tuple): 3-vector.
        b (tuple): 3-vector.
    """
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(vector):
    """Return Euclidean length of vector.

    Parameters:
        vector (tuple): 3-vector.
    """
    return math.sqrt(dot(vector, vector))


def normalize_strict(vector):
    """Normalize raising ValueError on zero-length input.

    Parameters:
        vector (tuple): 3-vector; non-zero length required.
    """
    magnitude = length(vector)
    if magnitude <= EPSILON:
        raise ValueError("Cannot normalize a zero-length vector")
    return mul(vector, 1.0 / magnitude)


def normalize_default(vector):
    """Normalize returning world-up (0,1,0) on zero-length input.

    Parameters:
        vector (tuple): 3-vector; zero vectors fall back to (0, 1, 0).
    """
    magnitude = length(vector)
    if magnitude <= EPSILON:
        return (0.0, 1.0, 0.0)
    return mul(vector, 1.0 / magnitude)
