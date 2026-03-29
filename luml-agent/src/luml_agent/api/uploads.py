import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from luml_agent.services.upload_queue import UploadQueue, UploadStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["uploads"])


class UploadUrlIn(BaseModel):
    presigned_url: str


def _upload_dict(upload: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "id": upload.id,
        "run_id": upload.run_id,
        "node_id": upload.node_id,
        "model_path": upload.model_path,
        "experiment_ids": upload.experiment_ids,
        "file_size": upload.file_size,
        "status": upload.status,
        "error": upload.error,
        "retry_count": upload.retry_count,
        "created_at": upload.created_at,
        "updated_at": upload.updated_at,
    }


async def _do_upload(
    upload_queue: UploadQueue,
    upload_id: str,
    model_path: str,
    presigned_url: str,
    event_bus: Any,  # noqa: ANN401
    run_id: str,
    node_id: str,
) -> None:
    try:
        async with httpx.AsyncClient() as client:
            with open(model_path, "rb") as f:
                resp = await client.put(presigned_url, content=f.read(), timeout=300)
            resp.raise_for_status()
        upload_queue.complete(upload_id)
        if event_bus is not None:
            event_bus.emit(
                "upload_completed",
                {
                    "upload_id": upload_id,
                    "run_id": run_id,
                    "node_id": node_id,
                },
            )
    except Exception as exc:
        error_msg = str(exc)
        logger.warning("Upload %s failed: %s", upload_id, error_msg)
        upload_queue.fail(upload_id, error_msg)
        upload = upload_queue.get(upload_id)
        status = upload.status if upload else UploadStatus.FAILED
        if event_bus is not None:
            event_bus.emit(
                "upload_failed",
                {
                    "upload_id": upload_id,
                    "run_id": run_id,
                    "node_id": node_id,
                    "error": error_msg,
                    "status": str(status),
                },
            )


@router.post(
    "/{run_id}/uploads/{upload_id}/url",
    status_code=202,
)
async def post_upload_url(
    request: Request,
    run_id: str,
    upload_id: str,
    body: UploadUrlIn,
) -> JSONResponse:
    upload_queue: UploadQueue = request.app.state.upload_queue
    claimed = upload_queue.claim(upload_id)
    if not claimed:
        return JSONResponse(
            status_code=409,
            content={"detail": "Upload already claimed"},
        )

    upload = upload_queue.get(upload_id)
    if upload is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Upload not found"},
        )

    event_bus = getattr(request.app.state, "event_bus", None)
    asyncio.create_task(
        _do_upload(
            upload_queue=upload_queue,
            upload_id=upload_id,
            model_path=upload.model_path,
            presigned_url=body.presigned_url,
            event_bus=event_bus,
            run_id=run_id,
            node_id=upload.node_id,
        ),
    )
    return JSONResponse(status_code=202, content={"status": "accepted"})


@router.get("/{run_id}/uploads")
def list_uploads(
    request: Request,
    run_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    upload_queue: UploadQueue = request.app.state.upload_queue
    if status == "pending":
        uploads = upload_queue.get_pending(run_id)
    else:
        uploads = upload_queue.get_pending(run_id)
    return [_upload_dict(u) for u in uploads]
