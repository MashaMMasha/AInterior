from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from storage_service.routers import storage
from storage_service.services.s3_service import get_s3_service

app = FastAPI(
    title="AInterior Storage Service",
    description="File storage service (S3/MinIO)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(storage.router)


@app.get("/health")
async def health_check():
    s3_service = get_s3_service()
    
    s3_healthy = False
    try:
        s3_service.list_files(prefix="")
        s3_healthy = True
    except:
        pass
    
    return {
        "status": "healthy" if s3_healthy else "degraded",
        "service": "storage-service",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0",
        "storage": {
            "type": "s3",
            "healthy": s3_healthy,
            "bucket": s3_service.bucket_name,
            "endpoint": s3_service.endpoint_url
        }
    }


@app.get("/")
async def root():
    return {
        "service": "AInterior Storage Service",
        "version": "0.1.0",
        "docs": "/docs"
    }
