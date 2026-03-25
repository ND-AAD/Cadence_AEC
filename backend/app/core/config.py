"""Application configuration via environment variables."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    # Database — Render provides postgresql://, we need postgresql+asyncpg://
    DATABASE_URL: str = (
        "postgresql+asyncpg://cadence:cadence_dev@localhost:5432/cadence"
    )
    DATABASE_URL_SYNC: str = "postgresql://cadence:cadence_dev@localhost:5432/cadence"

    @property
    def database_url_async(self) -> str:
        """DATABASE_URL guaranteed to use asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Application
    APP_NAME: str = "Cadence"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # CORS — stored as comma-separated string, split into list via property
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

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
