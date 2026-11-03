"""Concurrency control for file parsing, exports, and CPU-bound operations."""

import asyncio
from typing import Any, Callable
from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.config import settings

# Global parse semaphore limiting simultaneous CPU/memory-heavy file parses (default 1)
parse_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_PARSES)

# Global export semaphore limiting simultaneous memory-heavy workbook exports (default 1)
export_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_EXPORTS)


async def run_parse_task(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute a parsing or typing function in a background worker thread.
    
    Guarantees:
    1. Parsing/typing never blocks the FastAPI asyncio event loop (freeing health checks).
    2. Simultaneous parses are limited by parse_semaphore (default 1).
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


async def run_export_task(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute an export generation function in a background worker thread.
    
    Guarantees:
    1. Export generation never blocks the FastAPI asyncio event loop.
    2. Simultaneous exports are limited by export_semaphore (default 1).
    3. If saturated beyond timeout, raises HTTP 503 Service Unavailable with a clear message.
    """
    acquired = False
    try:
        if settings.EXPORT_SEMAPHORE_TIMEOUT_SECONDS > 0:
            try:
                await asyncio.wait_for(
                    export_semaphore.acquire(),
                    timeout=settings.EXPORT_SEMAPHORE_TIMEOUT_SECONDS,
                )
                acquired = True
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Server busy: maximum simultaneous export capacity reached. Please try again shortly.",
                )
        else:
            try:
                await asyncio.wait_for(export_semaphore.acquire(), timeout=0.001)
                acquired = True
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Server busy: maximum simultaneous export capacity reached. Please try again shortly.",
                )

        return await run_in_threadpool(func, *args, **kwargs)
    finally:
        if acquired:
            export_semaphore.release()
