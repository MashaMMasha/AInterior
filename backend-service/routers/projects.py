from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend_service.dependencies import get_current_user
from backend_service.db import get_db
from backend_service.schema.dto import ProjectCreate, ProjectUpdate
from backend_service.repositories import app_projects as projects_repo

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def get_projects(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список проектов; при первом обращении создаётся «Мой проект» и сохраняется в БД."""
    user_id = user["id"]
    rows = await projects_repo.ensure_at_least_one_project(db, user_id)
    await db.commit()
    return {
        "status": "success",
        "projects": [projects_repo.row_to_dict(r) for r in rows],
    }


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await projects_repo.get_by_id_for_user(db, project_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return {"status": "success", "project": projects_repo.row_to_dict(row)}


@router.post("")
async def create_project(
    req: ProjectCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await projects_repo.create(db, user["id"], req.name, [])
    await db.commit()
    await db.refresh(row)
    return {"status": "success", "project": projects_repo.row_to_dict(row)}


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    req: ProjectUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await projects_repo.get_by_id_for_user(db, project_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Проект не найден")

    updates = req.model_dump(exclude_unset=True)
    if "name" in updates:
        row.name = updates["name"]
    if "objects" in updates:
        row.objects = updates["objects"]
    if "conversation_id" in updates:
        row.conversation_id = updates["conversation_id"]
    row.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(row)
    return {"status": "success", "project": projects_repo.row_to_dict(row)}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await projects_repo.get_by_id_for_user(db, project_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Проект не найден")

    await projects_repo.delete_row(db, row)
    await db.commit()
    return {"status": "success", "message": "Проект удален"}
