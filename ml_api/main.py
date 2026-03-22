from ml_api.schema.dto import *

from ml_api.db.furniture_db import FURNITURE_DB

from ml_api.services.agents_service import AgentsService
from ml_api.services.s3_service import get_s3_service
from ml_api.database import engine, Base
from ml_api.routers.auth import router as auth_router
from ml_api.services.auth_service import decode_token

from fastapi import FastAPI, HTTPException, File, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import asynccontextmanager
from sqlalchemy import text
import hashlib
from datetime import datetime
import shutil
import tempfile
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS users"))
            await conn.run_sync(Base.metadata.create_all)
        print("DB: таблицы созданы")
    except Exception as e:
        print(f"DB: PostgreSQL недоступен ({e}). Авторизация не будет работать до подключения к БД.")
    yield
    await engine.dispose()


app = FastAPI(
    title="AInterior ML Agents API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

_OPEN_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}
_OPEN_PREFIXES = ("/auth/", "/static/")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PREFIXES):
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Требуется авторизация"})

    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return JSONResponse(status_code=401, content={"detail": "Невалидный токен"})

    request.state.user_id = int(payload["sub"])
    request.state.user_email = payload.get("email")
    return await call_next(request)


STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

agents_service = AgentsService()
s3_service = get_s3_service()

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return """
        <html>
        <head><title>AInterior - 3D Viewer</title></head>
        <body>
            <h1>Статический файл не найден</h1>
            <p>Пожалуйста, создайте файл static/index.html</p>
        </body>
        </html>
        """
    return FileResponse(str(index_path))

@app.post("/upload_model")
async def upload_model(file: UploadFile = File(...)):
    try:
        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = ['.glb', '.gltf', '.obj']
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Неподдерживаемый формат. Поддерживаются: {', '.join(allowed_extensions)}"
            )
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{file.filename}"
        s3_key = f"uploaded/{safe_filename}"
        
        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
            tmp_path = tmp.name
            shutil.copyfileobj(file.file, tmp)
        
        try:
            content_type_map = {
                '.glb': 'model/gltf-binary',
                '.gltf': 'model/gltf+json',
                '.obj': 'text/plain'
            }
            content_type = content_type_map.get(file_ext, 'application/octet-stream')
            
            metadata = {
                "original_filename": file.filename,
                "uploaded_at": datetime.now().isoformat(),
                "content_type": file.content_type or "unknown"
            }
            
            s3_service.upload_file(
                tmp_path,
                s3_key,
                metadata=metadata,
                content_type=content_type
            )
            
            file_size = Path(tmp_path).stat().st_size
            download_url = s3_service.get_presigned_url(s3_key, expiration=3600)
            
            return {
                "status": "success",
                "filename": safe_filename,
                "original_filename": file.filename,
                "s3_key": s3_key,
                "size": file_size,
                "storage": "s3",
                "download_url": download_url,
                "expires_in": 3600
            }
        
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")

@app.get("/uploaded_models/{filename}")
async def get_uploaded_model(filename: str):
    try:
        s3_key = f"uploaded/{filename}"
        
        if not s3_service.file_exists(s3_key):
            raise HTTPException(status_code=404, detail="Модель не найдена в хранилище")
        
        download_url = s3_service.get_presigned_url(s3_key, expiration=3600)
        return RedirectResponse(url=download_url)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения модели: {str(e)}")

