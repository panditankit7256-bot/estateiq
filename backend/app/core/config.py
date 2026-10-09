"""Application settings, read from environment variables (see .env.example)."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


def _find_config_dir() -> Path:
    env = os.getenv("CONFIG_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "facilities").is_dir():
            return parent / "config"
    return Path("/app/config")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./estateiq.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-change-me")
    jwt_minutes: int = int(os.getenv("JWT_MINUTES", "480"))
    seed_days: int = int(os.getenv("SEED_DAYS", "90"))
    default_facility: str = os.getenv("DEFAULT_FACILITY", "engineering_college")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    config_dir: Path = _find_config_dir()
    # Fixed reference "now" keeps demos and tests reproducible. Empty = real clock.
    fixed_now: str = os.getenv("FIXED_NOW", "")


settings = Settings()
