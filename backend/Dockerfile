FROM python:3.14-slim-bookworm@sha256:516b51cb9db2ef061e465c803e50f64361b82cefd91e525b889b967b83e83527 AS base

FROM base AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/uv
COPY pyproject.toml uv.lock /app/

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

FROM base AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    UV_NO_SYNC=1 \
    UV_CACHE_DIR=/tmp/uv \
    HOME=/app

COPY --from=builder /bin/uv /bin/uv
COPY --from=builder /app/.venv /app/.venv
COPY luml /app/luml
COPY pyproject.toml uv.lock /app/
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini

USER 10001:0

CMD ["uvicorn", "luml.server:app", "--host", "0.0.0.0", "--port", "8000"]
