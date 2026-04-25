import asyncio
import json
import mimetypes
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from obllomov.agents.llms import get_chat_yandex_model, MAX_NEW_TOKENS, ChatMock
from obllomov.services.chat import ChatService
from obllomov.services.events import (
    AsyncCompositeEventCallback,
    ChatEventCallback,
    CompositeEventCallback,
    LogEventCallback,
    RabbitMQEventCallback,
)
from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.env import env
from obllomov.shared.log import logger
from obllomov.shared.path import (
    HOLODECK_DOORS_IMAGES_DIR,
    HOLODECK_MATERIALS_IMAGES_DIR,
    OBJATHOR_ASSETS_DIR,
)
from obllomov.storage.assets import LocalAssets, S3Assets
from obllomov.storage.db.engine import create_db_engine
from obllomov.storage.db.repository import SessionRepository


engine = create_db_engine(env.DB_URL)
repo = SessionRepository(engine)
chat = ChatService(repo)

# llm = get_chat_yandex_model(temperature=0.3, max_completion_tokens=MAX_NEW_TOKENS)
llm = ChatMock()

if (
    not env.AGENTS_USE_LOCAL_ASSETS
    and env.S3_BUCKET_NAME
    and env.S3_ENDPOINT_URL
):
    logger.info("Using S3Assets")
    assets = S3Assets()
else:
    if env.AGENTS_USE_LOCAL_ASSETS:
        logger.info("Using LocalAssets (AGENTS_USE_LOCAL_ASSETS=1)")
    else:
        logger.info("Using LocalAssets (S3 not configured)")
    assets = LocalAssets()

obllomov = ObLLoMov(llm, assets)


app = FastAPI(title="AInterior Agents Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    query: str
    user_id: int
    session_id: Optional[str] = None


class GenerateResponse(BaseModel):
    session_id: str
    interaction_id: int
    status: str


def _to_xyz_list(value):
    if isinstance(value, dict):
        return [
            float(value.get("x", 0.0)),
            float(value.get("y", 0.0)),
            float(value.get("z", 0.0)),
        ]
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return [float(value[0]), float(value[1]), float(value[2])]
    return [0.0, 0.0, 0.0]


def _to_uv_list(value):
    if isinstance(value, dict):
        return [float(value.get("x", 0.0)), float(value.get("y", 0.0))]
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [float(value[0]), float(value[1])]
    return [0.0, 0.0]


@lru_cache(maxsize=256)
def _load_mesh_json_bytes(asset_id: str) -> bytes:
    pkl_rel = OBJATHOR_ASSETS_DIR / asset_id / f"{asset_id}.pkl.gz"
    mesh_raw = assets.read_pickle(pkl_rel)
    mesh = {
        "vertices": [_to_xyz_list(v) for v in mesh_raw.get("vertices", [])],
        "normals": [_to_xyz_list(n) for n in mesh_raw.get("normals", [])],
        "uvs": [_to_uv_list(u) for u in mesh_raw.get("uvs", [])],
        "triangles": [int(i) for i in mesh_raw.get("triangles", [])],
        "albedoUrl": f"/assets/{asset_id}/albedo.jpg",
        "normalUrl": f"/assets/{asset_id}/normal.jpg",
        "emissionUrl": f"/assets/{asset_id}/emission.jpg",
    }
    return json.dumps(mesh).encode()


def _mime_for_path(path: str) -> str:
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


async def _run_generation(
    query: str,
    session_id: str,
    interaction_id: int,
):
    callback = CompositeEventCallback([
        LogEventCallback(),
        ChatEventCallback(chat, interaction_id),
    ])

    async_callback = None
    if env.RABBITMQ_URL:
        async_callback = RabbitMQEventCallback(env.RABBITMQ_URL, f"{session_id}-{interaction_id}")

    try:
        await obllomov.generate_scene(
            query=query,
            save_dir="/tmp/scenes",
            callback=callback,
            async_callback=async_callback,
        )
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        callback.on_error(e)
        if async_callback:
            await async_callback.on_error(e)
    finally:
        if async_callback:
            await async_callback.close()

def _run_generation_sync(
    query: str,
    session_id: str,
    interaction_id: int,
):
    """
    Run async generation in a background thread to keep the
    main event loop responsive for /health and /generate.
    """
    asyncio.run(_run_generation(query, session_id, interaction_id))


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    if req.session_id:
        session = chat.get_session(req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = req.session_id
    else:
        session = chat.start_session(req.user_id)
        session_id = session.id

    interaction = chat.start_interaction(session_id, req.query)

    background_tasks.add_task(_run_generation_sync, req.query, session_id, interaction.id)

    return GenerateResponse(
        session_id=session_id,
        interaction_id=interaction.id,
        status="generating",
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agents-service"}


@app.get("/render/materials/{name}")
async def render_material(name: str):
    data = assets.read_bytes_or_none(HOLODECK_MATERIALS_IMAGES_DIR / name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Material not found: {name}")
    return Response(content=data, media_type="image/png")


@app.get("/render/doors/{name}")
async def render_door_image(name: str):
    data = assets.read_bytes_or_none(HOLODECK_DOORS_IMAGES_DIR / name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Door image not found: {name}")
    return Response(content=data, media_type="image/png")


@app.get("/render/mesh/{asset_id}")
async def render_mesh(asset_id: str):
    pkl_rel = OBJATHOR_ASSETS_DIR / asset_id / f"{asset_id}.pkl.gz"
    if not assets.exists(pkl_rel):
        raise HTTPException(status_code=404, detail=f"Mesh asset not found: {asset_id}")
    return Response(content=_load_mesh_json_bytes(asset_id), media_type="application/json")


@app.get("/render/assets/{asset_path:path}")
async def render_asset(asset_path: str):
    if not asset_path:
        raise HTTPException(status_code=404, detail="Asset path is required")
    rel = Path(asset_path)
    data = assets.read_bytes_or_none(OBJATHOR_ASSETS_DIR / rel)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_path}")
    return Response(content=data, media_type=_mime_for_path(asset_path))
