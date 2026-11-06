FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/jobs/sync:/app/services/mcp_server
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
COPY services/mcp_server/requirements.txt services/mcp_server/requirements.txt

FROM base AS test
RUN pip install -r requirements-dev.txt
