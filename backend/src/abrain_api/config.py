from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings; local Sibyl needs no credentials."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="ABRAIN_ENV"
    )
    host: str = Field(default="127.0.0.1", validation_alias="ABRAIN_HOST")
    port: int = Field(default=8000, validation_alias="ABRAIN_PORT", ge=1, le=65535)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3125",
            "http://127.0.0.1:3125",
        ],
        validation_alias="ABRAIN_CORS_ORIGINS",
    )
    memory_enabled: bool = Field(default=False, validation_alias="ABRAIN_MEMORY_ENABLED")
    sibyl_db_path: Path = Field(
        default=Path(".data/abrain-memory.sqlite3"), validation_alias="ABRAIN_SIBYL_DB_PATH"
    )
    model_provider: Literal["disabled", "gemini"] = Field(
        default="disabled", validation_alias="ABRAIN_MODEL_PROVIDER"
    )
    agent_provider: Literal["local", "gemini"] = Field(
        default="local", validation_alias="ABRAIN_AGENT_PROVIDER"
    )
    gemini_api_key: SecretStr | None = Field(default=None, validation_alias="ABRAIN_GEMINI_API_KEY")
    gemini_model: str = Field(
        default="gemini-3.5-flash-lite", validation_alias="ABRAIN_GEMINI_MODEL"
    )
    model_timeout_seconds: float = Field(
        default=20.0, validation_alias="ABRAIN_MODEL_TIMEOUT_SECONDS", gt=0, le=120
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            origins = [item.strip() for item in value.split(",") if item.strip()]
            if not origins:
                raise ValueError("ABRAIN_CORS_ORIGINS must contain at least one origin")
            return origins
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
