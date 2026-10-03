"""Validated application settings."""

from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Settings sourced from the process environment."""

    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

    database_url: str = ""
    database_host: str = "db"
    database_port: int = 5432
    database_name: str = "biblio_tpv"
    database_user: str = "biblio"
    database_password: SecretStr | None = None
    app_secret: SecretStr
    app_env: str = "production"
    app_timezone: str = "Europe/Madrid"
    app_currency: str = "EUR"
    prices_include_tax: bool = True
    cookie_secure: bool = True
    allowed_origin: str = "http://localhost:8080"
    bootstrap_admin_username: str = ""
    bootstrap_admin_password: SecretStr | None = None
    session_max_age_seconds: int = 28800

    @field_validator("app_secret")
    @classmethod
    def secret_must_be_long(cls, value: SecretStr) -> SecretStr:
        """Reject weak signing secrets before serving requests."""
        if len(value.get_secret_value()) < 32:
            raise ValueError("APP_SECRET debe tener al menos 32 caracteres")
        return value

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        """Build an escaped PostgreSQL URL from discrete credentials when needed."""
        if not self.database_url:
            if self.database_password is None:
                raise ValueError("Define DATABASE_URL o DATABASE_PASSWORD")
            self.database_url = URL.create(
                "postgresql+psycopg",
                username=self.database_user,
                password=self.database_password.get_secret_value(),
                host=self.database_host,
                port=self.database_port,
                database=self.database_name,
            ).render_as_string(hide_password=False)
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for this process."""
    return Settings()