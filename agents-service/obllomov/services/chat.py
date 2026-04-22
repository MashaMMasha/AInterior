from typing import Optional

from obllomov.schemas.dto.chat import ChatInteraction, ChatSession, ChatStage
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

    def start_interaction(self, session_id: str, query: str) -> ChatInteraction:
        return self._repo.add_interaction(session_id, query)

    def save_stage(
        self,
        interaction_id: int,
        stage_name: str,
        scene_plan: ScenePlan,
        raw_scene_plan: RawScenePlan,
    ) -> ChatStage:
        return self._repo.add_stage(
            interaction_id=interaction_id,
            stage_name=stage_name,
            scene_plan=scene_plan.to_scene(),
            raw_scene_plan=raw_scene_plan.model_dump(),
        )

    def save_stage_dict(
        self,
        interaction_id: int,
        stage_name: str,
        scene_plan: dict,
    ) -> ChatStage:
        return self._repo.add_stage(
            interaction_id=interaction_id,
            stage_name=stage_name,
            scene_plan=scene_plan,
            raw_scene_plan={},
        )

    def get_last_scene_json(self, session_id: str) -> Optional[dict]:
        stage = self._repo.get_last_stage(session_id)
        if stage is None:
            return None
        return stage.scene_plan

    def rollback(self, session_id: str, to_sequence: int) -> ChatInteraction:
        source = self._repo.get_interaction(session_id, to_sequence)
        if source is None:
            raise ValueError(f"Interaction {to_sequence} not found in session {session_id}")
        last_stage = source.current_stage
        if last_stage is None:
            raise ValueError(f"Interaction {to_sequence} has no stages")
        interaction = self._repo.add_interaction(
            session_id=session_id,
            query=f"rollback to #{to_sequence}",
        )
        self._repo.add_stage(
            interaction_id=interaction.id,
            stage_name="rollback",
            scene_plan=last_stage.scene_plan,
            raw_scene_plan=last_stage.raw_scene_plan,
        )
        return self._repo.get_interaction(session_id, interaction.sequence)
