"""CardLyze FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.security import SecurityHeadersMiddleware
from app.services.concurrency import run_parse_task
from app.store import session_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Background task lifecycle manager for session cleanup."""
    stop_event = asyncio.Event()

    async def sweeper_loop():
        while not stop_event.is_set():
            try:
                session_store.sweep_expired()
            except Exception:
                pass
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.SWEEPER_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                pass

    sweeper_task = asyncio.create_task(sweeper_loop())
    yield
    stop_event.set()
    try:
        await sweeper_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="CardLyze",
    description="Card Transaction Processing and Analysis Platform",
    lifespan=lifespan,
)

# Enforce security and privacy headers across all responses
app.add_middleware(SecurityHeadersMiddleware)


# --- Core API Endpoints ---

@app.get("/api/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "ok"}


@app.post("/api/session", status_code=status.HTTP_201_CREATED)
async def create_session():
    """Initialize a new in-memory session. Raises HTTP 503 if session capacity is reached."""
    session_id = session_store.create_session()
    return {"session_id": session_id}


@app.delete("/api/session")
async def delete_session(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Explicitly wipe all stored in-memory datasets and delete the session."""
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Session-Id header",
        )
    deleted = session_store.delete_session(x_session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already expired",
        )
    return {"status": "deleted"}


@app.post("/api/concurrency/test-parse")
async def concurrency_test_parse(duration: float = 0.5):
    """Internal/test endpoint running a parse task in threadpool guarded by concurrency semaphore."""
    import time

    def _slow_parse():
        time.sleep(duration)
        return {"status": "parsed"}

    return await run_parse_task(_slow_parse)


# Mount static frontend assets
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

