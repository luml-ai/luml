FROM python:3.14-slim-bookworm

WORKDIR /app/satellite

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv

COPY kit /app/satellite/kit
COPY implementations/docker /app/satellite/implementations/docker

WORKDIR /app/satellite/implementations/docker

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

CMD ["uv", "run", "--no-sync", "luml-satellite-docker"]
