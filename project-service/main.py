from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from project_service.routers import projects

app = FastAPI(
    title="AInterior Project Service",
    description="Project management service",
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
app.include_router(projects.router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "project-service",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0"
    }


@app.get("/")
async def root():
    return {
        "service": "AInterior Project Service",
        "version": "0.1.0",
        "docs": "/docs"
    }
