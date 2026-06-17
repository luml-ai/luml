import builtins
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from luml_api._exceptions import ResourceNotFoundError
from luml_api._types import (
    ArtifactType,
    SortOrder,
    Stage,
    StageUpsertIn,
    Track,
    TrackEntriesList,
    TrackEntry,
    TrackEntrySortBy,
    TracksList,
    TrackSortBy,
    is_uuid,
)
from luml_api._utils import find_by_value
from luml_api.resources._listed_resource import ListedResource
from luml_api.resources._validators import validate_orbit

if TYPE_CHECKING:
    from luml_api._client import AsyncLumlClient, LumlClient


class TrackResourceBase(ABC):
    @abstractmethod
    def create(
        self,
        name: str,
        artifact_type: ArtifactType,
        description: str | None = None,
        tags: list[str] | None = None,
        stages: list[str] | None = None,
    ) -> Track:
        pass

    @abstractmethod
    def list(
        self,
        start_after: str | None = None,
        limit: int = 100,
        sort_by: TrackSortBy = TrackSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        types: list[str] | None = None,
    ) -> TracksList:
        pass

    @abstractmethod
    def get(self, track_id: str) -> Track:
        pass

    @abstractmethod
    def update(
        self,
        track_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        stages: builtins.list[StageUpsertIn] | None = None,
    ) -> Track:
        pass

    @abstractmethod
    def delete(self, track_id: str) -> None:
        pass

    @abstractmethod
    def list_stages(self, track_id: str) -> builtins.list[Stage]:
        pass

    @abstractmethod
    def add_artifact(
        self, track_id: str, artifact_id: str, stage: str | None = None
    ) -> TrackEntry:
        pass

    @abstractmethod
    def get_artifact(self, track_id: str, tracked_artifact_id: str) -> TrackEntry:
        pass

    @abstractmethod
    def get_artifact_by_stage(self, track_id: str, stage: str) -> TrackEntry:
        pass

    @abstractmethod
    def list_artifacts(
        self,
        track_id: str,
        start_after: str | None = None,
        limit: int = 50,
        sort_by: TrackEntrySortBy = TrackEntrySortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        stage: str | None = None,
    ) -> TrackEntriesList:
        pass

    @abstractmethod
    def update_artifact(
        self,
        track_id: str,
        tracked_artifact_id: str,
        stage: str | None = None,
        force: bool = False,
    ) -> TrackEntry:
        pass

    @abstractmethod
    def remove_artifact(self, track_id: str, tracked_artifact_id: str) -> None:
        pass

    @abstractmethod
    def remove_batch_artifacts(
        self, track_id: str, tracked_artifact_ids: builtins.list[str]
    ) -> None:
        pass


