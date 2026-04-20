from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "ainterior-models"
    S3_REGION: str = "us-east-1"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
