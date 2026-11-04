FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

RUN jupyter lite build --output-dir dist

COPY ./server.py ./server.py

WORKDIR /app/dist

EXPOSE 8000

CMD ["uvicorn", "server:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8000"]
