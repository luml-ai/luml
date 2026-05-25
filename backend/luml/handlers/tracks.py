from uuid import UUID

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.models.tracks import TrackArtifactOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.tracks import TrackRepository
from luml.schemas.general import Cursor, SortOrder
from luml.schemas.permissions import Action, Resource
from luml.schemas.tracks import (
    Track,
    TrackArtifact,
    TrackArtifactCreate,
    TrackArtifactStage,
    TrackArtifactUpdate,
    TrackArtifactUpdateResponse,
    TrackCreate,
    TrackEntriesList,
    TracksList,
    TrackStage,
    TrackStageConflict,
    TrackStageCreate,
    TrackStagesList,
    TrackStageUpdate,
    TrackUpdate,
)
from luml.utils.pagination import decode_cursor, encode_cursor


class TracksHandler:
    __repository = TrackRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def _validate_orbit(self, orbit_id: UUID, organization_id: UUID) -> None:
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")

    async def create_track(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        data: TrackCreate,
    ) -> Track:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.CREATE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        existing = await self.__repository.list_tracks(orbit_id)
        if any(t.name == data.name for t in existing):
            raise ApplicationError(
                "Track with this name already exists", 409
            )

        track_orm = await self.__repository.create_track(data, orbit_id, user_id)
        return Track.model_validate(track_orm, from_attributes=True)

    async def list_tracks(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
    ) -> TracksList:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.LIST, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        tracks = await self.__repository.list_tracks(orbit_id)
        items = [Track.model_validate(t, from_attributes=True) for t in tracks]
        return TracksList(items=items, cursor=None)

    async def get_track(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
    ) -> Track:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.READ, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")
        return Track.model_validate(track, from_attributes=True)

    async def update_track(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        data: TrackUpdate,
    ) -> Track:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.UPDATE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        if data.name is not None and data.name != track.name:
            existing = await self.__repository.list_tracks(orbit_id)
            if any(t.name == data.name for t in existing):
                raise ApplicationError(
                    "Track with this name already exists", 409
                )

        updated = await self.__repository.update_track(track, data)
        return Track.model_validate(updated, from_attributes=True)

    async def delete_track(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.DELETE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        await self.__repository.delete_track(track)


class TrackEntriesHandler:
    __repository = TrackRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __artifact_repository = ArtifactRepository(engine)
    __collection_repository = CollectionRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def _validate_orbit(self, orbit_id: UUID, organization_id: UUID) -> None:
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")

    @staticmethod
    def _entry_to_schema(entry_orm: TrackArtifactOrm) -> TrackArtifact:
        stage = None
        if entry_orm.stage is not None:
            stage = TrackArtifactStage.model_validate(
                entry_orm.stage, from_attributes=True
            )
        return TrackArtifact(
            id=entry_orm.id,
            track_id=entry_orm.track_id,
            artifact_id=entry_orm.artifact_id,
            version=entry_orm.version,
            stage=stage,
            created_at=entry_orm.created_at,
            added_by=entry_orm.added_by,
        )

    async def add_entry(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        data: TrackArtifactCreate,
    ) -> TrackArtifact:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.CREATE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        artifact = await self.__artifact_repository.get_artifact(data.artifact_id)
        if not artifact:
            raise NotFoundError("Artifact not found")
        if artifact.collection_id is None:
            raise ApplicationError(
                "Artifact must belong to the same orbit", 422
            )

        collection = await self.__collection_repository.get_collection(
            artifact.collection_id
        )
        if not collection or collection.orbit_id != orbit_id:
            raise ApplicationError(
                "Artifact must belong to the same orbit", 422
            )

        if artifact.type != track.artifact_type:
            raise ApplicationError(
                f"Artifact type '{artifact.type}' does not match "
                f"track type '{track.artifact_type}'",
                422,
            )

        existing_entries = await self.__repository.list_entries(track_id)
        if any(e.artifact_id == data.artifact_id for e in existing_entries):
            raise ApplicationError(
                "Artifact is already an entry in this track", 409
            )

        entry = await self.__repository.add_entry(track, data.artifact_id, user_id)
        return self._entry_to_schema(entry)

    async def list_entries(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        stage: str | None = None,
        cursor_str: str | None = None,
        page_size: int = 20,
    ) -> TrackEntriesList:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.LIST, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        cursor = decode_cursor(cursor_str) if cursor_str else None

        entries = await self.__repository.list_entries(
            track_id, stage_name=stage, cursor=cursor, page_size=page_size + 1
        )

        has_more = len(entries) > page_size
        if has_more:
            entries = entries[:page_size]

        next_cursor: str | None = None
        if has_more and entries:
            last_entry = entries[-1]
            next_cursor = encode_cursor(
                Cursor(
                    id=last_entry.id,
                    value=str(last_entry.created_at),
                    sort_by="created_at",
                    order=SortOrder.DESC,
                    scope_id=track_id,
                )
            )

        items = [self._entry_to_schema(e) for e in entries]
        return TrackEntriesList(items=items, cursor=next_cursor)

    async def patch_entry(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        entry_id: UUID,
        data: TrackArtifactUpdate,
        force: bool = False,
    ) -> TrackArtifactUpdateResponse:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.UPDATE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        entry = await self.__repository.get_entry(entry_id)
        if not entry or entry.track_id != track_id:
            raise NotFoundError("Entry not found")

        if data.stage_id is not None:
            stage = await self.__repository.get_stage(data.stage_id)
            if not stage or stage.track_id != track_id:
                raise ApplicationError(
                    "Stage does not belong to this track", 422
                )

            holder = await self.__repository.get_entry_holding_stage(
                track_id, data.stage_id
            )
            if holder and holder.id != entry.id:
                if not force:
                    conflict = TrackStageConflict(
                        stage_name=stage.name,
                        held_by_version=holder.version,
                    )
                    raise ApplicationError(
                        conflict.model_dump_json(), 409
                    )
                await self.__repository.update_entry_stage(holder, None)

        updated = await self.__repository.update_entry_stage(entry, data.stage_id)
        return TrackArtifactUpdateResponse(entry=self._entry_to_schema(updated))

    async def delete_entry(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        entry_id: UUID,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.DELETE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        entry = await self.__repository.get_entry(entry_id)
        if not entry or entry.track_id != track_id:
            raise NotFoundError("Entry not found")

        await self.__repository.delete_entry(entry)

    async def list_entries_for_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        artifact_id: UUID,
    ) -> TrackEntriesList:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.LIST, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        entries = await self.__repository.list_entries_for_artifact(
            orbit_id, artifact_id
        )
        items = [self._entry_to_schema(e) for e in entries]
        return TrackEntriesList(items=items, cursor=None)


class TrackStagesHandler:
    __repository = TrackRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def _validate_orbit(self, orbit_id: UUID, organization_id: UUID) -> None:
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")

    async def create_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        data: TrackStageCreate,
    ) -> TrackStage:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.CREATE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        existing = await self.__repository.list_stages(track_id)
        if any(s.name == data.name for s in existing):
            raise ApplicationError(
                "Stage with this name already exists in this track", 409
            )

        stage = await self.__repository.create_stage(track_id, data)
        return TrackStage.model_validate(stage, from_attributes=True)

    async def list_stages(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
    ) -> TrackStagesList:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.LIST, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        stages = await self.__repository.list_stages(track_id)
        items = [TrackStage.model_validate(s, from_attributes=True) for s in stages]
        return TrackStagesList(items=items, cursor=None)

    async def update_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        stage_id: UUID,
        data: TrackStageUpdate,
    ) -> TrackStage:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.UPDATE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        stage = await self.__repository.get_stage(stage_id)
        if not stage or stage.track_id != track_id:
            raise NotFoundError("Stage not found")

        if data.name is not None and data.name != stage.name:
            existing = await self.__repository.list_stages(track_id)
            if any(s.name == data.name for s in existing):
                raise ApplicationError(
                    "Stage with this name already exists in this track", 409
                )

        updated = await self.__repository.update_stage(stage, data)
        return TrackStage.model_validate(updated, from_attributes=True)

    async def delete_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        stage_id: UUID,
        force: bool = False,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.TRACK, Action.DELETE, orbit_id
        )
        await self._validate_orbit(orbit_id, organization_id)

        track = await self.__repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        stage = await self.__repository.get_stage(stage_id)
        if not stage or stage.track_id != track_id:
            raise NotFoundError("Stage not found")

        holder = await self.__repository.get_entry_holding_stage(track_id, stage_id)
        if holder and not force:
            raise ApplicationError(
                "Stage is assigned to entries. Use force=true to remove.", 409
            )

        if holder:
            await self.__repository.clear_stage_from_entries(stage_id)

        await self.__repository.delete_stage(stage)
