import http.server
import json
import sys
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse, unquote

from obllomov.shared.path import (
    HOLODECK_DOORS_IMAGES_DIR,
    HOLODECK_MATERIALS_IMAGES_DIR,
    OBJATHOR_ASSETS_DIR,
)
from obllomov.storage.assets import BaseAssets, LocalAssets

SCENE_PATH = sys.argv[1] if len(sys.argv) > 1 else "scenes/A_lightful_living_room,_small/A_lightful_living_room,_small.json"
PORT = 8088
VIEWER_HTML = Path(__file__).parent / "viewer.html"

assets: BaseAssets = LocalAssets()


def _guess_mime(path: str) -> str:
    if path.endswith(".jpg"):
        return "image/jpeg"
    if path.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


@lru_cache(maxsize=128)
def _load_mesh_json(asset_id: str) -> bytes:
    pkl_rel = OBJATHOR_ASSETS_DIR / asset_id / f"{asset_id}.pkl.gz"
    data = assets.read_pickle(pkl_rel)

    def to_list(v):
        return [float(v["x"]), float(v["y"]), float(v["z"])]

    def to_uv(v):
        return [float(v["x"]), float(v["y"])]

    mesh = {
        "vertices": [to_list(v) for v in data["vertices"]],
        "normals": [to_list(n) for n in data["normals"]],
        "uvs": [to_uv(u) for u in data["uvs"]],
        "triangles": [int(i) for i in data["triangles"]],
        "albedoUrl": f"/assets/{asset_id}/albedo.jpg",
    }
    return json.dumps(mesh).encode()


class SceneHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = unquote(urlparse(self.path).path)

        if path == "/":
            self._serve_local_file(VIEWER_HTML, "text/html")
        elif path == "/scene.json":
            self._serve_local_file(SCENE_PATH, "application/json")
        elif path.startswith("/materials/"):
            name = path.split("/materials/")[-1]
            self._serve_asset(HOLODECK_MATERIALS_IMAGES_DIR / name, "image/png")
        elif path.startswith("/doors/"):
            name = path.split("/doors/")[-1]
            self._serve_asset(HOLODECK_DOORS_IMAGES_DIR / name, "image/png")
        elif path.startswith("/mesh/"):
            asset_id = path.split("/mesh/")[-1]
            self._serve_mesh(asset_id)
        elif path.startswith("/assets/"):
            parts = path.split("/assets/")[-1]
            self._serve_asset(OBJATHOR_ASSETS_DIR / parts, _guess_mime(parts))
        else:
            self.send_error(404)

    def _serve_local_file(self, filepath, content_type):
        filepath = Path(filepath)
        if not filepath.is_file():
            self.send_error(404, f"Not found: {filepath}")
            return
        self._respond(filepath.read_bytes(), content_type)

    def _serve_asset(self, relative_path, content_type):
        data = assets.read_bytes_or_none(relative_path)
        if data is None:
            self.send_error(404, f"Not found: {relative_path}")
            return
        self._respond(data, content_type)

    def _serve_mesh(self, asset_id):
        pkl_rel = OBJATHOR_ASSETS_DIR / asset_id / f"{asset_id}.pkl.gz"
        if not assets.exists(pkl_rel):
            self.send_error(404, f"Asset not found: {asset_id}")
            return
        self._respond(_load_mesh_json(asset_id), "application/json")

    def _respond(self, body: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"Rendering scene: {SCENE_PATH}")
    print(f"Open http://localhost:{PORT}")
    server = http.server.HTTPServer(("", PORT), SceneHandler)
    server.serve_forever()
