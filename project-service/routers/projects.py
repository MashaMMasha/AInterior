from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    objects: Optional[List] = None


class Project(BaseModel):
    id: str
    name: str
    user_id: str
    objects: List
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=dict)
async def get_projects():
    """Получить список всех проектов пользователя"""
    return {
        "status": "success",
        "projects": [
            {
                "id": "1",
                "name": "Мой проект",
                "user_id": "user123",
                "objects": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        ]
    }


@router.get("/{project_id}", response_model=dict)
async def get_project(project_id: str):
    """Получить информацию о конкретном проекте"""
    return {
        "status": "success",
        "project": {
            "id": project_id,
            "name": "Мой проект",
            "user_id": "user123",
            "objects": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    }


@router.post("", response_model=dict)
async def create_project(req: ProjectCreate):
    """Создать новый проект"""
    return {
        "status": "success",
        "project": {
            "id": "new_id",
            "name": req.name,
            "user_id": "user123",
            "objects": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    }


@router.put("/{project_id}", response_model=dict)
async def update_project(project_id: str, req: ProjectUpdate):
    """Обновить данные проекта"""
    return {
        "status": "success",
        "project": {
            "id": project_id,
            "name": req.name or "Updated Project",
            "user_id": "user123",
            "objects": req.objects or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    }


@router.delete("/{project_id}", response_model=dict)
async def delete_project(project_id: str):
    """Удалить проект"""
    return {
        "status": "success",
        "message": f"Проект {project_id} удален"
    }
