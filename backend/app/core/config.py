"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cadence:cadence_dev@localhost:5432/cadence"
    DATABASE_URL_SYNC: str = "postgresql://cadence:cadence_dev@localhost:5432/cadence"

    # Application
    APP_NAME: str = "Cadence"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