@app.get("/list_models")
async def list_models():
    try:
        files = s3_service.list_files(prefix="uploaded/")
        
        models = []
        for file_info in files:
            download_url = s3_service.get_presigned_url(
                file_info['key'], 
                expiration=3600
            )
            
            models.append({
                "filename": Path(file_info['key']).name,
                "s3_key": file_info['key'],
                "size": file_info['size'],
                "modified": file_info['last_modified'],
                "url": download_url,
                "storage": "s3"
            })
        
        return {
            "status": "success",
            "models": models,
            "count": len(models),
            "storage": "s3"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка: {str(e)}")

@app.post("/generate", response_model=Dict[str, Any])
async def generate_model(request: TextRequest):
    try:
        parsed = agents_service.parse_request(request.text)
        
        if parsed.get('furniture') and len(parsed['furniture']) > 0:
            furniture_item = parsed['furniture'][0]
            result = agents_service.generate_from_text(
                f"{furniture_item.get('type', 'furniture')} в стиле {parsed.get('style', 'современный')}"
            )
            
            return {
                "status": "success",
                "message": f"Создана модель: {result['furniture_type']}",
                "s3_key": result["s3_key"],
                "download_url": result["download_url"],
                "storage": "s3",
                "furniture_info": {
                    "type": result['furniture_type'],
                    "color": result.get('color'),
                    "dimensions": result.get('dimensions')
                },
                "expires_in": 3600
            }
        else:
            return {
                "status": "success",
                "message": "Опишите подробнее какую мебель вы хотите создать, например: 'добавь современный диван серого цвета'"
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Не удалось сгенерировать модель. Попробуйте переформулировать запрос. Ошибка: {str(e)}"
        }

@app.get("/generated_models/{filename}")
async def get_generated_model(filename: str):
    try:
        s3_key = f"models/{filename}"
        
        if not s3_service.file_exists(s3_key):
            raise HTTPException(status_code=404, detail="Модель не найдена")
        
        download_url = s3_service.get_presigned_url(s3_key, expiration=3600)
        return RedirectResponse(url=download_url)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.post("/chat", response_model=Dict[str, Any])
async def chat(request: TextRequest):
    try:
        parsed = agents_service.parse_request(request.text)
        return {
            "status": "success",
            "request_id": hashlib.md5(request.text.encode()).hexdigest()[:8],
            "parsed": parsed,
            "message": f"Определено {len(parsed['furniture'])} предметов в стиле '{parsed['style']}'"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")

@app.post("/generate_furniture", response_model=Dict[str, Any])
async def generate_furniture(request: TextRequest):
    try:
        result = agents_service.generate_from_text(request.text)

        return {
            "status": "success",
            "model_id": f"model_{result['furniture_type']}_{int(datetime.now().timestamp())}",
            "s3_key": result["s3_key"],
            "download_url": result["download_url"],
            "storage": "s3",
            "furniture_info": {
                "type": result['furniture_type'],
                "color": result.get('color'),
                "dimensions": result.get('dimensions')
            },
            "expires_in": 3600
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {str(e)}")

@app.post("/auto_arrange", response_model=Dict[str, Any])
async def auto_arrange_furniture(request: TextRequest):
    try:
        result = agents_service.auto_arrange_furniture(request.text)
        
        return {
            "status": "success",
            "scene_id": hashlib.md5(f"{request.text}{datetime.now()}".encode()).hexdigest()[:12],
            "s3_key": result["s3_key"],
            "download_url": result["download_url"],
            "storage": "s3",
            "placements": result["placements"],
            "furniture_count": len(result["placements"]),
            "expires_in": 3600
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расстановки: {str(e)}")

@app.post("/edit_furniture")
async def edit_furniture(item: FurnitureItem, modifications: Dict[str, Any]):
    try:
        mesh = agents_service.edit_furniture(item, modifications)

        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as tmp:
            tmp_path = tmp.name
            mesh.export(tmp_path)
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            s3_key = f"edited/{item.type}_edited_{timestamp}.glb"
            
            metadata = {
                "furniture_type": item.type,
                "edited_at": datetime.now().isoformat(),
                "modifications": str(list(modifications.keys()))
            }
            
            s3_service.upload_file(
                tmp_path,
                s3_key,
                metadata=metadata,
                content_type='model/gltf-binary'
            )
            
            download_url = s3_service.get_presigned_url(s3_key, expiration=3600)
            
            return {
                "status": "success",
                "s3_key": s3_key,
                "download_url": download_url,
                "storage": "s3",
                "modifications_applied": list(modifications.keys()),
                "expires_in": 3600
            }
        
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download_model/{filename}")
async def download_model(filename: str):
    try:
        s3_key = f"models/{filename}"
        
        if not s3_service.file_exists(s3_key):
            raise HTTPException(status_code=404, detail="Модель не найдена")
        
        download_url = s3_service.get_presigned_url(s3_key, expiration=3600)
        return RedirectResponse(url=download_url)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download_scene/{filename}")
async def download_scene(filename: str):
    try:
        s3_key = f"scenes/{filename}"
        
        if not s3_service.file_exists(s3_key):
            raise HTTPException(status_code=404, detail="Сцена не найдена")
        
        download_url = s3_service.get_presigned_url(s3_key, expiration=3600)
        return RedirectResponse(url=download_url)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    try:
        s3_healthy = False
        try:
            s3_service.list_files(prefix="")
            s3_healthy = True
        except:
            pass
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "models_loaded": len(FURNITURE_DB),
            "version": "0.1.0",
            "storage": {
                "type": "s3",
                "healthy": s3_healthy,
                "bucket": s3_service.bucket_name,
                "endpoint": s3_service.endpoint_url
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

projects_db = {}

class Project(BaseModel):
    id: str
    name: str
    objects: List[Dict[str, Any]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@app.get("/projects")
async def get_projects(request: Request):
    user_id = request.state.user_id
    user_projects = [p for p in projects_db.values() if p.get("user_id") == user_id]
    return {
        "status": "success",
        "projects": user_projects
    }

@app.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request):
    if project_id not in projects_db or projects_db[project_id].get("user_id") != request.state.user_id:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return {
        "status": "success",
        "project": projects_db[project_id]
    }

@app.post("/projects")
async def create_project(name: str, request: Request):
    project_id = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:12]
    now = datetime.now().isoformat()
    
    project = {
        "id": project_id,
        "name": name,
        "user_id": request.state.user_id,
        "objects": [],
        "created_at": now,
        "updated_at": now
    }
    
    projects_db[project_id] = project
    
    return {
        "status": "success",
        "project": project
    }

@app.put("/projects/{project_id}")
async def update_project(project_id: str, project: Project, request: Request):
    if project_id not in projects_db or projects_db[project_id].get("user_id") != request.state.user_id:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    project.updated_at = datetime.now().isoformat()
    project_data = project.dict()
    project_data["user_id"] = request.state.user_id
    projects_db[project_id] = project_data
    
    return {
        "status": "success",
        "project": projects_db[project_id]
    }

@app.delete("/projects/{project_id}")
async def delete_project(project_id: str, request: Request):
    if project_id not in projects_db or projects_db[project_id].get("user_id") != request.state.user_id:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    del projects_db[project_id]
    
    return {
        "status": "success",
        "message": "Проект удален"
    }

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
