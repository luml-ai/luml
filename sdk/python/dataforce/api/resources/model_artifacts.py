import builtins
from typing import TYPE_CHECKING

from .._types import ModelArtifact
from .._utils import find_by_name
from ..utils.file_handler import FileHandler
from ..utils.model_artifacts import ModelFileHandler
from ._validators import validate_collection

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient

file_handler = FileHandler()


class ModelArtifactResource:
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    @validate_collection
    def get(
        self, collection_id: int | None, model_value: str | int
    ) -> ModelArtifact | None:
        if isinstance(model_value, str):
            return self._get_by_name(collection_id, model_value)
        return self._get_by_id(collection_id, model_value)

    def _get_by_name(
        self, collection_id: int | None, name: str
    ) -> ModelArtifact | None:
        return find_by_name(
            self.list(collection_id),
            name,
            condition=lambda m: m.model_name == name or m.file_name == name,
        )

    def _get_by_id(
        self, collection_id: int | None, model_value: int
    ) -> ModelArtifact | None:
        for model in self.list(collection_id):
            if model.id == model_value:
                return model
        return None

    @validate_collection
    def list(self, collection_id: int | None = None) -> list[ModelArtifact]:
        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts"
        )
        if response is None:
            return []
        return [ModelArtifact.model_validate(model) for model in response]

    @validate_collection
    def download_url(self, collection_id: int | None, model_id: int) -> dict:
        return self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}/download-url"
        )

    @validate_collection
    def delete_url(self, collection_id: int | None, model_id: int) -> dict:
        return self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}/delete-url"
        )

    def upload(
        self,
        file_path: str,
        model_name: str,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> ModelArtifact:
        model_details = ModelFileHandler(file_path).model_details()
        created_model = self.create(
            file_name=model_details.file_name,
            metrics=model_details.metrics,
            manifest=model_details.manifest,
            file_hash=model_details.file_hash,
            file_index=model_details.file_index,
            size=model_details.size,
            model_name=model_name,
            description=description,
            tags=tags,
        )
        file_handler.upload_file_with_progress(
            url=created_model["url"],
            file_path=file_path,
            file_size=model_details.size,
            description=f'"Uploading model "{model_name}"..."',
        )
        return created_model["model"]

    @validate_collection
    def download(
        self, collection_id: int | None, model_id: int, file_path: str | None = None
    ) -> None:
        if file_path is None:
            model = self._get_by_id(collection_id=collection_id, model_value=model_id)
            if model is None:
                raise ValueError(f"Model with id {model_id} not found")
            file_path = model.file_name

        download_info = self.download_url(
            collection_id=collection_id, model_id=model_id
        )
        download_url = download_info["url"]

        file_handler.download_file_with_progress(
            url=download_url,
            file_path=file_path,
            description=f'Downloading model id="{model_id}"...',
        )

    @validate_collection
    def create(
        self,
        collection_id: int | None,
        file_name: str,
        metrics: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> dict[str, str | ModelArtifact]:
        response = self._client.post(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts",
            json={
                "file_name": file_name,
                "metrics": metrics,
                "manifest": manifest,
                "file_hash": file_hash,
                "file_index": file_index,
                "size": size,
                "model_name": model_name,
                "description": description,
                "tags": tags,
            },
        )
        return {
            "url": response["url"],
            "model": ModelArtifact.model_validate(response["model"]),
        }

    @validate_collection
    def update(
        self,
        collection_id: int | None,
        model_id: int,
        file_name: str | None = None,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: str | None = None,
    ) -> ModelArtifact:
        return self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}",
            json=self._client.filter_none(
                {
                    "file_name": file_name,
                    "model_name": model_name,
                    "description": description,
                    "tags": tags,
                    "status": status,
                }
            ),
        )

    @validate_collection
    def delete(self, collection_id: int | None, model_id: int) -> None:
        return self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}"
        )


class AsyncModelArtifactResource:
    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    @validate_collection
    async def get(
        self, collection_id: int | None, model_value: str | int
    ) -> ModelArtifact | None:
        if isinstance(model_value, str):
            return await self._get_by_name(collection_id, model_value)
        return await self._get_by_id(collection_id, model_value)

    async def _get_by_name(
        self, collection_id: int | None, name: str
    ) -> ModelArtifact | None:
        return find_by_name(
            await self.list(collection_id),
            name,
            condition=lambda m: m.model_name == name or m.file_name == name,
        )

    async def _get_by_id(
        self, collection_id: int | None, model_value: int
    ) -> ModelArtifact | None:
        for model in await self.list(collection_id):
            if model.id == model_value:
                return model
        return None

    @validate_collection
    async def list(self, collection_id: int | None) -> list[ModelArtifact]:
        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts"
        )
        if response is None:
            return []
        return [ModelArtifact.model_validate(model) for model in response]

    @validate_collection
    async def download_url(self, collection_id: int | None, model_id: int) -> dict:
        return await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}/download-url"
        )

    @validate_collection
    async def delete_url(self, collection_id: int | None, model_id: int) -> dict:
        return await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}/delete-url"
        )

    @validate_collection
    async def create(
        self,
        collection_id: int | None,
        file_name: str,
        metrics: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> dict[str, str | ModelArtifact]:
        response = await self._client.post(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts",
            json={
                "file_name": file_name,
                "metrics": metrics,
                "manifest": manifest,
                "file_hash": file_hash,
                "file_index": file_index,
                "size": size,
                "model_name": model_name,
                "description": description,
                "tags": tags,
            },
        )

        return {
            "url": response["url"],
            "model": ModelArtifact.model_validate(response["model"]),
        }

    async def upload(
        self,
        file_path: str,
        model_name: str,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> ModelArtifact:
        model_details = ModelFileHandler(file_path).model_details()
        created_model = await self.create(
            file_name=model_details.file_name,
            metrics=model_details.metrics,
            manifest=model_details.manifest,
            file_hash=model_details.file_hash,
            file_index=model_details.file_index,
            size=model_details.size,
            model_name=model_name,
            description=description,
            tags=tags,
        )
        file_handler.upload_file_with_progress(
            url=created_model["url"],
            file_path=file_path,
            file_size=model_details.size,
            description=f'"Uploading model "{model_name}"..."',
        )
        return created_model["model"]

    @validate_collection
    async def download(
        self, collection_id: int | None, model_id: int, file_path: str | None = None
    ) -> None:
        if file_path is None:
            model = await self._get_by_id(
                collection_id=collection_id, model_value=model_id
            )
            if model is None:
                raise ValueError(f"Model with id {model_id} not found")
            file_path = model.file_name

        download_info = await self.download_url(
            collection_id=collection_id, model_id=model_id
        )
        download_url = download_info["url"]

        file_handler.download_file_with_progress(
            url=download_url,
            file_path=file_path,
            description=f'Downloading model id="{model_id}"...',
        )

    @validate_collection
    async def update(
        self,
        collection_id: int | None,
        model_id: int,
        file_name: str | None = None,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: str | None = None,
    ) -> ModelArtifact:
        return await self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}",
            json=self._client.filter_none(
                {
                    "file_name": file_name,
                    "model_name": model_name,
                    "description": description,
                    "tags": tags,
                    "status": status,
                }
            ),
        )

    @validate_collection
    async def delete(self, collection_id: int | None, model_id: int) -> None:
        return await self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}"
        )