class TrackResource(TrackResourceBase, ListedResource):
    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    @validate_orbit
    def create(
        self,
        name: str,
        artifact_type: ArtifactType,
        description: str | None = None,
        tags: list[str] | None = None,
        stages: list[str] | None = None,
    ) -> Track:
        response = self._client.post(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks",
            json={
                "name": name,
                "artifact_type": artifact_type.value,
                "description": description,
                "tags": tags,
                "stages": stages,
            },
        )

        return Track.model_validate(response)

    @validate_orbit
    def list(
        self,
        *,
        start_after: str | None = None,
        limit: int = 100,
        sort_by: TrackSortBy = TrackSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        types: list[ArtifactType] | None = None,
    ) -> TracksList:
        params: dict[str, Any] = {
            "limit": limit,
            "order": order.value,
        }

        if start_after:
            params["cursor"] = start_after
        if sort_by:
            params["sort_by"] = (
                sort_by.value if isinstance(sort_by, TrackSortBy) else sort_by
            )
        if types:
            params["types"] = [
                t.value if isinstance(t, ArtifactType) else t for t in types
            ]
        if search:
            params["search"] = search

        response = self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks",
            params=params,
        )

        if response is None:
            return TracksList(items=[])

        return TracksList.model_validate(response)

    def _get_by_name(self, name: str) -> Track | None:
        return find_by_value(
            self.list().items,
            name,
            condition=lambda t: t.name == name,
        )

    @validate_orbit
    def get(self, track_id: str) -> Track | None:
        if not is_uuid(track_id):
            return self._get_by_name(track_id)

        response = self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}",
        )
        if response is None:
            return None
        return Track.model_validate(response)

    @validate_orbit
    def update(
        self,
        track_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        stages: builtins.list[StageUpsertIn] | None = None,
    ) -> Track:
        response = self._client.patch(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}",
            json=self._client.filter_none(
                {
                    "name": name,
                    "description": description,
                    "tags": tags,
                    "stages": (
                        [stage.model_dump(mode="json") for stage in stages]
                        if stages is not None
                        else None
                    ),
                }
            ),
        )
        return Track.model_validate(response)

    @validate_orbit
    def delete(self, track_id: str) -> None:
        self._client.delete(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}",
        )

    @validate_orbit
    def list_stages(self, track_id: str) -> builtins.list[Stage]:
        response = self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/stages",
        )
        if response is None:
            return []
        return [Stage.model_validate(stage) for stage in response]

    @validate_orbit
    def add_artifact(
        self, track_id: str, artifact_id: str, stage: str | None = None
    ) -> TrackEntry:
        stage_id = (
            self._resolve_stage_id(track_id, stage) if stage is not None else None
        )
        response = self._client.post(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries",
            json={"artifact_id": artifact_id, "stage_id": stage_id},
        )
        return TrackEntry.model_validate(response)

    @validate_orbit
    def get_artifact(self, track_id: str, tracked_artifact_id: str) -> TrackEntry:
        response = self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries/{tracked_artifact_id}",
        )
        return TrackEntry.model_validate(response)

    def _resolve_stage_id(self, track_id: str, stage: str) -> str:
        if is_uuid(stage):
            return stage
        stages = self.list_stages(track_id)
        found = find_by_value(stages, stage, condition=lambda s: s.name == stage)
        if found is None:
            raise ResourceNotFoundError("Stage", stage, all_values=stages)
        return str(found.id)

    @validate_orbit
    def get_artifact_by_stage(self, track_id: str, stage: str) -> TrackEntry:
        stage_id = self._resolve_stage_id(track_id, stage)
        response = self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries/by-stage",
            params={"stage_id": stage_id},
        )
        return TrackEntry.model_validate(response)

    @validate_orbit
    def list_artifacts(
        self,
        track_id: str,
        start_after: str | None = None,
        limit: int = 50,
        sort_by: TrackEntrySortBy = TrackEntrySortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        stage: str | None = None,
    ) -> TrackEntriesList:
        params: dict[str, Any] = {"limit": limit, "order": order.value}
        if start_after:
            params["cursor"] = start_after
        if sort_by:
            params["sort_by"] = sort_by.value
        if stage:
            params["stage"] = self._resolve_stage_id(track_id, stage)

        response = self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries",
            params=params,
        )
        if response is None:
            return TrackEntriesList(items=[], cursor=None)
        return TrackEntriesList.model_validate(response)

    @validate_orbit
    def update_artifact(
        self,
        track_id: str,
        tracked_artifact_id: str,
        stage: str | None = None,
        force: bool = False,
    ) -> TrackEntry:
        stage_id = (
            self._resolve_stage_id(track_id, stage) if stage is not None else None
        )
        response = self._client.patch(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries/{tracked_artifact_id}",
            json=self._client.filter_none({"stage_id": stage_id}),
            params={"force": force},
        )
        return TrackEntry.model_validate(response)

    @validate_orbit
    def remove_artifact(self, track_id: str, tracked_artifact_id: str) -> None:
        self._client.delete(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries/{tracked_artifact_id}",
        )

    @validate_orbit
    def remove_batch_artifacts(
        self, track_id: str, tracked_artifact_ids: builtins.list[str]
    ) -> None:
        self._client.delete(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries",
            json={"entry_ids": tracked_artifact_ids},
        )


