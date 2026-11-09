# =============================================================================
# CardLyze - High-Risk Transaction Monitoring & Report Generation Platform
# Multi-stage/lean production container configuration
# =============================================================================
FROM python:3.12-slim

# Prevent Python from writing .pyc files & force immediate stdout/stderr flushing
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CARDLYZE_HOST=0.0.0.0 \
    CARDLYZE_PORT=8000 \
    ALLOW_NON_LOOPBACK=1 \
    CARDLYZE_REPORT_TIMEZONE=Asia/Kolkata \
    CARDLYZE_DAILY_RUN_DELAY_MINUTES=15 \
    CARDLYZE_DATA_PROVIDER=file

WORKDIR /app

# Install minimal system tools (curl for Docker healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (maximizes Docker layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source, configuration, and data assets
COPY app/ /app/app/
COPY data_with_headers/ /app/data_with_headers/
COPY report_generation/ /app/report_generation/
COPY task_1/ /app/task_1/
COPY cards.py /app/cards.py

# Expose application port
EXPOSE 8000

# Container healthcheck: verify dashboard is accessible
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/task1.html || exit 1

# Launch CardLyze with single worker (in-memory zero-disk persistence model)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

