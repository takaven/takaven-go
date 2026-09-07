from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Takaven Go"
    database_url: str
    operator_password: SecretStr
    session_secret: SecretStr
    cookie_secure: bool = True
    session_hours: int = Field(default=12, ge=1, le=168)
    log_level: str = "INFO"
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None

    @field_validator("operator_password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 12:
            raise ValueError("OPERATOR_PASSWORD must contain at least 12 characters")
        return value

    @field_validator("session_secret")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
