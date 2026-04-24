from typing import Optional
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from obllomov.schemas.dto.chat import ChatInteraction, ChatSession, ChatStage
from obllomov.schemas.orm.chat import SessionRow, InteractionRow, StageRow


class SessionRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def create_session(self, user_id: str) -> ChatSession:
        session_id = uuid4().hex
        with Session(self._engine) as s:
            row = SessionRow(session_id=session_id, user_id=user_id)
            s.add(row)
            s.commit()
            s.refresh(row)
            return ChatSession(
                id=row.session_id,
                user_id=row.user_id,
                created_at=row.created_at,
            )

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        with Session(self._engine) as s:
            row = s.get(SessionRow, session_id)
            if row is None:
                return None
            return self._to_chat_session(row)

    def list_sessions(self, user_id: str) -> list[ChatSession]:
        with Session(self._engine) as s:
            rows = s.execute(
                select(SessionRow).where(SessionRow.user_id == user_id)
            ).scalars().all()
            return [self._to_chat_session(r) for r in rows]

    def add_interaction(self, session_id: str, query: str) -> ChatInteraction:
        with Session(self._engine) as s:
            last_seq = s.execute(
                select(InteractionRow.sequence)
                .where(InteractionRow.session_id == session_id)
                .order_by(InteractionRow.sequence.desc())
                .limit(1)
            ).scalar()
            sequence = (last_seq or 0) + 1

            row = InteractionRow(
                session_id=session_id,
                sequence=sequence,
                query=query,
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            return self._to_chat_interaction(row)

    def has_active_interaction(self, session_id: str) -> bool:
        with Session(self._engine) as s:
            return s.execute(
                select(InteractionRow.id)
                .where(
                    InteractionRow.session_id == session_id,
                    InteractionRow.status == "pending",
                )
                .limit(1)
            ).scalar() is not None

    def update_interaction_status(self, interaction_id: int, status: str):
        with Session(self._engine) as s:
            row = s.get(InteractionRow, interaction_id)
            if row:
                row.status = status
                s.commit()

    def complete_editing_interactions(self, session_id: str):
        with Session(self._engine) as s:
            rows = s.execute(
                select(InteractionRow).where(
                    InteractionRow.session_id == session_id,
                    InteractionRow.status == "user_editing",
                )
            ).scalars().all()
            for row in rows:
                row.status = "done"
            s.commit()

    def get_interaction(self, session_id: str, sequence: int) -> Optional[ChatInteraction]:
        with Session(self._engine) as s:
            row = s.execute(
                select(InteractionRow)
                .where(
                    InteractionRow.session_id == session_id,
                    InteractionRow.sequence == sequence,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._to_chat_interaction(row)

    def add_stage(
        self,
        interaction_id: int,
        stage_name: str,
        scene_plan: dict,
        raw_scene_plan: dict,
    ) -> ChatStage:
        with Session(self._engine) as s:
            row = StageRow(
                interaction_id=interaction_id,
                stage_name=stage_name,
                scene_plan=scene_plan,
                raw_scene_plan=raw_scene_plan,
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            return self._to_chat_stage(row)

    def get_last_stage(self, session_id: str) -> Optional[ChatStage]:
        with Session(self._engine) as s:
            row = s.execute(
                select(StageRow)
                .join(InteractionRow)
                .where(InteractionRow.session_id == session_id)
                .order_by(StageRow.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._to_chat_stage(row)

    @staticmethod
    def _to_chat_session(row: SessionRow) -> ChatSession:
        return ChatSession(
            id=row.session_id,
            user_id=row.user_id,
            interactions=[
                SessionRepository._to_chat_interaction(i)
                for i in row.interactions
            ],
            created_at=row.created_at,
        )

    @staticmethod
    def _to_chat_interaction(row: InteractionRow) -> ChatInteraction:
        return ChatInteraction(
            id=row.id,
            sequence=row.sequence,
            query=row.query,
            status=row.status,
            stages=[
                SessionRepository._to_chat_stage(st)
                for st in row.stages
            ],
            created_at=row.created_at,
        )

    @staticmethod
    def _to_chat_stage(row: StageRow) -> ChatStage:
        return ChatStage(
            id=row.id,
            stage_name=row.stage_name,
            scene_plan=row.scene_plan,
            raw_scene_plan=row.raw_scene_plan,
            created_at=row.created_at,
        )
