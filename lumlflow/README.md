## Usage

```bash
lumlflow ui                                        # Start UI at localhost:5000 (default: sqlite://./experiments)
lumlflow ui --path sqlite://./my_experiments       # Custom experiments path
lumlflow ui --port 8080                            # Custom port
lumlflow ui --no-browser                           # Don't open browser
```

## Development

### Backend

```bash
uv sync

uv pip install -e "your path to /dataforce.studio/sdk/python"

source .venv/bin/activate 

uvicorn lumlflow.server:app --reload --port 5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
