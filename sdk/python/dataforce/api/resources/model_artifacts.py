import builtins
from typing import TYPE_CHECKING

from .._types import ModelArtifact
from .._utils import find_by_name
from ._validators import validate_collection

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class ModelArtifactResource:
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    @validate_collection
    def get(
        self, collection_id: int | None, model_value: str | int
    ) -> ModelArtifact | None:
        return self._get_by_name(collection_id, model_value)

    @validate_collection
    def _get_by_name(self, collection_id: int | None, name: str) -> ModelArtifact | None:
        return find_by_name(
            self.list(collection_id),
            name,
            condition=lambda m: m.model_name == name or m.file_name == name,
        )

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
    ) -> ModelArtifact:
        return self._client.post(
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
            return await self.get_by_name(collection_id, model_value)
        return None

    @validate_collection
    async def get_by_name(
        self, collection_id: int | None, name: str
    ) -> ModelArtifact | None:
        return find_by_name(
            await self.list(collection_id),
            name,
            condition=lambda m: m.model_name == name or m.file_name == name,
        )

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
    ) -> ModelArtifact:
        return await self._client.post(
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
