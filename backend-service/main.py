from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from datetime import datetime

from backend_service.routers.projects import router as projects_router
from backend_service.routers.models import router as models_router
from backend_service.routers.ml import router as ml_router
from backend_service.services.s3_service import get_s3_service

app = FastAPI(
    title="AInterior Backend API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(models_router)
app.include_router(ml_router)

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return {
            "status": "ok",
            "service": "backend-service",
            "message": "Static file not found"
        }
    return FileResponse(str(index_path))


@app.get("/health")
async def health_check():
    try:
        s3_service = get_s3_service()
        s3_healthy = False
        try:
            s3_service.list_files(prefix="")
            s3_healthy = True
        except:
            pass
        
        return {
            "status": "healthy",
            "service": "backend-service",
            "timestamp": datetime.now().isoformat(),
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
            "service": "backend-service",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
