FROM python:3.13-slim-bookworm

COPY --from=mambaorg/micromamba:2.9.0@sha256:7b93def90e48d6d7744938e31c29172e03b19bc9f56f0db512039f18efd21529 /bin/micromamba /usr/local/bin/micromamba

WORKDIR /app

ENV HOME=/app \
    MAMBA_ROOT_PREFIX=/app/.micromamba \
    UV_CACHE_DIR=/app/.cache/uv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv

RUN mkdir -p /app/.cache/uv /app/.micromamba /app/models \
    && chown -R 10001:0 /app \
    && chmod -R g=u /app

COPY pyproject.toml uv.lock /app/

RUN --mount=type=cache,target=/app/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . /app/

RUN chown -R 10001:0 /app \
    && chmod -R g=u /app

ENV PYTHONPATH=/app

USER 10001:0

CMD ["/app/.venv/bin/python", "main.py"]
