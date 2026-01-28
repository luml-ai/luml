## Usage

```bash
lumlflow ui                    # Start UI at localhost:5000
lumlflow ui --port 8080        # Custom port
lumlflow ui --no-browser       # Don't open browser
```

## Development

### Backend

```bash
uv sync --group dev
uv run python -m uvicorn lumlflow.server:app --reload --port 5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
