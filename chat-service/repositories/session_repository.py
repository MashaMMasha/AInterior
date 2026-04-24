from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from chat_service.schemas.dto.chat import ChatInteraction, ChatSession, ChatStage
from chat_service.schemas.orm.chat import InteractionRow, SessionRow, StageRow


def _stage_to_dto(row: StageRow) -> ChatStage:
    return ChatStage(
        id=row.id,
        stage_name=row.stage_name,
        scene_plan=dict(row.scene_plan or {}),
        raw_scene_plan=dict(row.raw_scene_plan or {}),
        created_at=row.created_at,
    )


def _interaction_to_dto(row: InteractionRow) -> ChatInteraction:
    stages = [_stage_to_dto(s) for s in row.stages]
    return ChatInteraction(
        id=row.id,
        sequence=row.sequence,
        query=row.query,
        stages=stages,
        created_at=row.created_at,
    )


def _session_to_dto(row: SessionRow) -> ChatSession:
    interactions = [_interaction_to_dto(i) for i in row.interactions]
    return ChatSession(
        id=row.session_id,
        user_id=str(row.user_id),
        interactions=interactions,
        created_at=row.created_at,
    )


class SessionRepository:
    async def create_session(self, db: AsyncSession, user_id: int) -> ChatSession:
        session_id = str(uuid.uuid4())
        row = SessionRow(session_id=session_id, user_id=user_id)
        db.add(row)
        await db.commit()
        loaded = await self.get_session(db, session_id)
        assert loaded is not None
        return loaded

    async def get_session(self, db: AsyncSession, session_id: str) -> Optional[ChatSession]:
        stmt = (
            select(SessionRow)
            .where(SessionRow.session_id == session_id)
            .options(
                selectinload(SessionRow.interactions).selectinload(InteractionRow.stages),
            )
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return _session_to_dto(row) if row else None

    async def list_sessions(self, db: AsyncSession, user_id: int) -> list[ChatSession]:
        stmt = (
            select(SessionRow)
            .where(SessionRow.user_id == user_id)
            .options(
                selectinload(SessionRow.interactions).selectinload(InteractionRow.stages),
            )
            .order_by(SessionRow.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().unique().all()
        return [_session_to_dto(r) for r in rows]

    async def add_interaction(self, db: AsyncSession, session_id: str, query: str) -> ChatInteraction:
        max_seq_stmt = select(func.coalesce(func.max(InteractionRow.sequence), 0)).where(
            InteractionRow.session_id == session_id
        )
        max_seq = (await db.execute(max_seq_stmt)).scalar_one()
        next_seq = int(max_seq) + 1
        row = InteractionRow(session_id=session_id, sequence=next_seq, query=query)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        stmt = (
            select(InteractionRow)
            .where(InteractionRow.id == row.id)
            .options(selectinload(InteractionRow.stages))
        )
        loaded = (await db.execute(stmt)).scalar_one()
        return _interaction_to_dto(loaded)

    async def add_stage(
        self,
        db: AsyncSession,
        *,
        interaction_id: int,
        stage_name: str,
        scene_plan: dict,
        raw_scene_plan: dict,
    ) -> ChatStage:
        row = StageRow(
            interaction_id=interaction_id,
            stage_name=stage_name,
            scene_plan=dict(scene_plan),
            raw_scene_plan=dict(raw_scene_plan),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _stage_to_dto(row)

    async def get_last_stage(self, db: AsyncSession, session_id: str) -> Optional[ChatStage]:
        stmt = (
            select(StageRow)
            .join(InteractionRow, StageRow.interaction_id == InteractionRow.id)
            .where(InteractionRow.session_id == session_id)
            .order_by(StageRow.id.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return _stage_to_dto(row) if row else None

    async def get_interaction(
        self, db: AsyncSession, session_id: str, sequence: int
    ) -> Optional[ChatInteraction]:
        stmt = (
            select(InteractionRow)
            .where(
                InteractionRow.session_id == session_id,
                InteractionRow.sequence == sequence,
            )
            .options(selectinload(InteractionRow.stages))
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return _interaction_to_dto(row) if row else None
