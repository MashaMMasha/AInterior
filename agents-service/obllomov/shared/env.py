from pathlib import Path
from typing import Optional
from warnings import warn

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .log import configure_logging, logger

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)


class EnvConfig(BaseSettings):
    LOG_LEVEL: str = "DEBUG"
    HF_TOKEN: Optional[str] = None
    
    YANDEX_CLOUD_FOLDER: Optional[str] = None
    YANDEX_CLOUD_API_KEY: Optional[str] = None
    YANDEX_CLOUD_MODEL: Optional[str] = None

    OBJATHOR_ASSETS_BASE_DIR: str = "~/.objathor-assets"

    DB_URL: str = "sqlite:///obllomov.db"
    RABBITMQ_URL: Optional[str] = None

    S3_BUCKET_NAME: Optional[str] = None
    S3_KEY_PREFIX: str = "objathor-assets"
    S3_ENDPOINT_URL: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "ru-central1"

    model_config = SettingsConfigDict(env_file=env_path, env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_database_config(self):
        configure_logging(level=self.LOG_LEVEL)
        
        for env_var, env_value in vars(self).items():
            if env_value is None:
                logger.warning(f"{env_var} is not set")
        return self

env = EnvConfig()
