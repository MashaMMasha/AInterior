import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

import aio_pika
from aiohttp import web

from obllomov.shared.env import env
from obllomov.shared.path import (
    HOLODECK_DOORS_IMAGES_DIR,
    HOLODECK_MATERIALS_IMAGES_DIR,
    OBJATHOR_ASSETS_DIR,
)
from obllomov.storage.assets import BaseAssets, LocalAssets

GENERATION_ID = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8089
VIEWER_HTML = Path(__file__).parent / "viewer_stream.html"

assets: BaseAssets = LocalAssets()

ws_clients: list[web.WebSocketResponse] = []


def _guess_mime(path: str) -> str:
    if path.endswith(".jpg"):
        return "image/jpeg"
    if path.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


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
        "normalUrl": f"/assets/{asset_id}/normal.jpg",
        "emissionUrl": f"/assets/{asset_id}/emission.jpg",
    }
    return json.dumps(mesh).encode()


async def handle_index(request):
    return web.FileResponse(VIEWER_HTML)


async def handle_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.append(ws)
    try:
        async for _ in ws:
            pass
    finally:
        ws_clients.remove(ws)
    return ws


async def handle_materials(request):
    name = request.match_info["name"]
    data = assets.read_bytes_or_none(HOLODECK_MATERIALS_IMAGES_DIR / name)
    if data is None:
        raise web.HTTPNotFound()
    return web.Response(body=data, content_type="image/png")


async def handle_doors(request):
    name = request.match_info["name"]
    data = assets.read_bytes_or_none(HOLODECK_DOORS_IMAGES_DIR / name)
    if data is None:
        raise web.HTTPNotFound()
    return web.Response(body=data, content_type="image/png")


async def handle_mesh(request):
    asset_id = request.match_info["asset_id"]
    pkl_rel = OBJATHOR_ASSETS_DIR / asset_id / f"{asset_id}.pkl.gz"
    if not assets.exists(pkl_rel):
        raise web.HTTPNotFound()
    return web.Response(body=_load_mesh_json(asset_id), content_type="application/json")


async def handle_assets(request):
    path = request.match_info["path"]
    data = assets.read_bytes_or_none(OBJATHOR_ASSETS_DIR / path)
    if data is None:
        raise web.HTTPNotFound()
    return web.Response(body=data, content_type=_guess_mime(path))


async def rabbitmq_listener():
    rabbitmq_url = env.RABBITMQ_URL
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        "generation_events", aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue("", exclusive=True)
    await queue.bind(exchange, routing_key=f"generation.{GENERATION_ID}")

    print(f"Listening for generation.{GENERATION_ID} events...")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                payload = message.body.decode()
                dead = []
                for ws in ws_clients:
                    try:
                        await ws.send_str(payload)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    ws_clients.remove(ws)


async def start_background_tasks(app):
    app["rabbitmq_task"] = asyncio.create_task(rabbitmq_listener())


async def cleanup_background_tasks(app):
    app["rabbitmq_task"].cancel()
    try:
        await app["rabbitmq_task"]
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    if not GENERATION_ID:
        print("Usage: python scripts/render/render_stream.py <generation_id>")
        sys.exit(1)

    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/ws", handle_ws)
    app.router.add_get("/materials/{name}", handle_materials)
    app.router.add_get("/doors/{name}", handle_doors)
    app.router.add_get("/mesh/{asset_id}", handle_mesh)
    app.router.add_get("/assets/{path:.+}", handle_assets)

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    print(f"Streaming renderer for generation: {GENERATION_ID}")
    print(f"Open http://localhost:{PORT}")
    web.run_app(app, port=PORT, print=None)
