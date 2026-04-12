from contextlib import asynccontextmanager
from sqlalchemy import text

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth_service.database import engine, Base
from auth_service.routers.auth import router as auth_router


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
    title="AInterior Auth Service",
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


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "auth-service",
        "version": "0.1.0"
    }
