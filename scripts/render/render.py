import argparse
import http.server
from itertools import chain
import json
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

from obllomov.shared.path import (
    HOLODECK_DOORS_IMAGES_DIR,
    HOLODECK_MATERIALS_IMAGES_DIR,
    OBJATHOR_ASSETS_DIR,
)
from obllomov.services.chat import ChatService
from obllomov.storage.db.repository import SessionRepository
from obllomov.storage.db.engine import create_db_engine

from utils import assets, guess_mime, load_mesh_json


parser = argparse.ArgumentParser()
parser.add_argument("--session-id", type=str, default=None, dest="session_id")
args = parser.parse_args()

PORT = 8088
VIEWER_HTML = Path(__file__).parent / "viewer.html"
SCRIPTS_DIR = Path(__file__).parent

engine = create_db_engine()
chat = ChatService(SessionRepository(engine))


class SceneHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = unquote(urlparse(self.path).path)

        if path == "/":
            self._serve_local_file(VIEWER_HTML, "text/html")
        elif path == "/utils.js":
            self._serve_local_file(SCRIPTS_DIR / "utils.js", "application/javascript")
        elif path == "/scene.json":
            scene = chat.get_last_scene_json(args.session_id)
            self._respond(json.dumps(scene).encode(), "application/json")
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
            self._serve_asset(OBJATHOR_ASSETS_DIR / parts, guess_mime(parts))
        else:
            self.send_error(404)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        body = self._read_json_body()
        if body is None:
            return

        if path == "/editing/start":
            self._handle_editing_start()
        elif path == "/editing/move":
            self._handle_editing_move(body)
        elif path == "/editing/stop":
            self._handle_editing_stop()
        else:
            self.send_error(404)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _handle_editing_start(self):
        chat.complete_editing_interactions(args.session_id)
        interaction = chat.start_interaction(args.session_id, "user_editing")
        chat.set_interaction_status(interaction.id, "user_editing")
        scene = chat.get_last_scene_json(args.session_id)
        if scene:
            chat.save_stage_dict(interaction.id, "editing_start", scene)
        self._respond(
            json.dumps({"interaction_id": interaction.id}).encode(),
            "application/json",
        )

    def _handle_editing_move(self, body):
        interaction_id = body.get("interaction_id")
        object_id = body.get("object_id")
        position = body.get("position")

        if not all([interaction_id, object_id, position]):
            self.send_error(400, f"Missing interaction_id, object_id, or position: {(interaction_id, object_id, position)}")
            return

        scene = chat.get_last_scene_json(args.session_id)
        if not scene:
            self.send_error(404, "No scene found")
            return

        found = False
        object_keys = ["objects", "floor_objects", "wall_objects", "small_objects", "ceiling_objects"]
        
        objects = chain(*map(lambda key: scene.get(key, []), object_keys))
        for obj in objects:
            # print(obj)
            if obj.get("id") == object_id:
                obj["position"] = position
                found = True
                break

        if not found:
            self.send_error(404, f"Object {object_id} not found in scene")
            return

        chat.save_stage_dict(interaction_id, f"move_{object_id}", scene)
        self._respond(json.dumps({"ok": True}).encode(), "application/json")

    def _handle_editing_stop(self):
        chat.complete_editing_interactions(args.session_id)
        self._respond(json.dumps({"ok": True}).encode(), "application/json")

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
        self._respond(load_mesh_json(asset_id), "application/json")

    def _respond(self, body: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    if not args.session_id:
        print("Usage: python render/render.py <args.session_id>")
        sys.exit(1)
    print(f"Rendering session: {args.session_id}")
    print(f"Open http://localhost:{PORT}")
    server = http.server.HTTPServer(("", PORT), SceneHandler)
    server.serve_forever()
