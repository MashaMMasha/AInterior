from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    AUTH_SERVICE_URL: str = "http://localhost:8001"

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ainterior"
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: str = "password"
    AGENTS_SERVICE_URL: str = "http://agents-service:8006"


settings = Settings()

DATABASE_URL = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
