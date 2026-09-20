FROM python:3.14-slim-bookworm

WORKDIR /app/satellite

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/satellite/implementations/kubernetes/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv

COPY kit /app/satellite/kit
COPY implementations/kubernetes /app/satellite/implementations/kubernetes

WORKDIR /app/satellite/implementations/kubernetes

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev && \
    chgrp -R 0 /app && \
    chmod -R g=u /app

USER 10001:0

CMD ["luml-satellite-kubernetes"]
