from fastapi import APIRouter
from fastapi.responses import JSONResponse

general_router = APIRouter(prefix="/api")


@general_router.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@general_router.get("/hello")
async def hello() -> JSONResponse:
    return JSONResponse({"message": "Hello from Lumlflow!"})
