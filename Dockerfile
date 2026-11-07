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

# Runtime image for the chat bot: buddy_core, buddy_bot and only the MCP output models
# (buddy_mcp/__init__.py and models.py); no server code. Non-root. Tracing export stays off:
# prompts carry employee questions and may only reach the LLM backend and the MCP server.
FROM python:3.12-slim AS chat_bot
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/services/mcp_server:/app/services/chat_bot \
    LANGSMITH_TRACING=false
WORKDIR /app
COPY requirements.txt ./
COPY services/chat_bot/requirements.txt services/chat_bot/requirements.txt
RUN pip install -r requirements.txt -r services/chat_bot/requirements.txt
COPY packages/buddy_core packages/buddy_core
COPY services/mcp_server/buddy_mcp/__init__.py services/mcp_server/buddy_mcp/__init__.py
COPY services/mcp_server/buddy_mcp/models.py services/mcp_server/buddy_mcp/models.py
COPY services/chat_bot/buddy_bot services/chat_bot/buddy_bot
USER 10001
EXPOSE 8080
CMD ["python", "-m", "buddy_bot"]
