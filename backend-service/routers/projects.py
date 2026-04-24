from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
import hashlib

from backend_service.schema.dto import Project, ProjectCreate, ProjectUpdate
from backend_service.dependencies import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])

projects_db = {}


@router.get("")
async def get_projects(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    user_projects = [p for p in projects_db.values() if p.get("user_id") == user_id]
    return {
        "status": "success",
        "projects": user_projects
    }


@router.get("/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    if project_id not in projects_db or projects_db[project_id].get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return {
        "status": "success",
        "project": projects_db[project_id]
    }


@router.post("")
async def create_project(req: ProjectCreate, user: dict = Depends(get_current_user)):
    project_id = hashlib.md5(f"{req.name}{datetime.now()}".encode()).hexdigest()[:12]
    now = datetime.now().isoformat()
    
    project = {
        "id": project_id,
        "name": req.name,
        "user_id": user["id"],
        "objects": [],
        "created_at": now,
        "updated_at": now
    }
    
    projects_db[project_id] = project
    
    return {
        "status": "success",
        "project": project
    }


@router.put("/{project_id}")
async def update_project(project_id: str, req: ProjectUpdate, user: dict = Depends(get_current_user)):
    if project_id not in projects_db or projects_db[project_id].get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    project = projects_db[project_id]
    updates = req.model_dump(exclude_unset=True)
    for key, value in updates.items():
        project[key] = value
    
    project["updated_at"] = datetime.now().isoformat()
    
    return {
        "status": "success",
        "project": project
    }


@router.delete("/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    if project_id not in projects_db or projects_db[project_id].get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    del projects_db[project_id]
    
    return {
        "status": "success",
        "message": "Проект удален"
    }
