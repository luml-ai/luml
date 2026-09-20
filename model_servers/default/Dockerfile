FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y \
    curl \
    bzip2 \
    && rm -rf /var/lib/apt/lists/*

ARG MICROMAMBA_VERSION=2.9.0
# The platform comes from the build container itself, so the binary always matches the
# image being built — with or without BuildKit, and under --platform. micromamba names
# x86_64 "linux-64" and every other machine "linux-<machine>".
RUN MAMBA_PLATFORM="linux-$(uname -m | sed 's/^x86_64$/64/')" \
    && curl -Ls "https://micro.mamba.pm/api/micromamba/${MAMBA_PLATFORM}/${MICROMAMBA_VERSION}" \
    | tar -xvj -C /usr/local bin/micromamba && chmod +x /usr/local/bin/micromamba

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

CMD ["uv", "run", "python", "main.py"]
