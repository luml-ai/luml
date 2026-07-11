from fastapi import APIRouter
from pydantic import BaseModel

from luml_prisma.version import __version__

router = APIRouter(prefix="/api/health", tags=["health"])


class HealthResponse(BaseModel):
    service: str
    version: str


@router.get("/", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(service="luml-prisma", version=__version__)
