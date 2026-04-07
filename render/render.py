import gzip
import http.server
import json
import os
import pickle
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

import numpy as np

SCENE_PATH = sys.argv[1] if len(sys.argv) > 1 else "scenes/A_lightful_living_room,_small/A_lightful_living_room,_small.json"
MATERIALS_DIR = os.path.expanduser("~/.objathor-assets/holodeck/2023_09_23/materials/images")
ASSETS_DIR = os.path.expanduser("~/.objathor-assets/2023_09_23/assets")
DOORS_IMG_DIR = os.path.expanduser("~/.objathor-assets/holodeck/2023_09_23/doors/images")
PORT = 8088

VIEWER_HTML = Path(__file__).parent / "viewer.html"


class SceneHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = unquote(urlparse(self.path).path)

        if path == "/":
            self._serve_file(VIEWER_HTML, "text/html")
        elif path == "/scene.json":
            self._serve_file(SCENE_PATH, "application/json")
        elif path.startswith("/materials/"):
            name = path.split("/materials/")[-1]
            self._serve_file(os.path.join(MATERIALS_DIR, name), "image/png")
        elif path.startswith("/doors/"):
            name = path.split("/doors/")[-1]
            self._serve_file(os.path.join(DOORS_IMG_DIR, name), "image/png")
        elif path.startswith("/mesh/"):
            asset_id = path.split("/mesh/")[-1]
            self._serve_mesh(asset_id)
        elif path.startswith("/assets/"):
            parts = path.split("/assets/")[-1]
            self._serve_file(os.path.join(ASSETS_DIR, parts), self._guess_mime(parts))
        else:
            self.send_error(404)

    def _serve_file(self, filepath, content_type):
        filepath = str(filepath)
        if not os.path.isfile(filepath):
            self.send_error(404, f"Not found: {filepath}")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(filepath, "rb") as f:
            self.wfile.write(f.read())

    def _serve_mesh(self, asset_id):
        pkl_path = os.path.join(ASSETS_DIR, asset_id, f"{asset_id}.pkl.gz")
        if not os.path.isfile(pkl_path):
            self.send_error(404, f"Asset not found: {asset_id}")
            return

        with gzip.open(pkl_path, "rb") as f:
            data = pickle.load(f)

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

        body = json.dumps(mesh).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _guess_mime(self, path):
        if path.endswith(".jpg"):
            return "image/jpeg"
        if path.endswith(".png"):
            return "image/png"
        return "application/octet-stream"


if __name__ == "__main__":
    print(f"Rendering scene: {SCENE_PATH}")
    print(f"Materials: {MATERIALS_DIR}")
    print(f"Open http://localhost:{PORT}")
    server = http.server.HTTPServer(("", PORT), SceneHandler)
    server.serve_forever()
