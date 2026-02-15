FROM python:3.14-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/uv

COPY satellite-kit /satellite-kit
COPY satellite/pyproject.toml satellite/uv.lock /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

COPY satellite/agent /app/agent

CMD ["uv", "run", "python", "-m", "agent"]
