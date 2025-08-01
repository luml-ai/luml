import builtins
from typing import TYPE_CHECKING

from .._types import ModelArtifact
from .._utils import find_by_name
from ._validators import validate_organization_orbit_collection

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class ModelArtifactResource:
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    @validate_organization_orbit_collection
    def get_by_name(
        self, organization_id: int, orbit_id: int, collection_id: int, name: str
    ) -> ModelArtifact | None:
        return find_by_name(
            self.list(organization_id, orbit_id, collection_id),
            name,
            condition=lambda m: m.model_name == name or m.file_name == name,
        )

    @validate_organization_orbit_collection
    def list(
        self, organization_id: int, orbit_id: int, collection_id: int
    ) -> list[ModelArtifact]:
        response = self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models"
        )
        if response is None:
            return []
        return [ModelArtifact.model_validate(model) for model in response]

    @validate_organization_orbit_collection
    def download_url(
        self, organization_id: int, orbit_id: int, collection_id: int, model_id: int
    ) -> dict:
        return self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}/download-url"
        )

    @validate_organization_orbit_collection
    def delete_url(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
        model_id: int,
    ) -> dict:
        return self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}/delete-url"
        )

    @validate_organization_orbit_collection
    def create(
        self,
        organization_id: int | None,
        orbit_id: int | None,
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
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models",
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

    @validate_organization_orbit_collection
    def update(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
        model_id: int,
        file_name: str | None = None,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: str | None = None,
    ) -> ModelArtifact:
        return self._client.patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}",
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

    @validate_organization_orbit_collection
    def delete(
        self, organization_id: int, orbit_id: int, collection_id: int, model_id: int
    ) -> None:
        return self._client.delete(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}"
        )


class AsyncModelArtifactResource:
    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    @validate_organization_orbit_collection
    async def get_by_name(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
        name: str,
    ) -> ModelArtifact | None:
        return find_by_name(
            await self.list(organization_id, orbit_id, collection_id),
            name,
            condition=lambda m: m.model_name == name or m.file_name == name,
        )

    @validate_organization_orbit_collection
    async def list(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
    ) -> list[ModelArtifact]:
        response = await self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models"
        )
        if response is None:
            return []
        return [ModelArtifact.model_validate(model) for model in response]

    @validate_organization_orbit_collection
    async def download_url(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
        model_id: int,
    ) -> dict:
        return await self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}/download-url"
        )

    @validate_organization_orbit_collection
    async def delete_url(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
        model_id: int,
    ) -> dict:
        return await self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}/delete-url"
        )

    @validate_organization_orbit_collection
    async def create(
        self,
        organization_id: int | None,
        orbit_id: int | None,
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
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models",
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

    @validate_organization_orbit_collection
    async def update(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
        model_id: int,
        file_name: str | None = None,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: str | None = None,
    ) -> ModelArtifact:
        return await self._client.patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}",
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

    @validate_organization_orbit_collection
    async def delete(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
        model_id: int,
    ) -> None:
        return await self._client.delete(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}"
        )
