from ml_service.schema.dto import *

from ml_service.db.furniture_db import FURNITURE_DB

from ml_service.services.agents_service import AgentsService
from ml_service.services.s3_service import get_s3_service
from ml_service.services.rabbitmq_service import get_rabbitmq_service
from ml_service.database import get_db_session, GenerationProgress

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import uuid
import asyncio


app = FastAPI(
    title="AInterior ML Service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agents_service = AgentsService()
s3_service = get_s3_service()
rabbitmq_service = get_rabbitmq_service()


@app.on_event("startup")
async def startup():
    await rabbitmq_service.connect()


@app.on_event("shutdown")
async def shutdown():
    await rabbitmq_service.close()


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


@app.post("/chat", response_model=Dict[str, Any])
async def chat(request: TextRequest):
    try:
        parsed = agents_service.parse_request(request.text)
        import hashlib
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
        import hashlib
        
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


@app.post("/generate_scene", response_model=Dict[str, Any])
async def generate_scene(
    request: TextRequest,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        generation_id = uuid.uuid4()
        
        progress = GenerationProgress(
            generation_id=generation_id,
            user_id=None,
            query=request.text,
            status='pending',
            scene_json={}
        )
        db.add(progress)
        await db.commit()
        
        asyncio.create_task(
            agents_service.generate_scene_streaming(
                generation_id=str(generation_id),
                query=request.text
            )
        )
        
        return {
            "status": "success",
            "generation_id": str(generation_id),
            "message": "Генерация сцены начата"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка запуска генерации: {str(e)}")


@app.get("/generation/{generation_id}", response_model=Dict[str, Any])
async def get_generation_status(
    generation_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        result = await db.execute(
            select(GenerationProgress).where(GenerationProgress.generation_id == uuid.UUID(generation_id))
        )
        progress = result.scalar_one_or_none()
        
        if not progress:
            raise HTTPException(status_code=404, detail="Generation not found")
        
        return {
            "generation_id": str(progress.generation_id),
            "status": progress.status,
            "current_step": progress.current_step,
            "completed_steps": progress.completed_steps,
            "total_steps": progress.total_steps,
            "scene_json": progress.scene_json,
            "error_message": progress.error_message,
            "created_at": progress.created_at.isoformat(),
            "updated_at": progress.updated_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")


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
            "service": "ml-service",
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
            "service": "ml-service",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
