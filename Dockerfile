# Single-stage Python 3.12+ production image for TCDD Ticket Finder Bot
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install production dependencies only.
# Inspect runtime imports (app/tcdd/client.py: curl_cffi is lazily imported inside
# _try_curl_cffi_fallback only for TLS/WAF fallback; primary path uses httpx).
# Therefore base install with httpx + python-telegram-bot is sufficient for production.
# The optional extra `curl` (curl_cffi) is NOT installed by default to keep image minimal;
# operators needing WAF fallback can rebuild with `pip install \".[curl]\"` or override.
# Test dependencies (pytest, pytest-asyncio) are never installed in the image.
COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Ensure persistent volume mount point exists and is writable
RUN mkdir -p /data

ENV DATABASE_PATH=/data/tcdd-ticket.sqlite3

CMD ["python", "-m", "app.main"]
