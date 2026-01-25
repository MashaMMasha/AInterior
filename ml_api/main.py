from ml_api.schema.dto import *

from ml_api.db.furniture_db import FURNITURE_DB

from ml_api.services.agents_service import AgentsService

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib
from datetime import datetime
import shutil


app = FastAPI(
    title="AInterior ML Agents API",
    version="0.1.0"
)

UPLOAD_DIR = Path("uploaded_models")
UPLOAD_DIR.mkdir(exist_ok=True)

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

agents_service = AgentsService()

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
        file_path = UPLOAD_DIR / safe_filename
        
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "status": "success",
            "filename": safe_filename,
            "original_filename": file.filename,
            "size": file_path.stat().st_size,
            "view_url": f"/view_model/{safe_filename}",
            "download_url": f"/uploaded_models/{safe_filename}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")

@app.get("/uploaded_models/{filename}")
async def get_uploaded_model(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Модель не найдена")
    return FileResponse(str(file_path), filename=filename)

@app.get("/list_models")
async def list_models():
    models = []
    for file_path in UPLOAD_DIR.glob("*"):
        if file_path.is_file():
            models.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                "url": f"/uploaded_models/{file_path.name}"
            })
    return {"models": models, "count": len(models)}

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

        output_dir = Path("generated_models")
        output_dir.mkdir(exist_ok=True)
        model_path = output_dir / f"{result['furniture_type']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.glb"
        result["mesh"].export(str(model_path))
        
        return {
            "status": "success",
            "model_id": f"model_{result['type']}_{datetime.now().timestamp()}",
            "model_info": result,
            "download_url": f"/download_model/{model_path}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {str(e)}")

@app.post("/auto_arrange", response_model=Dict[str, Any])
async def auto_arrange_furniture(request: TextRequest):
    try:

        scene = agents_service.auto_arrange_furniture(request.text)
        
        scenes_dir = Path("scenes")
        scenes_dir.mkdir(exist_ok=True)
        scene_id = hashlib.md5(f"{request.text}{datetime.now()}".encode()).hexdigest()[:12]
        scene_path = scenes_dir / f"scene_{scene_id}.glb"
        scene.export(str(scene_path))
        
        return {
            "status": "success",
            "scene_id": scene_id,
            "room_dimensions": request.dimensions,
            "scene_url": f"/download_scene/{scene_path.name}",
            "preview_url": f"/preview/{scene_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расстановки: {str(e)}")

@app.post("/edit_furniture")
async def edit_furniture(item: FurnitureItem, modifications: Dict[str, Any]):
    try:
        mesh = agents_service.edit_furniture(item, modifications)

        edit_dir = Path("edited_models")
        edit_dir.mkdir(exist_ok=True)
        edit_path = edit_dir / f"{item.type}_edited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.glb"
        mesh.export(str(edit_path))
        
        return {
            "status": "success",
            "edited_model_path": str(edit_path),
            "modifications_applied": list(modifications.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download_model/{filename}")
async def download_model(filename: str):
    file_path = Path("generated_models") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Модель не найдена")
    return FileResponse(str(file_path), filename=filename)


@app.get("/download_scene/{filename}")
async def download_scene(filename: str):
    file_path = Path("scenes") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Сцена не найдена")
    return FileResponse(str(file_path), filename=filename)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": len(FURNITURE_DB),
        "version": "0.1.0"
    }

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
