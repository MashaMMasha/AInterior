from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    # Optional legacy HTTP API (e.g. ml_service on 8002). Not docker render-service, not scripts/render/ viewers.
    RENDER_SERVICE_URL: str = "http://localhost:8002"
    
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "ainterior-models"
    S3_REGION: str = "us-east-1"
    
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

RABBITMQ_URL = f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"
