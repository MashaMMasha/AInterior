from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)


class EnvConfig(BaseSettings):
    LOG_LEVEL: str = "DEBUG"

    HF_TOKEN: Optional[str] = None
    YANDEX_CLOUD_FOLDER: Optional[str] = None
    YANDEX_CLOUD_API_KEY: Optional[str] = None
    YANDEX_CLOUD_MODEL: Optional[str] = None

    model_config = SettingsConfigDict(env_file=env_path, env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_database_config(self):
        for env_var, env_value in vars(self).items():
            if env_value is None:
                raise UserWarning(f"{env_var} is not set")

env = EnvConfig()
