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


def _link_experiments(model_path: str, experiment_ids: list[str]) -> None:
    if not experiment_ids:
        return
    try:
        from pathlib import Path

        from luml.artifacts.model import ModelReference
        from luml.experiments.tracker import ExperimentTracker

        db_path = Path.home() / ".luml-agent" / "experiments"
        tracker = ExperimentTracker(f"sqlite://{db_path}")
        model_ref = ModelReference(model_path)
        for exp_id in experiment_ids:
            try:
                att_dir = db_path / exp_id / "attachments"
                att_dir.mkdir(parents=True, exist_ok=True)
                tracker.link_to_model(model_ref, experiment_id=exp_id)
                logger.info("Linked experiment %s to %s", exp_id, model_path)
            except Exception:
                logger.warning(
                    "Failed to link experiment %s to %s",
                    exp_id, model_path, exc_info=True,
                )
    except ImportError:
        logger.warning("luml-sdk not installed, skipping experiment linking")
    except Exception:
        logger.warning(
            "Failed to link experiments to %s", model_path, exc_info=True,
        )


async def _do_upload(
    upload_queue: UploadQueue,
    upload_id: str,
    model_path: str,
    presigned_url: str,
    engine: Any,  # noqa: ANN401
    run_id: str,
    node_id: str,
) -> None:
    try:
        with open(model_path, "rb") as f:
            file_content = f.read()
        if not file_content:
            raise RuntimeError(f"Artifact file is empty: {model_path}")
        logger.info(
            "Uploading %s (%d bytes) for upload %s",
            model_path, len(file_content), upload_id,
        )
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                presigned_url,
                content=file_content,
                headers={"Content-Type": "application/octet-stream"},
                timeout=300,
            )
            resp.raise_for_status()
            body = resp.text
            if body and "<Error>" in body:
                raise RuntimeError(
                    f"Storage returned error: {body[:500]}"
                )
        upload_queue.complete(upload_id)
        if engine is not None:
            engine._emit_event(
                run_id, node_id, "upload_completed",
                {
                    "upload_id": upload_id,
                    "run_id": run_id,
                    "node_id": node_id,
                },
            )
    except Exception as exc:
        error_msg = str(exc)
        logger.warning(
            "Upload %s failed: %s (path=%s)",
            upload_id, error_msg, model_path, exc_info=True,
        )
        upload_queue.fail(upload_id, error_msg)
        upload = upload_queue.get(upload_id)
        status = upload.status if upload else UploadStatus.FAILED
        if engine is not None:
            engine._emit_event(
                run_id, node_id, "upload_failed",
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

    engine = getattr(request.app.state, "engine", None)
    asyncio.create_task(
        _do_upload(
            upload_queue=upload_queue,
            upload_id=upload_id,
            model_path=upload.model_path,
            presigned_url=body.presigned_url,
            engine=engine,
            run_id=run_id,
            node_id=upload.node_id,
        ),
    )
    return JSONResponse(status_code=202, content={"status": "accepted"})


class ArtifactLinkIn(BaseModel):
    artifact_id: str
    organization_id: str
    orbit_id: str
    collection_id: str


@router.post(
    "/{run_id}/uploads/{upload_id}/artifact-link",
    status_code=200,
)
def post_artifact_link(
    request: Request,
    run_id: str,
    upload_id: str,
    body: ArtifactLinkIn,
) -> JSONResponse:
    upload_queue: UploadQueue = request.app.state.upload_queue
    upload = upload_queue.get(upload_id)
    if upload is None:
        return JSONResponse(status_code=404, content={"detail": "Upload not found"})

    db = request.app.state.db
    node = db.get_run_node(upload.node_id)
    if node is None:
        return JSONResponse(status_code=404, content={"detail": "Node not found"})

    import json as _json
    result = _json.loads(node.result_json) if node.result_json else {}
    result["artifact_link"] = {
        "artifact_id": body.artifact_id,
        "organization_id": body.organization_id,
        "orbit_id": body.orbit_id,
        "collection_id": body.collection_id,
    }
    db.update_node_result(node.id, _json.dumps(result))

    engine = getattr(request.app.state, "engine", None)
    if engine is not None:
        engine._emit_event(
            run_id, node.id, "node_updated",
            {"result": result},
        )

    return JSONResponse(status_code=200, content={"status": "ok"})


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
