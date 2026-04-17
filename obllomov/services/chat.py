from typing import Optional

from obllomov.schemas.dto.chat import ChatInteraction, ChatSession
from obllomov.schemas.domain.entries import ScenePlan
from obllomov.schemas.domain.raw import RawScenePlan
from obllomov.storage.db import SessionRepository


class ChatService:
    def __init__(self, repository: SessionRepository):
        self._repo = repository

    def start_session(self, user_id: str) -> ChatSession:
        return self._repo.create_session(user_id)

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self._repo.get_session(session_id)

    def list_sessions(self, user_id: str) -> list[ChatSession]:
        return self._repo.list_sessions(user_id)

    def get_last_scene_json(self, session_id: str) -> dict:
        session = self.get_session(session_id)

        interaction = session.interactions[-1]
        return interaction.scene_plan
    
    def save_interaction(
        self,
        session_id: str,
        query: str,
        scene_plan: ScenePlan,
        raw_scene_plan: RawScenePlan,
    ) -> ChatInteraction:
        return self._repo.add_interaction(
            session_id=session_id,
            query=query,
            scene_plan=scene_plan.to_scene(),
            raw_scene_plan=raw_scene_plan.model_dump(),
        )

    def update_stage(
        self,
        session_id: str,
        sequence: int,
        scene_plan: ScenePlan,
        raw_scene_plan: RawScenePlan,
    ) -> None:
        self._repo.update_plans(
            session_id=session_id,
            sequence=sequence,
            scene_plan=scene_plan.to_scene(),
            raw_scene_plan=raw_scene_plan.model_dump(),
        )

    def rollback(self, session_id: str, to_sequence: int) -> ChatInteraction:
        source = self._repo.get_interaction(session_id, to_sequence)
        if source is None:
            raise ValueError(f"Interaction {to_sequence} not found in session {session_id}")
        return self._repo.add_interaction(
            session_id=session_id,
            query=f"rollback to #{to_sequence}",
            scene_plan=source.scene_plan,
            raw_scene_plan=source.raw_scene_plan,
        )
