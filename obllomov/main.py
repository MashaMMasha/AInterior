import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from obllomov.db.furniture_db import FURNITURE_DB
from obllomov.schema.dto import *
from obllomov.services.obllomov import ObLLoMov
from obllomov.agents.llms import ChatYandexQwen


from os import getenv
from dotenv import load_dotenv

load_dotenv()


app = FastAPI(
    title="AInterior ML Agents API",
    version="0.1.0"
)

llm = ChatYandexQwen(
    api_key=getenv("YANDEX_CLOUD_API_KEY"),
    base_url="https://ai.api.cloud.yandex.net/v1",
    project=getenv("YANDEX_CLOUD_FOLDER"),
    model_name=getenv("YANDEX_CLOUD_MODEL")
)

obLLoMov = ObLLoMov(llm)

@app.post("/chat", response_model=ChatMessage)
async def chat(request: ChatMessage):
    try:
        response = obLLoMov.parse_request(request.content)
    
        return {
            "content": response.content,
            "session_id": request.session_id,
            "role": "ai"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")


@app.post("/generate_furniture", response_model=Dict[str, Any])
async def generate_furniture(request: TextRequest):
    try:
        result = obLLoMov.generate_from_text(request.text)

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

        scene = obLLoMov.auto_arrange_furniture(request.text)
        
        scenes_dir = Path("scenes")
        scenes_dir.mkdir(exist_ok=True)
        scene_id = hashlib.md5(f"{request.text}{datetime.now()}".encode()).hexdigest()[:12]
        scene_path = scenes_dir / f"scene_{scene_id}.glb"
        scene.export(str(scene_path))
        
        return {
            "status": "success",
            "scene_id": scene_id,
            "room_dimensions": request.dimensions,
            # "style": parsed["style"],
            # "furniture_count": len(placements),
            # "placements": [item.dict() for item in placements],
            "scene_url": f"/download_scene/{scene_path.name}",
            "preview_url": f"/preview/{scene_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расстановки: {str(e)}")

@app.post("/edit_furniture")
async def edit_furniture(item: FurnitureItem, modifications: Dict[str, Any]):
    try:
        mesh = obLLoMov.edit_furniture(item, modifications)

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
