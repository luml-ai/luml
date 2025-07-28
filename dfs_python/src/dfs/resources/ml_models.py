from typing import List

from .._resource import APIResource
from .._types import MLModel


class MLModelResource(APIResource):
    async def list(
        self, organization_id: int, orbit_id: int, collection_id: int
    ) -> list[MLModel]:
        response = await self._get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models"
        )
        if response is None:
            return []
        return [MLModel(**model) for model in response]

    async def download_url(
        self, organization_id: int, orbit_id: int, collection_id: int, model_id: int
    ):
        return await self._get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}/download-url"
        )

    async def delete_url(
        self, organization_id: int, orbit_id: int, collection_id: int, model_id: int
    ):
        return await self._get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}/delete-url"
        )

    async def create(
        self,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        file_name: str,
        metrics: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        model_name: str | None = None,
        description: str | None = None,
        tags: List[str] | None = None,
    ):
        return await self._post(
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

    async def update(
        self,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        model_id: int,
        file_name: str | None = None,
        model_name: str | None = None,
        description: str | None = None,
        tags: List[str] | None = None,
        status: str | None = None,
    ):
        return await self._patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}",
            json=self._filter_none(
                {
                    "file_name": file_name,
                    "model_name": model_name,
                    "description": description,
                    "tags": tags,
                    "status": status,
                }
            ),
        )

    async def delete(
        self, organization_id: int, orbit_id: int, collection_id: int, model_id: int
    ):
        return await self._delete(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/ml-models/{model_id}"
        )
