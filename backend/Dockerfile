FROM python:3.14-slim-bookworm

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/uv
COPY luml /app/luml
COPY pyproject.toml /app/pyproject.toml
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini
COPY uv.lock /app/uv.lock

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
CMD ["uv", "run", "ddtrace-run", "uvicorn", "luml.server:app", "--host", "0.0.0.0", "--port", "8000"]
