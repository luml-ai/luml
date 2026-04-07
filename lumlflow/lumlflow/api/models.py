from fastapi import APIRouter, status

from lumlflow.handlers.models import ModelsHandler
from lumlflow.schemas.models import Model, UpdateModel

models_router = APIRouter(prefix="/api/models", tags=["models"])
models_handler = ModelsHandler()


@models_router.patch("/{model_id}", response_model=Model)
def update_model(model_id: str, body: UpdateModel) -> Model:
    return models_handler.update_model(model_id, body)


@models_router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: str) -> None:
    models_handler.delete_model(model_id)
