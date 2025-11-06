FROM python:3.13-slim-bookworm

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.4.18 /uv /bin/uv

COPY pyproject.toml /app/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-dev --no-install-project

COPY agent /app/agent

CMD ["uv", "run", "python", "-m", "agent"]
