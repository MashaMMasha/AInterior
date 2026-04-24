from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
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
    user_id: str
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
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        callback.on_error(e)
        if async_callback:
            await async_callback.on_error(e)
    finally:
        if async_callback:
            await async_callback.close()


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

    background_tasks.add_task(_run_generation, req.query, session_id, interaction.id)

    return GenerateResponse(
        session_id=session_id,
        interaction_id=interaction.id,
        status="generating",
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agents-service"}
