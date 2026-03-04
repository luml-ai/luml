from typing import Any

from fastapi import APIRouter, Request

from luml_agent.schemas import RepositoryCreateIn, RepositoryOut

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


def _get_handler(request: Request) -> Any:  # noqa: ANN401
    return request.app.state.repository_handler


@router.get("")
def list_repositories(
    request: Request,
) -> list[dict[str, Any]]:
    handler = _get_handler(request)
    return [
        RepositoryOut.model_validate(p).model_dump()
        for p in handler.list_all()
    ]


@router.post("", status_code=201)
def create_repository(
    request: Request, body: RepositoryCreateIn,
) -> dict[str, Any]:
    handler = _get_handler(request)
    repo = handler.create(body.name, body.path)
    return RepositoryOut.model_validate(repo).model_dump()


@router.delete("/{repository_id}")
def delete_repository(
    request: Request, repository_id: str,
) -> dict[str, str]:
    handler = _get_handler(request)
    handler.delete(repository_id)
    return {"status": "deleted"}
