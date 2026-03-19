from pathlib import Path

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from lumlflow.service import AppService


def get_static_dir() -> Path:
    return Path(__file__).parent / "static"


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException:
            return await super().get_response("index.html", scope)


app = AppService()


static_dir = get_static_dir()
if static_dir.exists() and (static_dir / "index.html").exists():
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="spa")
