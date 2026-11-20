import hmac
import json
import time

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from lumlflow.file_response import file_bytes_response
from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.handlers.models import ModelsHandler
from lumlflow.schemas.experiments import (
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    FileNode,
    MetricBuckets,
    MetricBucketsRequest,
    MetricCatalog,
    UpdateExperiment,
)
from lumlflow.schemas.models import Model

experiments_router = APIRouter(
    prefix="/api/experiments",
    tags=["experiments"],
)

experiments_handler = ExperimentsHandler()
models_handler = ModelsHandler()


@experiments_router.get("/{experiment_id}", response_model=ExperimentDetails)
def get_experiment(experiment_id: str) -> ExperimentDetails:
    return experiments_handler.get_experiment(experiment_id)


@experiments_router.patch("/{experiment_id}", response_model=Experiment)
def update_experiment(experiment_id: str, body: UpdateExperiment) -> Experiment:
    return experiments_handler.update_experiment(experiment_id, body)


@experiments_router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(experiment_id: str) -> None:
    experiments_handler.delete_experiment(experiment_id)


@experiments_router.get(
    "/{experiment_id}/metrics/{key:path}", response_model=ExperimentMetricHistory
)
def get_experiment_metric_history(
    experiment_id: str, key: str, max_points: int = 1000
) -> ExperimentMetricHistory:
    return experiments_handler.get_experiment_metric_history(
        experiment_id, key, max_points
    )


@experiments_router.get("/{experiment_id}/metric-catalog", response_model=MetricCatalog)
def get_metric_catalog(experiment_id: str, response: Response) -> MetricCatalog:
    # A running experiment keeps growing, so a cached catalog would hide new points.
    response.headers["Cache-Control"] = "no-store"
    return experiments_handler.get_metric_catalog(experiment_id)


@experiments_router.post(
    "/{experiment_id}/metric-buckets", response_model=MetricBuckets
)
def get_metric_buckets(experiment_id: str, body: MetricBucketsRequest) -> MetricBuckets:
    return experiments_handler.get_metric_buckets(experiment_id, body)


@experiments_router.get("/{experiment_id}/models", response_model=list[Model])
def list_experiment_models(experiment_id: str) -> list[Model]:
    return models_handler.list_experiment_models(experiment_id)


@experiments_router.get("/{experiment_id}/attachments/content")
def get_attachment_content(
    request: Request, experiment_id: str, file_path: str
) -> Response:
    path = experiments_handler.attachment_path(experiment_id, file_path)
    response = file_bytes_response(request, path)
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return response


def _preview_signature(
    request: Request, experiment_id: str, file_path: str, expires: int
) -> str:
    scope = json.dumps(
        ["attachment-preview", experiment_id, file_path, expires]
    ).encode()
    return hmac.digest(request.app.state.session_token.encode(), scope, "sha256").hex()


@experiments_router.post("/{experiment_id}/attachments/preview")
def attachment_preview_ticket(
    request: Request, experiment_id: str, file_path: str
) -> dict[str, int | str]:
    path = experiments_handler.attachment_path(experiment_id, file_path)
    expires = int(time.time()) + 24 * 60 * 60
    return {
        "expires": expires,
        "signature": _preview_signature(request, experiment_id, file_path, expires),
        "size": path.stat().st_size,
    }


@experiments_router.get("/preview/content")
def stream_attachment_preview(
    request: Request, experiment_id: str, file_path: str, expires: int, signature: str
) -> Response:
    expected = _preview_signature(request, experiment_id, file_path, expires)
    if expires < time.time() or not hmac.compare_digest(
        signature.encode(), expected.encode()
    ):
        raise HTTPException(
            status_code=401, detail="Invalid or expired attachment preview"
        )
    return get_attachment_content(request, experiment_id, file_path)


@experiments_router.get("/{experiment_id}/attachments", response_model=list[FileNode])
def list_experiment_attachments(
    experiment_id: str, parent_path: str | None = None
) -> list[FileNode]:
    return experiments_handler.list_attachments_tree(
        experiment_id, parent_path=parent_path
    )
