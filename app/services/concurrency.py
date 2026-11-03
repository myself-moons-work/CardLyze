"""Concurrency control for file parsing and CPU-bound operations."""

import asyncio
from typing import Any, Callable
from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.config import settings

# Global parse semaphore limiting simultaneous CPU/memory-heavy file parses (default 2)
parse_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_PARSES)


async def run_parse_task(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute a parsing or typing function in a background worker thread.
    
    Guarantees:
    1. Parsing/typing never blocks the FastAPI asyncio event loop (freeing health checks).
    2. Simultaneous parses are limited by parse_semaphore (default 2).
    3. If saturated beyond timeout, raises HTTP 503 Service Unavailable with a clear message.
    """
    acquired = False
    try:
        if settings.PARSE_SEMAPHORE_TIMEOUT_SECONDS > 0:
            try:
                await asyncio.wait_for(
                    parse_semaphore.acquire(),
                    timeout=settings.PARSE_SEMAPHORE_TIMEOUT_SECONDS,
                )
                acquired = True
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Server busy: maximum simultaneous file processing capacity reached. Please try again shortly.",
                )
        else:
            # Immediate acquisition check
            try:
                await asyncio.wait_for(parse_semaphore.acquire(), timeout=0.001)
                acquired = True
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Server busy: maximum simultaneous file processing capacity reached. Please try again shortly.",
                )

        return await run_in_threadpool(func, *args, **kwargs)
    finally:
        if acquired:
            parse_semaphore.release()
