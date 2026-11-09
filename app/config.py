"""Application configuration settings for CardLyze."""

import os
from dataclasses import dataclass
from typing import Optional


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
        os.getenv("MAX_SESSIONS", os.getenv("CARDLYZE_MAX_CONCURRENT_SESSIONS", "2"))
    )
    MAX_CONCURRENT_PARSES: int = int(
        os.getenv("MAX_PARALLEL_PARSES", os.getenv("CARDLYZE_MAX_CONCURRENT_PARSES", "1"))
    )
    MAX_CONCURRENT_EXPORTS: int = int(
        os.getenv("MAX_PARALLEL_EXPORTS", os.getenv("CARDLYZE_MAX_CONCURRENT_EXPORTS", "1"))
    )
    PARSE_SEMAPHORE_TIMEOUT_SECONDS: float = float(
        os.getenv("CARDLYZE_PARSE_SEMAPHORE_TIMEOUT", "30.0")
    )
    EXPORT_SEMAPHORE_TIMEOUT_SECONDS: float = float(
        os.getenv("CARDLYZE_EXPORT_SEMAPHORE_TIMEOUT", "30.0")
    )
    SWEEPER_INTERVAL_SECONDS: int = int(
        os.getenv("CARDLYZE_SWEEPER_INTERVAL_SECONDS", "60")
    )
    ALLOW_NON_LOOPBACK: bool = os.getenv("ALLOW_NON_LOOPBACK", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    # -------------------------------------------------------------------------
    # TMS Report Generation & Database Provider Settings
    # -------------------------------------------------------------------------
    DATA_SOURCE_PROVIDER: str = os.getenv("CARDLYZE_DATA_PROVIDER", "file").strip().lower()

    # AWS RDS MS SQL Server Connection parameters (used when DATA_SOURCE_PROVIDER="sql")
    DB_HOST: str = os.getenv("CARDLYZE_DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("CARDLYZE_DB_PORT", "1433"))
    DB_NAME: str = os.getenv("CARDLYZE_DB_NAME", "tms_atm_db")
    DB_USER: str = os.getenv("CARDLYZE_DB_USER", "")
    DB_PASSWORD: str = os.getenv("CARDLYZE_DB_PASSWORD", "")
    DB_DRIVER: str = os.getenv("CARDLYZE_DB_DRIVER", "ODBC Driver 17 for SQL Server")

    # Timezone & Scheduling
    REPORT_TIMEZONE: str = os.getenv("CARDLYZE_REPORT_TIMEZONE", "Asia/Kolkata")
    DAILY_RUN_DELAY_MINUTES: int = int(os.getenv("CARDLYZE_DAILY_RUN_DELAY_MINUTES", "15"))
    # Optional simulation date override for testing historical data without altering system clock
    SIMULATE_DATE: str = os.getenv("CARDLYZE_SIMULATE_DATE", "").strip()

    # Alert Thresholds
    FREQUENCY_THRESHOLD: int = int(os.getenv("CARDLYZE_FREQUENCY_THRESHOLD", "3"))
    USD_THRESHOLD: float = float(os.getenv("CARDLYZE_USD_THRESHOLD", "1500.0"))
    CUMULATIVE_ALERT_THRESHOLD: int = int(os.getenv("CARDLYZE_CUMULATIVE_ALERT_THRESHOLD", "3"))

    # Storage Paths
    INPUT_FILES_DIR: str = os.getenv("CARDLYZE_INPUT_FILES_DIR", "report_generation/input_files")
    DAY_OUTPUT_DIR: str = os.getenv("CARDLYZE_DAY_OUTPUT_DIR", "report_generation/day_output_files")
    CUMULATIVE_OUTPUT_DIR: str = os.getenv(
        "CARDLYZE_CUMULATIVE_OUTPUT_DIR", "report_generation/cumulative_output_files"
    )
    ALERT_LEDGER_PATH: str = os.getenv(
        "CARDLYZE_ALERT_LEDGER_PATH", "report_generation/alert_ledger.json"
    )

    # Scheduler flags
    AUTO_SCHEDULER_ENABLED: bool = os.getenv("CARDLYZE_AUTO_SCHEDULER_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    STARTUP_CATCHUP_ENABLED: bool = os.getenv("CARDLYZE_STARTUP_CATCHUP_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    # -------------------------------------------------------------------------
    # Cloud Storage & AWS S3 / LocalStack Settings
    # -------------------------------------------------------------------------
    STORAGE_BACKEND: str = os.getenv("CARDLYZE_STORAGE_BACKEND", "local").strip().lower()
    S3_BUCKET_NAME: str = os.getenv("CARDLYZE_S3_BUCKET", "cardlyze-reports")
    # For LocalStack use: http://localhost:4566 (or http://localstack:4566 in Docker)
    S3_ENDPOINT_URL: Optional[str] = os.getenv("CARDLYZE_S3_ENDPOINT_URL") or None
    S3_REGION_NAME: str = os.getenv("CARDLYZE_S3_REGION", "ap-south-1")
    S3_ACCESS_KEY_ID: Optional[str] = os.getenv("CARDLYZE_S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY: Optional[str] = os.getenv("CARDLYZE_S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
    # If False, skips uploading clean (0 alerts) spreadsheets to S3 to save bandwidth/API costs
    S3_SAVE_CLEAN_REPORTS: bool = os.getenv("CARDLYZE_S3_SAVE_CLEAN_REPORTS", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )


settings = Settings()
