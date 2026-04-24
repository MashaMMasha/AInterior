from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .log import configure_logging, logger

# Project root: agents-service/obllomov/shared -> parents[3] == AInterior
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_obllomov_env = Path(__file__).resolve().parents[1] / ".env"
for _p in (_PROJECT_ROOT / ".env", _obllomov_env):
    if _p.is_file():
        load_dotenv(_p, override=False)


def _env_files() -> tuple[Path, ...]:
    return tuple(p for p in (_PROJECT_ROOT / ".env", _obllomov_env) if p.is_file())


class EnvConfig(BaseSettings):
    """Loads root `.env` so `S3_*` and app vars match the rest of the stack."""

    LOG_LEVEL: str = "DEBUG"
    HF_TOKEN: Optional[str] = None

    YANDEX_CLOUD_FOLDER: Optional[str] = None
    YANDEX_CLOUD_API_KEY: Optional[str] = None
    YANDEX_CLOUD_MODEL: Optional[str] = None

    OBJATHOR_ASSETS_BASE_DIR: str = "~/.objathor-assets"

    # When True, agents always use local disk (ignore S3) — use in Docker with a host mount.
    AGENTS_USE_LOCAL_ASSETS: bool = False

    DB_URL: str = "sqlite:///obllomov.db"
    RABBITMQ_URL: Optional[str] = None

    S3_BUCKET_NAME: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("S3_BUCKET_NAME", "S3_BUCKET"),
    )
    S3_KEY_PREFIX: str = "objathor-assets"
    S3_ENDPOINT_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("S3_ENDPOINT_URL", "S3_ENDPOINT"),
    )
    AWS_ACCESS_KEY_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AWS_ACCESS_KEY_ID", "S3_ACCESS_KEY"),
    )
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AWS_SECRET_ACCESS_KEY", "S3_SECRET_KEY"),
    )
    AWS_DEFAULT_REGION: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("AWS_DEFAULT_REGION", "S3_REGION"),
    )

    model_config = SettingsConfigDict(
        env_file=_env_files() or None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_database_config(self):
        configure_logging(level=self.LOG_LEVEL)
        
        for env_var, env_value in vars(self).items():
            if env_value is None:
                logger.warning(f"{env_var} is not set")
        return self

env = EnvConfig()
