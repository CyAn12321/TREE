"""License-aware organ asset catalog and lightweight OBJ loader.

The pure-Python layer deliberately avoids Maya imports so catalog selection and
mesh normalization can be tested outside the DCC.  OBJ vertices are normalized
to unit height, with the lowest Y point placed at the attachment origin.
"""

from __future__ import division, print_function

import json
import os

from .math_utils import stable_unit


# Asset provenance is recorded in ``assets/organs/SOURCES.md``.  The bundled
# Kenney Nature Kit meshes are CC0 assets; the loader below is original project
# code that normalizes and triangulates them for Maya instancing.


def _project_root():
    """Internal helper for project root.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_catalog_path():
    """Return the absolute path to the bundled organ catalog JSON.

    Returns:
        str: Path to ``assets/organs/catalog.json``.
    """
    return os.path.join(_project_root(), "assets", "organs", "catalog.json")


class OrganAsset(object):
    def __init__(self, root, data):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            root: Input value used by this function.
            data: Input value used by this function.
        """
        self.id = str(data["id"])
        self.kind = str(data["kind"])
        self.path = os.path.normpath(os.path.join(root, data["file"]))
        self.weight = float(data.get("weight", 1.0))
        self.scale = float(data.get("scale", 1.0))
        self.states = tuple(data.get("states", ()))

    def supports(self, kind, state=None):
        """Return whether this object supports the requested option.

        Parameters:
            kind: Input value used by this function.
            state: Input value used by this function.
        """
        return self.kind == kind and (state is None or state in self.states)


class OrganMesh(object):
    def __init__(self, vertices, faces):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            vertices: Input value used by this function.
            faces: Input value used by this function.
        """
        self.vertices = tuple(vertices)
        self.faces = tuple(tuple(face) for face in faces)


class OrganAssetLibrary(object):
    def __init__(self, catalog_path=None):
        """Initialize this object from the supplied configuration or input data.

        Parameters:
            catalog_path: Input value used by this function.
        """
        self.catalog_path = os.path.abspath(catalog_path or default_catalog_path())
        with open(self.catalog_path, "r") as stream:
            data = json.load(stream)
        self.source = dict(data.get("source", {}))
        root = os.path.dirname(self.catalog_path)
        self.assets = tuple(OrganAsset(root, item) for item in data["assets"])
        self._by_id = dict((asset.id, asset) for asset in self.assets)
        self._mesh_cache = {}

    def get(self, asset_id):
        """Execute the get operation.

        Parameters:
            asset_id: Input value used by this function.
        """
        return self._by_id[asset_id]

    def candidates(self, kind, state=None):
        """Execute the candidates operation.

        Parameters:
            kind: Input value used by this function.
            state: Input value used by this function.
        """
        exact = [asset for asset in self.assets if asset.supports(kind, state)]
        if exact:
            return exact
        return [asset for asset in self.assets if asset.kind == kind]

    def choose(self, kind, state, seed, identity):
        """Stochastically choose an asset of ``kind`` matching ``state``.

        Parameters:
            kind (str): "leaf" or "flower".
            state (str): Lifecycle state ("fresh", "mature", "dry",
                "bloom", "wilted").  Assets without state tags are
                treated as fallback candidates.
            seed (int): Reproducible seed feeding ``stable_unit``.
            identity (str|float): Per-instance identifier (typically
                the attachment_id) used to derive the random pick.
        """
        candidates = self.candidates(kind, state)
        if not candidates:
            return None
        total = sum(max(0.0, asset.weight) for asset in candidates)
        if total <= 0.0:
            return candidates[0]
        target = stable_unit(seed, identity, "asset") * total
        accumulated = 0.0
        for asset in candidates:
            accumulated += max(0.0, asset.weight)
            if target <= accumulated:
                return asset
        return candidates[-1]

    def mesh(self, asset_id):
        """Execute the mesh operation.

        Parameters:
            asset_id: Input value used by this function.
        """
        if asset_id not in self._mesh_cache:
            self._mesh_cache[asset_id] = load_obj_normalized(self.get(asset_id).path)
        return self._mesh_cache[asset_id]


def _obj_index(token, vertex_count):
    """Internal helper for obj index.

    Parameters:
        token: Input value used by this function.
        vertex_count: Input value used by this function.
    """
    value = int(token.split("/", 1)[0])
    return value - 1 if value > 0 else vertex_count + value


def load_obj_normalized(path):
    """Load a Wavefront OBJ, normalize to unit height, triangulate.

    Parameters:
        path (str): Filesystem path to the .obj file.
    """
    vertices = []
    polygon_faces = []
    with open(path, "r") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if line.startswith("v "):
                fields = line.split()
                vertices.append(tuple(float(value) for value in fields[1:4]))
            elif line.startswith("f "):
                tokens = line.split()[1:]
                polygon_faces.append(tuple(_obj_index(token, len(vertices)) for token in tokens))
    if not vertices or not polygon_faces:
        raise ValueError("OBJ contains no renderable mesh: {}".format(path))

    minimum_y = min(vertex[1] for vertex in vertices)
    maximum_y = max(vertex[1] for vertex in vertices)
    height = maximum_y - minimum_y
    if height <= 1.0e-9:
        height = max(
            max(vertex[axis] for vertex in vertices) - min(vertex[axis] for vertex in vertices)
            for axis in range(3)
        )
    if height <= 1.0e-9:
        raise ValueError("OBJ has zero extent: {}".format(path))
    normalized = tuple((x / height, (y - minimum_y) / height, z / height) for x, y, z in vertices)

    triangles = []
    for face in polygon_faces:
        for offset in range(1, len(face) - 1):
            triangles.append((face[0], face[offset], face[offset + 1]))
    return OrganMesh(normalized, triangles)
