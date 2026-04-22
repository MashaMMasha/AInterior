import json
import math
from functools import lru_cache

import numpy as np

from obllomov.shared.path import (
    HOLODECK_DOORS_IMAGES_DIR,
    HOLODECK_MATERIALS_IMAGES_DIR,
    OBJATHOR_ASSETS_DIR,
)
from obllomov.storage.assets import BaseAssets, LocalAssets

assets: BaseAssets = LocalAssets()


def guess_mime(path: str) -> str:
    if path.endswith(".jpg"):
        return "image/jpeg"
    if path.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


def align_mesh_xz(verts: np.ndarray, norms: np.ndarray):
    from shapely.geometry import MultiPoint

    xz = verts[:, [0, 2]]
    hull = MultiPoint(xz.tolist()).convex_hull
    mrr = hull.minimum_rotated_rectangle
    coords = np.array(mrr.exterior.coords[:4])

    e1 = coords[1] - coords[0]
    e2 = coords[2] - coords[1]
    long_edge = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2
    angle = math.atan2(long_edge[1], long_edge[0])

    snapped = round(angle / (math.pi / 2)) * (math.pi / 2)
    correction = snapped - angle

    if abs(correction) < math.radians(2):
        return verts, norms

    cos_a = math.cos(correction)
    sin_a = math.sin(correction)

    aligned_verts = verts.copy()
    aligned_verts[:, 0] = cos_a * verts[:, 0] - sin_a * verts[:, 2]
    aligned_verts[:, 2] = sin_a * verts[:, 0] + cos_a * verts[:, 2]

    aligned_norms = norms.copy()
    aligned_norms[:, 0] = cos_a * norms[:, 0] - sin_a * norms[:, 2]
    aligned_norms[:, 2] = sin_a * norms[:, 0] + cos_a * norms[:, 2]

    return aligned_verts, aligned_norms


@lru_cache(maxsize=128)
def load_mesh_json(asset_id: str) -> bytes:
    pkl_rel = OBJATHOR_ASSETS_DIR / asset_id / f"{asset_id}.pkl.gz"
    data = assets.read_pickle(pkl_rel)

    def to_list(v):
        return [float(v["x"]), float(v["y"]), float(v["z"])]

    def to_uv(v):
        return [float(v["x"]), float(v["y"])]

    verts = np.array([to_list(v) for v in data["vertices"]])
    norms = np.array([to_list(n) for n in data["normals"]])
    verts, norms = align_mesh_xz(verts, norms)

    mesh = {
        "vertices": verts.tolist(),
        "normals": norms.tolist(),
        "uvs": [to_uv(u) for u in data["uvs"]],
        "triangles": [int(i) for i in data["triangles"]],
        "albedoUrl": f"/assets/{asset_id}/albedo.jpg",
        "normalUrl": f"/assets/{asset_id}/normal.jpg",
        "emissionUrl": f"/assets/{asset_id}/emission.jpg",
    }
    return json.dumps(mesh).encode()
