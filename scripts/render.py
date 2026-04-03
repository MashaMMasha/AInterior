import http.server
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

SCENE_PATH = sys.argv[1] if len(sys.argv) > 1 else "scenes/A_lightful_living_room,_small_/A_lightful_living_room,_small_.json"
MATERIALS_DIR = os.path.expanduser("~/.objathor-assets/holodeck/2023_09_23/materials/images")
ASSETS_DIR = os.path.expanduser("~/.objathor-assets/2023_09_23/assets")
PORT = 8080

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
