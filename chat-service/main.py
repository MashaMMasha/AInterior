from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from chat_service.routers import chat

app = FastAPI(
    title="AInterior Chat Service",
    description="Chat service with AI assistant (mock responses)",
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
app.include_router(chat.router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "chat-service",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0",
        "mode": "mock"  # Указываем что используются моки
    }


@app.get("/")
async def root():
    return {
        "service": "AInterior Chat Service",
        "version": "0.1.0",
        "docs": "/docs",
        "mode": "mock"
    }
