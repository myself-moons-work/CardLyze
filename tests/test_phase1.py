"""Tests for Phase 1: Security headers, in-memory SessionStore, raw uploads, and zero-disk guarantee."""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.store import SessionData, SessionStore, session_store
from app.uploads import read_limited_body


@pytest.fixture(autouse=True)
def clean_sessions():
    """Ensure session store is cleared before and after each test."""
    session_store.clear_all()
    yield
    session_store.clear_all()


def test_security_headers_on_api_response():
    """Verify all security headers are present on API endpoints."""
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers.get("cache-control") == "no-store"
        assert response.headers.get("referrer-policy") == "no-referrer"
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("content-security-policy") == "default-src 'self'"


def test_security_headers_on_static_response():
    """Verify security headers are attached when serving static files."""
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "CardLyze" in response.text
        assert response.headers.get("cache-control") == "no-store"
        assert response.headers.get("referrer-policy") == "no-referrer"
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("content-security-policy") == "default-src 'self'"

        # Check static CSS
        css_response = client.get("/css/app.css")
        assert css_response.status_code == 200
        assert css_response.headers.get("cache-control") == "no-store"
        assert css_response.headers.get("x-content-type-options") == "nosniff"


def test_session_creation():
    """Verify creating a session returns a valid 32+ char token and registers in-memory."""
    with TestClient(app) as client:
        response = client.post("/api/session")
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        session_id = data["session_id"]
        assert len(session_id) >= 32

        # Verify present in server-side session store
        session = session_store.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
        assert isinstance(session.coladd, dict)
        assert isinstance(session.analysis, dict)


def test_session_cap_returns_503():
    """Verify that creating sessions beyond MAX_CONCURRENT_SESSIONS returns 503."""
    with TestClient(app) as client:
        created_tokens = []
        # Create up to max capacity
        for _ in range(settings.MAX_CONCURRENT_SESSIONS):
            res = client.post("/api/session")
            assert res.status_code == 201
            created_tokens.append(res.json()["session_id"])

        assert session_store.active_session_count() == settings.MAX_CONCURRENT_SESSIONS

        # 11th attempt must fail with 503
        overflow_res = client.post("/api/session")
        assert overflow_res.status_code == 503
        assert "Maximum concurrent sessions" in overflow_res.json()["detail"]


def test_session_ttl_expiry_with_injectable_clock():
    """Verify session expiration using a deterministic fake clock."""
    fake_time = 1000.0

    def mock_clock():
        return fake_time

    store = SessionStore(ttl_seconds=1800, max_sessions=10, time_func=mock_clock)
    session_id = store.create_session()
    assert store.active_session_count() == 1

    # Advance time within TTL (29 minutes later)
    fake_time += 1740.0
    session = store.get_session(session_id, touch=False)
    assert session is not None

    # Advance time past TTL (31 minutes later total)
    fake_time += 120.0
    expired_session = store.get_session(session_id)
    assert expired_session is None
    assert store.active_session_count() == 0


def test_session_delete_wipes_data():
    """Verify DELETE /api/session drops all data references and invalidates token."""
    with TestClient(app) as client:
        create_res = client.post("/api/session")
        session_id = create_res.json()["session_id"]

        session = session_store.get_session(session_id)
        assert session is not None
        # Simulate stored datasets in session
        session.coladd["dataset"] = {"rows": 100}
        session.analysis["df"] = "dummy_dataframe_reference"

        # Explicit delete call
        del_res = client.delete("/api/session", headers={"X-Session-Id": session_id})
        assert del_res.status_code == 200
        assert del_res.json() == {"status": "deleted"}

        # Verification: session is gone and data was wiped
        assert session_store.get_session(session_id) is None
        assert len(session.coladd) == 0
        assert len(session.analysis) == 0

        # Subsequent delete returns 404
        second_del = client.delete("/api/session", headers={"X-Session-Id": session_id})
        assert second_del.status_code == 404

        # Delete without header returns 400
        bad_del = client.delete("/api/session")
        assert bad_del.status_code == 400


def test_read_limited_body_success():
    """Verify reading a streaming body within limits."""
    payload = b"Hello, CardLyze in-memory streaming!"

    async def _run():
        async def mock_stream():
            yield payload[:10]
            yield payload[10:]

        mock_request = MagicMock(spec=Request)
        mock_request.stream = mock_stream
        mock_request.headers = {"content-length": str(len(payload))}

        return await read_limited_body(mock_request, max_bytes=1024)

    result = asyncio.run(_run())
    assert result == payload


def test_read_limited_body_oversize_abort_413():
    """Verify that exceeding max_bytes raises HTTP 413 and aborts reading."""
    chunk = b"X" * 1024

    async def _run():
        async def mock_stream():
            yield chunk
            yield chunk
            yield chunk

        mock_request = MagicMock(spec=Request)
        mock_request.stream = mock_stream
        mock_request.headers = {}

        await read_limited_body(mock_request, max_bytes=2000)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_run())

    assert exc_info.value.status_code == 413
    assert "Payload exceeds limit" in exc_info.value.detail


def test_read_limited_body_content_length_header_413():
    """Verify fast rejection when Content-Length header indicates oversized body."""
    async def _run():
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"content-length": str(100 * 1024 * 1024)}  # 100 MB
        await read_limited_body(mock_request, max_bytes=50 * 1024 * 1024)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_run())

    assert exc_info.value.status_code == 413


def test_no_disk_during_5mb_upload(monkeypatch):
    """Zero-Disk Invariant Test:
    
    1. Monkeypatch tempfile spooled and named temp file creation to raise.
    2. Snapshot system temp dir and project directory before upload.
    3. Stream a 5 MB payload through read_limited_body.
    4. Assert no files were created anywhere on disk.
    """
    def forbidden_tempfile(*args, **kwargs):
        raise RuntimeError("PRIVACY VIOLATION: Spooling or writing temporary files to disk is strictly forbidden!")

    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", forbidden_tempfile)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", forbidden_tempfile)
    monkeypatch.setattr(tempfile, "TemporaryFile", forbidden_tempfile)

    temp_dir = tempfile.gettempdir()
    project_dir = Path(__file__).resolve().parent.parent

    # Snapshot directories
    temp_before = set(os.listdir(temp_dir))
    proj_before = set(os.listdir(project_dir))

    # Generate 5 MB payload in memory
    payload_size = 5 * 1024 * 1024
    chunk_size = 64 * 1024
    num_chunks = payload_size // chunk_size
    chunk = b"A" * chunk_size

    async def _run():
        async def stream_generator():
            for _ in range(num_chunks):
                yield chunk

        mock_request = MagicMock(spec=Request)
        mock_request.stream = stream_generator
        mock_request.headers = {"content-length": str(payload_size)}

        return await read_limited_body(mock_request, max_bytes=10 * 1024 * 1024)

    # Stream 5 MB into memory
    received_bytes = asyncio.run(_run())
    assert len(received_bytes) == payload_size

    # Verify no disk activity
    temp_after = set(os.listdir(temp_dir))
    proj_after = set(os.listdir(project_dir))

    new_temp_files = [f for f in (temp_after - temp_before) if not f.startswith("~")]
    new_proj_files = proj_after - proj_before

    assert len(new_temp_files) == 0, f"Unexpected temp files created on disk: {new_temp_files}"
    assert len(new_proj_files) == 0, f"Unexpected files created in project dir: {new_proj_files}"
