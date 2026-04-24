from typing import Optional

from obllomov.schemas.dto.chat import ChatInteraction, ChatSession, ChatStage
from obllomov.schemas.domain.scene import ScenePlan
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

    def has_active_interaction(self, session_id: str) -> bool:
        return self._repo.has_active_interaction(session_id)

    def complete_interaction(self, interaction_id: int):
        self._repo.update_interaction_status(interaction_id, "done")

    def fail_interaction(self, interaction_id: int):
        self._repo.update_interaction_status(interaction_id, "error")

    def set_interaction_status(self, interaction_id: int, status: str):
        self._repo.update_interaction_status(interaction_id, status)

    def complete_editing_interactions(self, session_id: str):
        self._repo.complete_editing_interactions(session_id)

    def save_stage(
        self,
        interaction_id: int,
        stage_name: str,
        scene_plan: ScenePlan,
        raw_scene_plan: Optional[RawScenePlan] = None,
    ) -> ChatStage:
        return self._repo.add_stage(
            interaction_id=interaction_id,
            stage_name=stage_name,
            scene_plan=scene_plan.to_json(),
            raw_scene_plan=raw_scene_plan.model_dump() if raw_scene_plan else {},
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
