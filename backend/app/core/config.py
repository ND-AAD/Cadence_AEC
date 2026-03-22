"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://cadence:cadence_dev@localhost:5432/cadence"
    )
    DATABASE_URL_SYNC: str = "postgresql://cadence:cadence_dev@localhost:5432/cadence"

    # Application
    APP_NAME: str = "Cadence"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # LLM Classification (WP-15)
    ANTHROPIC_API_KEY: str | None = None
    CLASSIFICATION_MODEL: str = "claude-haiku-4-5-20251001"
    CLASSIFICATION_ENABLED: bool = True

    # LLM Extraction (WP-17)
    EXTRACTION_MODEL: str = "claude-sonnet-4-5-20250929"
    EXTRACTION_MAX_TOKENS: int = 1024
    EXTRACTION_TEMPERATURE: float = 0.2
    EXTRACTION_ENABLED: bool = True

    # Auth
    JWT_SECRET: str = "cadence-dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Registration
    ALPHA_INVITE_CODE: str = "CADENCE-ALPHA"

    class Config:
        env_file = ".env"

    def model_post_init(self, __context) -> None:
        """Fix Render's database URL format for asyncpg."""
        # Render provides postgresql:// — asyncpg needs postgresql+asyncpg://
        if (
            self.DATABASE_URL.startswith("postgresql://")
            and "+asyncpg" not in self.DATABASE_URL
        ):
            object.__setattr__(
                self,
                "DATABASE_URL",
                self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1),
            )
        # Ensure SYNC URL uses plain postgresql://
        if "+asyncpg" in self.DATABASE_URL_SYNC:
            object.__setattr__(
                self,
                "DATABASE_URL_SYNC",
                self.DATABASE_URL_SYNC.replace(
                    "postgresql+asyncpg://", "postgresql://", 1
                ),
            )


settings = Settings()
