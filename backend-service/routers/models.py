from fastapi import APIRouter, HTTPException, File, UploadFile, Depends
from fastapi.responses import RedirectResponse
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
import os

from backend_service.services.s3_service import get_s3_service
from backend_service.dependencies import get_current_user

router = APIRouter(prefix="", tags=["models"])

s3_service = get_s3_service()


@router.post("/upload_model")
async def upload_model(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
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
                "content_type": file.content_type or "unknown",
                "user_id": str(user["id"])
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


@router.get("/uploaded_models/{filename}")
async def get_uploaded_model(filename: str, user: dict = Depends(get_current_user)):
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


@router.get("/list_models")
async def list_models(user: dict = Depends(get_current_user)):
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


@router.get("/generated_models/{filename}")
async def get_generated_model(filename: str, user: dict = Depends(get_current_user)):
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


@router.get("/download_model/{filename}")
async def download_model(filename: str, user: dict = Depends(get_current_user)):
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


@router.get("/download_scene/{filename}")
async def download_scene(filename: str, user: dict = Depends(get_current_user)):
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
