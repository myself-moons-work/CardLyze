"""AWS S3 & LocalStack Cloud Storage Adapter for CardLyze TMS-ATM.

Provides seamless upload and synchronization of:
1. Daily batch reports (.xlsx)
2. Cumulative full-history dossiers (.xlsx)
3. Alert Ledger metadata (alert_ledger.json)

Supports both AWS S3 (production) and LocalStack (local $0 simulation via endpoint_url).
"""

import logging
import os
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class S3StorageManager:
    """Manages cloud report archival and ledger synchronization with AWS S3 or LocalStack."""

    def __init__(
        self,
        storage_backend: Optional[str] = None,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        save_clean_reports: Optional[bool] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        self.storage_backend = (storage_backend or settings.STORAGE_BACKEND).strip().lower()
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.endpoint_url = endpoint_url if endpoint_url is not None else settings.S3_ENDPOINT_URL
        self.region_name = region_name or settings.S3_REGION_NAME
        self.save_clean_reports = (
            save_clean_reports if save_clean_reports is not None else settings.S3_SAVE_CLEAN_REPORTS
        )
        self.access_key_id = access_key_id or settings.S3_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.S3_SECRET_ACCESS_KEY
        self._client = None

    @property
    def is_enabled(self) -> bool:
        """Check if S3 storage backend is activated via configuration."""
        return self.storage_backend == "s3"

    def _get_client(self):
        """Lazy-initialize boto3 S3 client."""
        if self._client is None:
            try:
                import boto3
                from botocore.client import Config

                kwargs = {
                    "region_name": self.region_name,
                    "config": Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}),
                }
                # LocalStack endpoint override (e.g. http://localhost:4566)
                if self.endpoint_url:
                    kwargs["endpoint_url"] = self.endpoint_url
                if self.access_key_id and self.secret_access_key:
                    kwargs["aws_access_key_id"] = self.access_key_id
                    kwargs["aws_secret_access_key"] = self.secret_access_key

                self._client = boto3.client("s3", **kwargs)
                logger.info(
                    "Initialized S3 storage client (region: %s, endpoint: %s)",
                    self.region_name,
                    self.endpoint_url or "AWS Default",
                )
            except Exception as e:
                logger.error("Failed to initialize boto3 S3 client: %s", e)
                raise
        return self._client

    def ensure_bucket_exists(self) -> bool:
        """Verify target S3 bucket exists, or create it if using LocalStack/development."""
        if not self.is_enabled:
            return False

        client = self._get_client()
        bucket = self.bucket_name

        try:
            client.head_bucket(Bucket=bucket)
            return True
        except Exception:
            try:
                logger.info("Bucket '%s' not found. Creating...", bucket)
                if self.region_name and self.region_name != "us-east-1":
                    client.create_bucket(
                        Bucket=bucket,
                        CreateBucketConfiguration={"LocationConstraint": self.region_name},
                    )
                else:
                    client.create_bucket(Bucket=bucket)
                logger.info("Successfully created S3 bucket: %s", bucket)
                return True
            except Exception as e:
                logger.error("Failed to ensure S3 bucket '%s': %s", bucket, e)
                return False

    def upload_file(self, local_path: str, s3_key: str, content_type: Optional[str] = None) -> Optional[str]:
        """Upload a file to S3 and return the s3:// URI."""
        if not self.is_enabled:
            return None

        if not os.path.exists(local_path):
            logger.warning("Cannot upload to S3: local file does not exist: %s", local_path)
            return None

        self.ensure_bucket_exists()
        client = self._get_client()
        bucket = self.bucket_name

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        elif local_path.endswith(".xlsx"):
            extra_args["ContentType"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif local_path.endswith(".json"):
            extra_args["ContentType"] = "application/json"

        try:
            client.upload_file(local_path, bucket, s3_key, ExtraArgs=extra_args if extra_args else None)
            s3_uri = f"s3://{bucket}/{s3_key}"
            logger.info("Uploaded to S3: %s -> %s", local_path, s3_uri)
            return s3_uri
        except Exception as e:
            logger.error("Failed to upload %s to s3://%s/%s: %s", local_path, bucket, s3_key, e)
            return None

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download an S3 object to a local destination."""
        if not self.is_enabled:
            return False

        client = self._get_client()
        bucket = self.bucket_name

        try:
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            client.download_file(bucket, s3_key, local_path)
            logger.info("Downloaded from S3: s3://%s/%s -> %s", bucket, s3_key, local_path)
            return True
        except Exception as e:
            logger.warning("Could not download s3://%s/%s: %s", bucket, s3_key, e)
            return False

    def upload_daily_report(self, local_path: str, card: str, date_str: str, is_clean: bool = False) -> Optional[str]:
        """Upload a daily report to S3. Skips clean reports if save_clean_reports is disabled."""
        if not self.is_enabled:
            return None

        if is_clean and not self.save_clean_reports:
            logger.info("Skipping S3 upload for clean daily report (0 alerts): %s", local_path)
            return None

        filename = os.path.basename(local_path)
        s3_key = f"daily_reports/{card.lower()}/{date_str}/{filename}"
        return self.upload_file(local_path, s3_key)

    def upload_cumulative_report(self, local_path: str, card: str, account_number: str) -> Optional[str]:
        """Upload a cumulative watchlist dossier to S3."""
        if not self.is_enabled:
            return None

        filename = os.path.basename(local_path)
        s3_key = f"cumulative_reports/{card.lower()}/{account_number}/{filename}"
        return self.upload_file(local_path, s3_key)

    def sync_ledger_to_s3(self, local_ledger_path: str) -> bool:
        """Backup the alert ledger to S3."""
        if not self.is_enabled:
            return False

        s3_key = "metadata/alert_ledger.json"
        uri = self.upload_file(local_ledger_path, s3_key, content_type="application/json")
        return uri is not None

    def sync_ledger_from_s3(self, local_ledger_path: str) -> bool:
        """Restore the alert ledger from S3 if missing locally."""
        if not self.is_enabled:
            return False

        if os.path.exists(local_ledger_path):
            return True

        s3_key = "metadata/alert_ledger.json"
        return self.download_file(s3_key, local_ledger_path)


s3_storage = S3StorageManager()
