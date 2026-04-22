import http.server
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

SESSION_ID = sys.argv[1] if len(sys.argv) > 1 else None
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
            scene = chat.get_last_scene_json(SESSION_ID)
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
        else:
            self.send_error(404)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _handle_editing_start(self):
        interaction = chat.start_interaction(SESSION_ID, "user_editing")
        scene = chat.get_last_scene_json(SESSION_ID)
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
            self.send_error(400, "Missing interaction_id, object_id, or position")
            return

        scene = chat.get_last_scene_json(SESSION_ID)
        if not scene:
            self.send_error(404, "No scene found")
            return

        found = False
        for obj in scene.get("objects", []):
            if obj.get("id") == object_id:
                obj["position"] = position
                found = True
                break

        if not found:
            self.send_error(404, f"Object {object_id} not found in scene")
            return

        chat.save_stage_dict(interaction_id, f"move_{object_id}", scene)
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
    if not SESSION_ID:
        print("Usage: python render/render.py <session_id>")
        sys.exit(1)
    print(f"Rendering session: {SESSION_ID}")
    print(f"Open http://localhost:{PORT}")
    server = http.server.HTTPServer(("", PORT), SceneHandler)
    server.serve_forever()
