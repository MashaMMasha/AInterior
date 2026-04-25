import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
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
from obllomov.storage.assets import LocalAssets, S3Assets
from obllomov.storage.db.engine import create_db_engine
from obllomov.storage.db.repository import SessionRepository

engine = None
chat = None
obllomov = None


@asynccontextmanager
async def lifespan(app):
    global engine, chat, obllomov

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

    logger.info("Service started")
    yield

    engine.dispose()
    logger.info("Service stopped")


app = FastAPI(title="AInterior Agents Service", version="0.1.0", lifespan=lifespan)

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
        chat.complete_interaction(interaction_id)
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        chat.fail_interaction(interaction_id)
        callback.on_error(e)
        if async_callback:
            await async_callback.on_error(e)
    finally:
        if async_callback:
            await async_callback.close()

@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    if req.session_id:
        session = chat.get_session(req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = req.session_id
    else:
        session = chat.start_session(req.user_id)
        session_id = session.id

    chat.complete_editing_interactions(session_id)
    if chat.has_active_interaction(session_id):
        raise HTTPException(status_code=409, detail="Session already has an active request")

    interaction = chat.start_interaction(session_id, req.query)

    asyncio.create_task(_run_generation(req.query, session_id, interaction.id))

    return GenerateResponse(
        session_id=session_id,
        interaction_id=interaction.id,
        status="generating",
    )

class EditRequest(BaseModel):
    query: str
    session_id: str


class EditResponse(BaseModel):
    session_id: str
    interaction_id: int
    status: str


@app.post("/edit", response_model=EditResponse)
async def edit(req: EditRequest):
    session = chat.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    last_scene_json = chat.get_last_scene_json(req.session_id)
    if last_scene_json is None:
        raise HTTPException(status_code=400, detail="No scene to edit in this session")

    from obllomov.schemas.domain.scene import ScenePlan
    scene_plan = ScenePlan.from_json(last_scene_json)

    chat.complete_editing_interactions(req.session_id)
    if chat.has_active_interaction(req.session_id):
        raise HTTPException(status_code=409, detail="Session already has an active request")

    interaction = chat.start_interaction(req.session_id, req.query)

    asyncio.create_task(_run_edit(req.query, req.session_id, interaction.id, scene_plan))

    return EditResponse(
        session_id=req.session_id,
        interaction_id=interaction.id,
        status="editing",
    )


async def _run_edit(
    query: str,
    session_id: str,
    interaction_id: int,
    scene_plan,
):
    callback = CompositeEventCallback([
        LogEventCallback(),
        ChatEventCallback(chat, interaction_id),
    ])

    try:
        obllomov.edit_scene(
            query=query,
            session_id=session_id,
            scene_plan=scene_plan,
            callback=callback,
        )
        chat.complete_interaction(interaction_id)
    except Exception as e:
        logger.error(f"Edit failed: {e}")
        chat.fail_interaction(interaction_id)
        callback.on_error(e)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agents-service"}
