from uuid import UUID

from sqlalchemy.exc import IntegrityError

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactTypeMismatchError,
    NotFoundError,
)
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.tracks import (
    TrackEntryRepository,
    TrackRepository,
    TrackStageRepository,
)
from luml.schemas.general import Cursor, PaginationParams, SortOrder
from luml.schemas.permissions import Action, Resource
from luml.schemas.tracks import (
    Stage,
    StageCreate,
    StageCreateIn,
    StageUpdate,
    StageUpdateIn,
    Track,
    TrackCreate,
    TrackCreateIn,
    TrackEntriesList,
    TrackEntry,
    TrackEntryCreate,
    TrackEntryCreateIn,
    TrackEntrySortBy,
    TrackEntryUpdate,
    TrackEntryUpdateIn,
    TracksList,
    TrackSortBy,
    TrackUpdate,
    TrackUpdateIn,
)
from luml.utils.pagination import decode_cursor, encode_cursor


class TracksHandler:
    __track_repository = TrackRepository(engine)
    __stage_repository = TrackStageRepository(engine)
    __entry_repository = TrackEntryRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __artifact_repository = ArtifactRepository(engine)
    __collection_repository = CollectionRepository(engine)
    __permissions_handler = PermissionsHandler()

    @staticmethod
    def _validate_cursor(
        cursor: Cursor | None,
        sort_by: TrackSortBy,
        order: SortOrder,
        orbit_id: UUID,
    ) -> Cursor | None:
        if cursor and (
            cursor.sort_by == sort_by.value
            and cursor.order == order.value
            and cursor.scope_id == orbit_id
        ):
            return cursor
        return None

    async def create_track(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_in: TrackCreateIn,
    ) -> Track:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.CREATE,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")

        track_create = TrackCreate(
            **track_in.model_dump(exclude={"stages"}),
            orbit_id=orbit_id,
        )
        try:
            track = await self.__track_repository.create_track(
                track_create, stage_names=track_in.stages
            )
        except IntegrityError as error:
            message = str(error)
            if "uq_tracks_orbit_id_name" in message:
                raise ApplicationError(
                    f"Track with name '{track_in.name}' already exists in this orbit.",
                    409,
                ) from error
            if "uq_track_stages_track_id_name" in message:
                raise ApplicationError(
                    "Duplicate stage names are not allowed.", 409
                ) from error
            raise

        return track

    async def list_tracks(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        cursor_str: str | None = None,
        limit: int = 100,
        sort_by: TrackSortBy = TrackSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        types: list[str] | None = None,
    ) -> TracksList:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.LIST,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")

        cursor = decode_cursor(cursor_str)
        use_cursor = self._validate_cursor(cursor, sort_by, order, orbit_id)

        pagination = PaginationParams(
            cursor=use_cursor,
            sort_by=str(sort_by.value),
            order=order,
            limit=limit,
            scope_id=orbit_id,
        )

        items, cursor = await self.__track_repository.get_orbit_tracks(
            orbit_id=orbit_id,
            pagination=pagination,
            search=search,
            types=types,
        )

        return TracksList(items=items, cursor=encode_cursor(cursor))

    async def get_track(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
    ) -> Track:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.READ,
            orbit_id,
        )
        track = await self.__track_repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")
        return track

    async def update_track(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        track_in: TrackUpdateIn,
    ) -> Track:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.UPDATE,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")

        try:
            updated = await self.__track_repository.update_track(
                track_id,
                TrackUpdate(
                    id=track_id,
                    name=track_in.name,
                    description=track_in.description,
                    tags=track_in.tags,
                ),
            )
        except IntegrityError as error:
            raise ApplicationError(
                f"Track with name '{track_in.name}' already exists in this orbit.",
                409,
            ) from error

        if not updated:
            raise NotFoundError("Track not found")
        return updated

    async def delete_track(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.DELETE,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        track = await self.__track_repository.get_track(track_id)
        if not track:
            raise NotFoundError("Track not found")
        await self.__track_repository.delete_track(track_id)

    async def create_entry(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        entry_in: TrackEntryCreateIn,
    ) -> TrackEntry:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.CREATE,
            orbit_id,
        )
        track = await self.__track_repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        artifact = await self.__artifact_repository.get_artifact(entry_in.artifact_id)
        if not artifact:
            raise NotFoundError("Artifact not found")

        if artifact.type != track.artifact_type:
            raise ArtifactTypeMismatchError(
                f"Artifact type '{artifact.type}' does not match "
                f"track artifact type '{track.artifact_type}'."
            )

        collection = await self.__collection_repository.get_collection(
            artifact.collection_id
        )
        if not collection or collection.orbit_id != orbit_id:
            raise ApplicationError(
                "Artifact must belong to the same orbit as the track.", 422
            )

        entry_create = TrackEntryCreate(
            track_id=track_id,
            artifact_id=entry_in.artifact_id,
            added_by=user_id,
        )
        try:
            return await self.__entry_repository.create_entry(entry_create)
        except IntegrityError as error:
            raise ApplicationError(
                "Artifact is already an entry in this track.", 409
            ) from error

    async def get_entry(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        entry_id: UUID,
    ) -> TrackEntry | None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.READ,
            orbit_id,
        )

        track = await self.__track_repository.get_track(track_id)

        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        entry = await self.__entry_repository.get_entry(entry_id)

        if entry and entry.track_id != track_id:
            raise NotFoundError("Entry not found")

        return entry

    async def get_entry_by_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        stage_id: UUID,
    ) -> TrackEntry | None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.READ,
            orbit_id,
        )

        track = await self.__track_repository.get_track(track_id)

        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        stage = await self.__stage_repository.get_stage(stage_id)

        if not stage or stage.track_id != track_id:
            raise NotFoundError("Stage not found")

        return await self.__entry_repository.get_entry_by_stage(track_id, stage_id)

    async def list_entries(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        cursor_str: str | None = None,
        limit: int = 100,
        sort_by: TrackEntrySortBy = TrackEntrySortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        stage_id: UUID | None = None,
    ) -> TrackEntriesList:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.READ,
            orbit_id,
        )

        track = await self.__track_repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        cursor = decode_cursor(cursor_str)
        use_cursor: Cursor | None = None
        if cursor and (
            cursor.sort_by == sort_by.value
            and cursor.order == order.value
            and cursor.scope_id == track_id
        ):
            use_cursor = cursor

        pagination = PaginationParams(
            cursor=use_cursor,
            sort_by=sort_by.value,
            order=order,
            limit=limit,
            scope_id=track_id,
        )

        items, new_cursor = await self.__entry_repository.list_entries(
            track_id=track_id,
            pagination=pagination,
            stage_id=stage_id,
        )

        return TrackEntriesList(items=items, cursor=encode_cursor(new_cursor))

    async def update_entry(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        entry_id: UUID,
        entry_in: TrackEntryUpdateIn,
        force: bool = False,
    ) -> TrackEntry:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.UPDATE,
            orbit_id,
        )
        entry = await self.__entry_repository.get_entry(entry_id)
        if not entry or entry.track_id != track_id:
            raise NotFoundError("Entry not found")

        if entry_in.stage_id is not None:
            stage = await self.__stage_repository.get_stage(entry_in.stage_id)
            if not stage or stage.track_id != track_id:
                raise ApplicationError("Stage does not belong to this track.", 422)

            holder = await self.__entry_repository.get_entry_by_stage(
                track_id, entry_in.stage_id
            )
            if holder and holder.id != entry_id and not force:
                raise ApplicationError(
                    f"Stage '{stage.name}' is already assigned to "
                    f"v{holder.version}. "
                    f"Use force to reassign.",
                    409,
                )

        update_data = TrackEntryUpdate(stage_id=entry_in.stage_id)
        updated = await self.__entry_repository.update_entry(
            entry_id, update_data, force=force
        )
        if not updated:
            raise NotFoundError("Entry not found")
        return updated

    async def delete_entry(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        entry_id: UUID,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.DELETE,
            orbit_id,
        )
        entry = await self.__entry_repository.get_entry(entry_id)
        if not entry or entry.track_id != track_id:
            raise NotFoundError("Entry not found")
        await self.__entry_repository.delete_entry(entry_id)

    async def delete_entries(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        entry_ids: list[UUID],
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.DELETE,
            orbit_id,
        )
        track = await self.__track_repository.get_track(track_id)

        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        await self.__entry_repository.delete_entries(track_id, entry_ids)

    async def list_entries_for_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        artifact_id: UUID,
    ) -> list[TrackEntry]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.READ,
            orbit_id,
        )
        return await self.__entry_repository.list_entries_for_artifact(artifact_id)

    async def create_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        stage_in: StageCreateIn,
    ) -> Stage:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.CREATE,
            orbit_id,
        )
        track = await self.__track_repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        try:
            return await self.__stage_repository.create_stage(
                StageCreate(track_id=track_id, name=stage_in.name)
            )
        except IntegrityError as error:
            raise ApplicationError(
                f"Stage with name '{stage_in.name}' already exists in this track.",
                409,
            ) from error

    async def list_stages(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
    ) -> list[Stage]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.READ,
            orbit_id,
        )
        track = await self.__track_repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")
        return await self.__stage_repository.list_stages(track_id)

    async def update_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        track_id: UUID,
        stage_id: UUID,
        stage_in: StageUpdateIn,
    ) -> Stage:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.TRACK,
            Action.UPDATE,
            orbit_id,
        )
        track = await self.__track_repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        try:
            updated = await self.__stage_repository.update_stage(
                stage_id, StageUpdate(id=stage_id, name=stage_in.name)
            )
        except IntegrityError as error:
            raise ApplicationError(
                f"Stage with name '{stage_in.name}' already exists in this track.",
                409,
            ) from error

        if not updated:
            raise NotFoundError("Stage not found")
        return updated

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
            organization_id,
            user_id,
            Resource.TRACK,
            Action.DELETE,
            orbit_id,
        )
        track = await self.__track_repository.get_track(track_id)
        if not track or track.orbit_id != orbit_id:
            raise NotFoundError("Track not found")

        in_use = await self.__stage_repository.is_stage_in_use(stage_id)
        if in_use and not force:
            raise ApplicationError(
                "Stage is currently assigned to an entry. "
                "Use force to delete and unassign.",
                409,
            )
        if in_use:
            await self.__stage_repository.clear_stage_from_entries(track_id, stage_id)

        await self.__stage_repository.delete_stage(stage_id)
