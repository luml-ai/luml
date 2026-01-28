from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@api_router.get("/hello")
async def hello() -> JSONResponse:
    return JSONResponse({"message": "Hello from Lumlflow!"})


def get_static_dir() -> Path:
    return Path(__file__).parent / "static"


app = FastAPI(
    title="Lumlflow",
    description="Local ML experiment tracking",
    version="0.1.0",
)

app.include_router(api_router)


static_dir = get_static_dir()
if static_dir.exists() and (static_dir / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str) -> FileResponse:
        file_path = static_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")
