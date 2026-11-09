"""Unit tests for AWS S3 and LocalStack Storage Adapter using botocore Stubber."""

import os
import tempfile
import pytest
from botocore.stub import Stubber

from app.services.s3_storage import S3StorageManager


def test_s3_storage_disabled_by_default():
    """Verify S3StorageManager is inactive when STORAGE_BACKEND is 'local'."""
    mgr = S3StorageManager(storage_backend="local")
    assert mgr.is_enabled is False
    # In disabled mode, upload returns None without attempting any network call
    res = mgr.upload_daily_report("nonexistent.xlsx", "visa", "2026-11-08")
    assert res is None


def test_s3_storage_upload_daily_report_mocked():
    """Test daily report upload to S3 using botocore Stubber."""
    mgr = S3StorageManager(
        storage_backend="s3",
        bucket_name="test-tms-bucket",
        region_name="ap-south-1",
        save_clean_reports=True,
    )
    assert mgr.is_enabled is True
    client = mgr._get_client()

    with Stubber(client) as stubber:
        # Mock head_bucket check
        stubber.add_response("head_bucket", {})
        # Mock put_object / upload_file
        stubber.add_response("put_object", {})

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(b"MOCK_EXCEL_BYTES")
            tmp_path = tmp.name

        target_path = os.path.join(os.path.dirname(tmp_path), "daily_report_visa_2026-11-08.xlsx")
        try:
            os.replace(tmp_path, target_path)
            uri = mgr.upload_daily_report(target_path, "visa", "2026-11-08", is_clean=False)
            assert uri == "s3://test-tms-bucket/daily_reports/visa/2026-11-08/daily_report_visa_2026-11-08.xlsx"
        finally:
            if os.path.exists(target_path):
                os.remove(target_path)


def test_s3_storage_skip_clean_reports():
    """Verify that when save_clean_reports=False, clean reports with 0 alerts are not uploaded."""
    mgr = S3StorageManager(
        storage_backend="s3",
        save_clean_reports=False,
    )
    # Should skip immediately without initializing or calling S3
    uri = mgr.upload_daily_report("some_clean_report.xlsx", "visa", "2026-11-08", is_clean=True)
    assert uri is None


def test_s3_storage_ledger_sync():
    """Test alert ledger upload synchronization with S3."""
    mgr = S3StorageManager(
        storage_backend="s3",
        bucket_name="test-tms-bucket",
        region_name="ap-south-1",
    )
    client = mgr._get_client()

    with Stubber(client) as stubber:
        stubber.add_response("head_bucket", {})
        stubber.add_response("put_object", {})

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(b'{"ledger": "test"}')
            tmp_path = tmp.name

        try:
            success = mgr.sync_ledger_to_s3(tmp_path)
            assert success is True
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


def test_s3_storage_cumulative_report_upload():
    """Test cumulative full-history dossier upload to S3."""
    mgr = S3StorageManager(
        storage_backend="s3",
        bucket_name="test-tms-bucket",
        region_name="ap-south-1",
    )
    client = mgr._get_client()

    with Stubber(client) as stubber:
        stubber.add_response("head_bucket", {})
        stubber.add_response("put_object", {})

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(b"DOSSIER_BYTES")
            tmp_path = tmp.name

        target_path = os.path.join(os.path.dirname(tmp_path), "cumulative_visa_P0000000001449799.xlsx")
        try:
            os.replace(tmp_path, target_path)
            uri = mgr.upload_cumulative_report(target_path, "visa", "P0000000001449799")
            assert uri == "s3://test-tms-bucket/cumulative_reports/visa/P0000000001449799/cumulative_visa_P0000000001449799.xlsx"
        finally:
            if os.path.exists(target_path):
                os.remove(target_path)
