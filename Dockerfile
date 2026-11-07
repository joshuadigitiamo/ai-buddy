FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/jobs/sync:/app/services/mcp_server:/app/services/chat_bot
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
COPY services/mcp_server/requirements.txt services/mcp_server/requirements.txt
COPY services/chat_bot/requirements.txt services/chat_bot/requirements.txt

FROM base AS test
RUN pip install -r requirements-dev.txt

# Runtime image for the MCP server: only buddy_core and buddy_mcp code, non-root. The index is
# not baked in; ARTIFACT_DIR points at a mounted directory (handoff decided in Phase 4).
FROM python:3.12-slim AS mcp_server
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/services/mcp_server
WORKDIR /app
COPY requirements.txt ./
COPY services/mcp_server/requirements.txt services/mcp_server/requirements.txt
RUN pip install -r requirements.txt -r services/mcp_server/requirements.txt
COPY packages/buddy_core packages/buddy_core
COPY services/mcp_server services/mcp_server
USER 10001
EXPOSE 8000
CMD ["python", "-m", "buddy_mcp"]
