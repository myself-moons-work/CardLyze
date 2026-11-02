"""Application configuration settings for CardLyze."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    HOST: str = os.getenv("CARDLYZE_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("CARDLYZE_PORT", "8000"))
    MAX_UPLOAD_SIZE_BYTES: int = int(
        os.getenv("CARDLYZE_MAX_UPLOAD_SIZE_BYTES", str(50 * 1024 * 1024))  # 50 MB
    )
    SESSION_TTL_SECONDS: int = int(
        os.getenv("CARDLYZE_SESSION_TTL_SECONDS", str(1800))  # 30 minutes
    )
    MAX_CONCURRENT_SESSIONS: int = int(
        os.getenv("CARDLYZE_MAX_CONCURRENT_SESSIONS", "10")
    )
    SWEEPER_INTERVAL_SECONDS: int = int(
        os.getenv("CARDLYZE_SWEEPER_INTERVAL_SECONDS", "60")
    )


settings = Settings()

