from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend_service.models.app_project import AppProjectRow

DEFAULT_PROJECT_NAME = "Мой проект"


def new_project_id() -> str:
    return secrets.token_hex(6)


def row_to_dict(row: AppProjectRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "user_id": row.user_id,
        "objects": list(row.objects) if row.objects is not None else [],
        "conversation_id": row.conversation_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_by_user(db: AsyncSession, user_id: int) -> list[AppProjectRow]:
    stmt = (
        select(AppProjectRow)
        .where(AppProjectRow.user_id == user_id)
        .order_by(AppProjectRow.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id_for_user(
    db: AsyncSession, project_id: str, user_id: int
) -> Optional[AppProjectRow]:
    stmt = select(AppProjectRow).where(
        AppProjectRow.id == project_id, AppProjectRow.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    user_id: int,
    name: str,
    objects: Optional[list[dict[str, Any]]] = None,
    project_id: Optional[str] = None,
) -> AppProjectRow:
    row = AppProjectRow(
        id=project_id or new_project_id(),
        user_id=user_id,
        name=name,
        objects=objects or [],
    )
    db.add(row)
    await db.flush()
    return row


async def ensure_at_least_one_project(db: AsyncSession, user_id: int) -> list[AppProjectRow]:
    rows = await list_by_user(db, user_id)
    if not rows:
        await create(db, user_id, DEFAULT_PROJECT_NAME, [])
        rows = await list_by_user(db, user_id)
    return rows


async def delete_row(db: AsyncSession, row: AppProjectRow) -> None:
    await db.execute(
        delete(AppProjectRow).where(
            AppProjectRow.id == row.id, AppProjectRow.user_id == row.user_id
        )
    )
    await db.flush()
