FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/jobs/sync:/app/services/mcp_server:/app/services/chat_bot:/app/jobs/eval
# The base digest is the newest python:3.12-slim but ships zlib1g 1+b1 (CVE-2026-76844,
# CVE-2026-85091); the exact fixed version comes from trixie-security until upstream rebuilds.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-dev.lock ./

# The tested dependency set: every distribution pinned and hash-checked (WR-04). Regenerate the
# locks with scripts/lock-requirements.sh.
FROM base AS test
RUN pip install --require-hashes -r requirements-dev.lock

# Runtime image for the MCP server: only buddy_core and buddy_mcp code, non-root. The index is
# not baked in; ARTIFACT_DIR points at a mounted directory (handoff decided in Phase 4).
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS mcp_server
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/services/mcp_server
# The base digest is the newest python:3.12-slim but ships zlib1g 1+b1 (CVE-2026-76844,
# CVE-2026-85091); the exact fixed version comes from trixie-security until upstream rebuilds.
RUN apt-get update \
    && apt-get install -y --no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/mcp_server/requirements.lock services/mcp_server/requirements.lock
RUN pip install --require-hashes -r services/mcp_server/requirements.lock
COPY packages/buddy_core packages/buddy_core
COPY services/mcp_server services/mcp_server
USER 10001
EXPOSE 8000
CMD ["python", "-m", "buddy_mcp"]

# Runtime image for the chat bot: buddy_core, buddy_bot and only the MCP output models
# (buddy_mcp/__init__.py and models.py); no server code. Non-root. Tracing export stays off:
# prompts carry employee questions and may only reach the LLM backend and the MCP server.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS chat_bot
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/services/mcp_server:/app/services/chat_bot \
    LANGSMITH_TRACING=false
# The base digest is the newest python:3.12-slim but ships zlib1g 1+b1 (CVE-2026-76844,
# CVE-2026-85091); the exact fixed version comes from trixie-security until upstream rebuilds.
RUN apt-get update \
    && apt-get install -y --no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/chat_bot/requirements.lock services/chat_bot/requirements.lock
RUN pip install --require-hashes -r services/chat_bot/requirements.lock
COPY packages/buddy_core packages/buddy_core
COPY services/mcp_server/buddy_mcp/__init__.py services/mcp_server/buddy_mcp/__init__.py
COPY services/mcp_server/buddy_mcp/models.py services/mcp_server/buddy_mcp/models.py
COPY services/chat_bot/buddy_bot services/chat_bot/buddy_bot
USER 10001
EXPOSE 8080
CMD ["python", "-m", "buddy_bot"]

# Laptop sync image (D-06, D-09): builds index.db from the handbook folder and the Guides
# repository, both mounted read-only at run time. Nothing private is baked in. git is needed to
# clone the Guides mount; the mount belongs to the host user, so the clone would trip git's
# ownership check as uid 10001, so /guides-src and its .git (git names the .git path) are marked
# safe: the documented mount path only.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS sync
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/jobs/sync
# The base digest is the newest python:3.12-slim but ships zlib1g 1+b1 (CVE-2026-76844,
# CVE-2026-85091); the exact fixed version comes from trixie-security until upstream rebuilds.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory /guides-src && git config --system --add safe.directory /guides-src/.git
WORKDIR /app
COPY jobs/sync/requirements.lock jobs/sync/requirements.lock
RUN pip install --require-hashes -r jobs/sync/requirements.lock
COPY packages/buddy_core packages/buddy_core
COPY jobs/sync jobs/sync
RUN mkdir -p /artifacts /app/.cache && chown 10001:10001 /artifacts /app/.cache
USER 10001
ENTRYPOINT ["python", "-m", "buddy_sync"]
CMD ["run"]

# Eval job image (D-12, D-14): runs the bot workflow in-process against the compose MCP server and
# traces to the local MLflow server. Never deployed; nothing private is baked in. Tracing and
# telemetry exporters stay off, MLflow evaluates serially (RESEARCH pitfalls 1-2), and git is not
# installed. /eval-empty is the mount point of the empty-context fixture volume, owned by the
# runtime user so a fresh named volume inherits that owner.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS eval
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/packages/buddy_core:/app/services/mcp_server:/app/services/chat_bot:/app/jobs/eval \
    LANGSMITH_TRACING=false \
    MLFLOW_DISABLE_TELEMETRY=true \
    MLFLOW_ENABLE_ASYNC_TRACE_LOGGING=false \
    MLFLOW_GENAI_EVAL_MAX_WORKERS=1 \
    MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS=1 \
    GIT_PYTHON_REFRESH=quiet
# The base digest is the newest python:3.12-slim but ships zlib1g 1+b1 (CVE-2026-76844,
# CVE-2026-85091); the exact fixed version comes from trixie-security until upstream rebuilds.
RUN apt-get update \
    && apt-get install -y --no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY jobs/eval/requirements.lock jobs/eval/requirements.lock
RUN pip install --require-hashes -r jobs/eval/requirements.lock
COPY packages/buddy_core packages/buddy_core
COPY services/mcp_server/buddy_mcp/__init__.py services/mcp_server/buddy_mcp/__init__.py
COPY services/mcp_server/buddy_mcp/models.py services/mcp_server/buddy_mcp/models.py
COPY services/chat_bot/buddy_bot services/chat_bot/buddy_bot
COPY jobs/eval jobs/eval
RUN mkdir -p /eval-empty && chown 10001:10001 /eval-empty
USER 10001
ENTRYPOINT ["python", "-m", "buddy_eval"]
CMD ["--help"]
