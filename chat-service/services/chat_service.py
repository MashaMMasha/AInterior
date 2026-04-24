from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from chat_service.repositories.session_repository import SessionRepository
from chat_service.schemas.dto.chat import ChatInteraction, ChatSession, ChatStage


class ChatService:
    """Доменный слой чата (сессия → взаимодействие → стадии), как в agents-chats."""

    def __init__(self, repository: SessionRepository | None = None):
        self._repo = repository or SessionRepository()

    async def start_session(self, db: AsyncSession, user_id: int) -> ChatSession:
        return await self._repo.create_session(db, user_id)

    async def get_session(self, db: AsyncSession, session_id: str) -> Optional[ChatSession]:
        return await self._repo.get_session(db, session_id)

    async def list_sessions(self, db: AsyncSession, user_id: int) -> list[ChatSession]:
        return await self._repo.list_sessions(db, user_id)

    async def start_interaction(self, db: AsyncSession, session_id: str, query: str) -> ChatInteraction:
        return await self._repo.add_interaction(db, session_id, query)

    async def save_stage(
        self,
        db: AsyncSession,
        *,
        interaction_id: int,
        stage_name: str,
        scene_plan: dict,
        raw_scene_plan: dict,
    ) -> ChatStage:
        return await self._repo.add_stage(
            db,
            interaction_id=interaction_id,
            stage_name=stage_name,
            scene_plan=scene_plan,
            raw_scene_plan=raw_scene_plan,
        )

    async def get_last_scene_json(self, db: AsyncSession, session_id: str) -> Optional[dict]:
        stage = await self._repo.get_last_stage(db, session_id)
        if stage is None:
            return None
        return stage.scene_plan

    async def append_mock_turn(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        user_message: str,
        assistant_text: str,
        intent: dict,
    ) -> ChatStage:
        interaction = await self._repo.add_interaction(db, session_id, user_message)
        return await self._repo.add_stage(
            db,
            interaction_id=interaction.id,
            stage_name="assistant",
            scene_plan={"text": assistant_text, "intent": intent},
            raw_scene_plan={},
        )
