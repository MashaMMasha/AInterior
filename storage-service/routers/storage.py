from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional

from storage_service.services.s3_service import get_s3_service
from storage_service.dependencies import get_current_user

router = APIRouter(prefix="/storage", tags=["storage"])


class PresignedUrlResponse(BaseModel):
    url: str
    object_key: str
    expires_in: int


class FileMetadataResponse(BaseModel):
    key: str
    size: int
    content_type: str
    last_modified: str
    metadata: dict


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    folder: Optional[str] = "uploads",
    user: dict = Depends(get_current_user)
):
    """Загрузить файл в S3"""
    try:
        s3_service = get_s3_service()
        
        # Формируем ключ файла
        object_key = f"{folder}/{user['id']}/{file.filename}"
        
        # Загружаем файл
        s3_service.upload_fileobj(
            file.file,
            object_key,
            metadata={"user_id": str(user['id']), "filename": file.filename},
            content_type=file.content_type or "application/octet-stream"
        )
        
        # Получаем presigned URL для скачивания
        download_url = s3_service.get_presigned_url(object_key, expiration=3600)
        
        return {
            "status": "success",
            "object_key": object_key,
            "filename": file.filename,
            "download_url": download_url,
            "size": file.size
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/download/{object_key:path}")
async def get_download_url(
    object_key: str,
    expiration: int = 3600,
    user: dict = Depends(get_current_user)
):
    """Получить presigned URL для скачивания файла"""
    try:
        s3_service = get_s3_service()
        
        if not s3_service.file_exists(object_key):
            raise HTTPException(status_code=404, detail="File not found")
        
        download_url = s3_service.get_presigned_url(object_key, expiration=expiration)
        
        return PresignedUrlResponse(
            url=download_url,
            object_key=object_key,
            expires_in=expiration
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate URL: {str(e)}")


@router.get("/upload-url")
async def get_upload_url(
    filename: str,
    folder: Optional[str] = "uploads",
    content_type: str = "application/octet-stream",
    user: dict = Depends(get_current_user)
):
    """Получить presigned URL для загрузки файла"""
    try:
        s3_service = get_s3_service()
        
        object_key = f"{folder}/{user['id']}/{filename}"
        
        upload_data = s3_service.get_presigned_upload_url(
            object_key,
            expiration=3600,
            content_type=content_type
        )
        
        return {
            "status": "success",
            "upload_url": upload_data['url'],
            "fields": upload_data['fields'],
            "object_key": object_key
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")


@router.delete("/{object_key:path}")
async def delete_file(
    object_key: str,
    user: dict = Depends(get_current_user)
):
    """Удалить файл из S3"""
    try:
        s3_service = get_s3_service()
        
        # Проверяем что файл существует
        if not s3_service.file_exists(object_key):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Проверяем что файл принадлежит пользователю (по метаданным или пути)
        if f"/{user['id']}/" not in object_key:
            metadata = s3_service.get_file_metadata(object_key)
            if metadata.get('metadata', {}).get('user_id') != str(user['id']):
                raise HTTPException(status_code=403, detail="Access denied")
        
        s3_service.delete_file(object_key)
        
        return {"status": "success", "message": "File deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.get("/list")
async def list_files(
    prefix: Optional[str] = "",
    user: dict = Depends(get_current_user)
):
    """Получить список файлов пользователя"""
    try:
        s3_service = get_s3_service()
        
        # Ограничиваем поиск файлами пользователя
        user_prefix = f"{prefix}/{user['id']}/" if prefix else f"uploads/{user['id']}/"
        
        files = s3_service.list_files(prefix=user_prefix)
        
        return {
            "status": "success",
            "files": files,
            "count": len(files)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.get("/metadata/{object_key:path}", response_model=FileMetadataResponse)
async def get_file_metadata(
    object_key: str,
    user: dict = Depends(get_current_user)
):
    """Получить метаданные файла"""
    try:
        s3_service = get_s3_service()
        
        if not s3_service.file_exists(object_key):
            raise HTTPException(status_code=404, detail="File not found")
        
        metadata = s3_service.get_file_metadata(object_key)
        
        return FileMetadataResponse(
            key=object_key,
            size=metadata['size'],
            content_type=metadata['content_type'],
            last_modified=metadata['last_modified'],
            metadata=metadata['metadata']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")
