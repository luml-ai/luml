
FROM python:3.12-slim

RUN pip install --no-cache-dir "jupyterlite==0.5.1" "jupyterlite-pyodide-kernel==0.5.2" "fastapi==0.115.12" "uvicorn==0.34.3"

WORKDIR /app

RUN jupyter lite build --output-dir dist

COPY ./server.py ./dist/server.py

WORKDIR /app/dist

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]