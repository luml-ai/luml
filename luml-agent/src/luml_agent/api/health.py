from fastapi import APIRouter
from pydantic import BaseModel

from luml_agent.version import __version__

router = APIRouter(prefix="/api/health", tags=["health"])


class HealthResponse(BaseModel):
    service: str
    version: str


@router.get("/", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(service="luml-agent", version=__version__)