class AsyncTrackResource(TrackResourceBase, ListedResource):
    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    @validate_orbit
    async def create(
        self,
        name: str,
        artifact_type: ArtifactType,
        description: str | None = None,
        tags: list[str] | None = None,
        stages: list[str] | None = None,
    ) -> Track:
        response = await self._client.post(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks",
            json={
                "name": name,
                "artifact_type": artifact_type.value,
                "description": description,
                "tags": tags,
                "stages": stages,
            },
        )
        return Track.model_validate(response)

    @validate_orbit
    async def list(
        self,
        *,
        start_after: str | None = None,
        limit: int = 100,
        sort_by: TrackSortBy = TrackSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        types: list[ArtifactType] | None = None,
    ) -> TracksList:
        params: dict[str, Any] = {
            "limit": limit,
            "order": order.value,
        }

        if start_after:
            params["cursor"] = start_after
        if sort_by:
            params["sort_by"] = (
                sort_by.value if isinstance(sort_by, TrackSortBy) else sort_by
            )
        if types:
            params["types"] = [
                t.value if isinstance(t, ArtifactType) else t for t in types
            ]
        if search:
            params["search"] = search

        response = await self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks",
            params=params,
        )

        if response is None:
            return TracksList(items=[])

        return TracksList.model_validate(response)

    async def _get_by_name(self, name: str) -> Track | None:
        tracks = await self.list()
        return find_by_value(
            tracks.items,
            name,
            condition=lambda t: t.name == name,
        )

    @validate_orbit
    async def get(self, track_id: str) -> Track | None:
        if not is_uuid(track_id):
            return await self._get_by_name(track_id)

        response = await self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}",
        )
        if response is None:
            return None
        return Track.model_validate(response)

    @validate_orbit
    async def update(
        self,
        track_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        stages: builtins.list[StageUpsertIn] | None = None,
    ) -> Track:
        response = await self._client.patch(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}",
            json=self._client.filter_none(
                {
                    "name": name,
                    "description": description,
                    "tags": tags,
                    "stages": (
                        [stage.model_dump(mode="json") for stage in stages]
                        if stages is not None
                        else None
                    ),
                }
            ),
        )
        return Track.model_validate(response)

    @validate_orbit
    async def delete(self, track_id: str) -> None:
        await self._client.delete(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}",
        )

    @validate_orbit
    async def list_stages(self, track_id: str) -> builtins.list[Stage]:
        response = await self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/stages",
        )
        if response is None:
            return []
        return [Stage.model_validate(stage) for stage in response]

    @validate_orbit
    async def add_artifact(
        self, track_id: str, artifact_id: str, stage: str | None = None
    ) -> TrackEntry:
        stage_id = (
            await self._resolve_stage_id(track_id, stage) if stage is not None else None
        )
        response = await self._client.post(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries",
            json={"artifact_id": artifact_id, "stage_id": stage_id},
        )
        return TrackEntry.model_validate(response)

    @validate_orbit
    async def get_artifact(self, track_id: str, tracked_artifact_id: str) -> TrackEntry:
        response = await self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries/{tracked_artifact_id}",
        )
        return TrackEntry.model_validate(response)

    async def _resolve_stage_id(self, track_id: str, stage: str) -> str:
        if is_uuid(stage):
            return stage
        stages = await self.list_stages(track_id)
        found = find_by_value(stages, stage, condition=lambda s: s.name == stage)
        if found is None:
            raise ResourceNotFoundError("Stage", stage, all_values=stages)
        return str(found.id)

    @validate_orbit
    async def get_artifact_by_stage(self, track_id: str, stage: str) -> TrackEntry:
        stage_id = await self._resolve_stage_id(track_id, stage)
        response = await self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries/by-stage",
            params={"stage_id": stage_id},
        )
        return TrackEntry.model_validate(response)

    @validate_orbit
    async def list_artifacts(
        self,
        track_id: str,
        start_after: str | None = None,
        limit: int = 50,
        sort_by: TrackEntrySortBy = TrackEntrySortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        stage: str | None = None,
    ) -> TrackEntriesList:
        params: dict[str, Any] = {"limit": limit, "order": order.value}
        if start_after:
            params["cursor"] = start_after
        if sort_by:
            params["sort_by"] = sort_by.value
        if stage:
            params["stage"] = await self._resolve_stage_id(track_id, stage)

        response = await self._client.get(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries",
            params=params,
        )
        if response is None:
            return TrackEntriesList(items=[], cursor=None)
        return TrackEntriesList.model_validate(response)

    @validate_orbit
    async def update_artifact(
        self,
        track_id: str,
        tracked_artifact_id: str,
        stage: str | None = None,
        force: bool = False,
    ) -> TrackEntry:
        stage_id = (
            await self._resolve_stage_id(track_id, stage) if stage is not None else None
        )
        response = await self._client.patch(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries/{tracked_artifact_id}",
            json=self._client.filter_none({"stage_id": stage_id}),
            params={"force": force},
        )
        return TrackEntry.model_validate(response)

    @validate_orbit
    async def remove_artifact(self, track_id: str, tracked_artifact_id: str) -> None:
        await self._client.delete(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries/{tracked_artifact_id}",
        )

    @validate_orbit
    async def remove_batch_artifacts(
        self, track_id: str, tracked_artifact_ids: builtins.list[str]
    ) -> None:
        await self._client.delete(
            f"/v1/organizations/{self._client.organization}/orbits/{self._client.orbit}/tracks/{track_id}/entries",
            json={"entry_ids": tracked_artifact_ids},
        )
