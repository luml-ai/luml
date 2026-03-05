import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse

from lumlflow.handlers.luml.artifacts import ArtifactHandler
from lumlflow.handlers.luml.luml import LumlHandler
from lumlflow.infra.progress_store import progress_store
from lumlflow.schemas.luml import (
    JobResponse,
    Orbit,
    Organization,
    PaginatedCollections,
    UploadArtifactForm,
)

luml_router = APIRouter(prefix="/api/luml", tags=["luml"])

luml_handler = LumlHandler()
artifact_handler = ArtifactHandler()


@luml_router.get("/organizations", response_model=list[Organization])
def get_luml_organizations() -> list[Organization]:
    return luml_handler.get_luml_organizations()


@luml_router.get("/orbits", response_model=list[Orbit])
def get_luml_orbits(organization_id: str) -> list[Orbit]:
    return luml_handler.get_luml_orbits(organization_id)


@luml_router.get("/collections", response_model=PaginatedCollections)
def get_luml_collections(
    organization_id: str,
    orbit_id: str,
    start_after: str | None = None,
    limit: int = 50,
    search: str | None = None,
) -> PaginatedCollections:
    return luml_handler.get_luml_collections(
        organization_id=organization_id,
        orbit_id=orbit_id,
        start_after=start_after,
        limit=limit,
        search=search,
    )


@luml_router.post("/artifact", status_code=202, response_model=JobResponse)
def upload_artifact(
    artifact: UploadArtifactForm, background_tasks: BackgroundTasks
) -> JobResponse:
    job_id = str(uuid4())
    progress_store.create(job_id)
    background_tasks.add_task(artifact_handler.upload_artifact, artifact, job_id)
    return JobResponse(job_id=job_id)


@luml_router.get("/artifact/{job_id}/progress", response_class=StreamingResponse)
def upload_progress(job_id: str) -> StreamingResponse:
    def event_stream():
        last_sent = None
        while True:
            job = progress_store.get(job_id)
            if job is None:
                yield 'data: {"type":"not_found"}\n\n'
                break
            current = job.to_json()
            if current != last_sent:
                yield f"data: {current}\n\n"
                last_sent = current
            if job.status in ("complete", "error"):
                progress_store.delete(job_id)
                break
            time.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
