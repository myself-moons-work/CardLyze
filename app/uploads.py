"""Streaming upload handler enforcing raw-body parsing and in-memory byte limits."""

import io
from fastapi import HTTPException, Request, status
from app.config import settings


async def read_limited_body(
    request: Request,
    max_bytes: int = settings.MAX_UPLOAD_SIZE_BYTES,
) -> bytes:
    """Stream request body chunks into memory, aborting with HTTP 413 if max_bytes is exceeded.
    
    Avoids Starlette multipart form disk spooling by reading the raw stream directly.
    """
    # Fast check via Content-Length header if present
    content_length_header = request.headers.get("content-length")
    if content_length_header is not None:
        try:
            content_length = int(content_length_header)
            if content_length > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Payload exceeds limit of {max_bytes} bytes.",
                )
        except ValueError:
            pass

    buffer = io.BytesIO()
    total_bytes = 0

    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            buffer.close()
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Payload exceeds limit of {max_bytes} bytes.",
            )
        buffer.write(chunk)

    return buffer.getvalue()
