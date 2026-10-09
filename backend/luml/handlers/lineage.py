from collections.abc import Iterable, Sequence
from uuid import UUID

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactNotFoundError,
    NotFoundError,
    OrbitNotFoundError,
)
from luml.models.lineage import LineageEdgeOrm, LineageNodeOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.lineage import LineageRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import ArtifactListed
from luml.schemas.lineage import (
    LineageBatchIn,
    LineageBatchResult,
    LineageCoordinates,
    LineageEdge,
    LineageGraph,
    LineageNode,
    LineageNodePair,
    LineageNodeRef,
    LineagePair,
    LineagePosition,
    LineageVia,
)
from luml.schemas.permissions import Action, Resource


class LineageHandler:
    __repository = LineageRepository(engine)
    __artifact_repository = ArtifactRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __user_repository = UserRepository(engine)
    __permissions_handler = PermissionsHandler()

    @staticmethod
    def _creation_via(auth_scopes: Sequence[str]) -> LineageVia:
        if "api_key" in auth_scopes:
            return LineageVia.API
        return LineageVia.UI

    @staticmethod
    def _artifact_ids(refs: Iterable[LineageNodeRef]) -> list[UUID]:
        return list(
            dict.fromkeys(
                ref.artifact_id for ref in refs if ref.artifact_id is not None
            )
        )

    @staticmethod
    def _node_ids(refs: Iterable[LineageNodeRef]) -> list[UUID]:
        return list(
            dict.fromkeys(ref.node_id for ref in refs if ref.node_id is not None)
        )

    @staticmethod
    def _resolve_node_reference(
        ref: LineageNodeRef,
        nodes_by_id: dict[UUID, LineageNodeOrm],
        nodes_by_artifact_id: dict[UUID, LineageNodeOrm],
    ) -> UUID:
        if ref.node_id is not None:
            return nodes_by_id[ref.node_id].id
        if ref.artifact_id is None:
            raise RuntimeError("Validated lineage reference has no identifier")
        return nodes_by_artifact_id[ref.artifact_id].id

    @staticmethod
    def _find_node(
        ref: LineageNodeRef,
        nodes_by_id: dict[UUID, LineageNodeOrm],
        nodes_by_artifact_id: dict[UUID, LineageNodeOrm],
    ) -> LineageNodeOrm | None:
        if ref.node_id is not None:
            return nodes_by_id.get(ref.node_id)
        if ref.artifact_id is not None:
            return nodes_by_artifact_id.get(ref.artifact_id)
        return None

    @staticmethod
    def _dedupe_pairs(node_pairs: Iterable[LineageNodePair]) -> list[LineageNodePair]:
        resolved: list[LineageNodePair] = []
        seen: set[LineageNodePair] = set()
        for source, target in node_pairs:
            if source == target:
                raise ApplicationError(
                    "Artifact cannot be linked to itself",
                    status.HTTP_400_BAD_REQUEST,
                )
            if (source, target) in seen:
                continue
            if (target, source) in seen:
                raise ApplicationError(
                    "Reverse lineage connection already exists",
                    status.HTTP_409_CONFLICT,
                )
            seen.add((source, target))
            resolved.append((source, target))
        return resolved

    @staticmethod
    def _check_existing_pairs(
        node_pairs: Iterable[LineageNodePair],
        existing_edges: Iterable[LineageEdgeOrm],
    ) -> None:
        existing_pairs = {
            (edge.source_node_id, edge.target_node_id) for edge in existing_edges
        }
        for source, target in node_pairs:
            if (source, target) in existing_pairs:
                raise ApplicationError(
                    "Lineage connection already exists",
                    status.HTTP_409_CONFLICT,
                )
            if (target, source) in existing_pairs:
                raise ApplicationError(
                    "Reverse lineage connection already exists",
                    status.HTTP_409_CONFLICT,
                )

    @staticmethod
    def _build_lineage_node(
        node: LineageNodeOrm, data: ArtifactListed | None
    ) -> LineageNode:
        return LineageNode(
            id=node.id,
            artifact_id=node.artifact_id,
            type=data.type.value if data else node.type,
            name=(data.name or node.name) if data else node.name,
            collection_name=data.collection_name if data else node.collection_name,
            x=node.x,
            y=node.y,
            is_deleted=node.artifact_id is None,
            data=data,
        )

    async def _apply_batch(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        changes: LineageBatchIn,
        auth_scopes: Sequence[str],
        *,
        check_access: bool,
    ) -> LineageBatchResult:
        if check_access:
            await self._check_access(user_id, organization_id, orbit_id, Action.UPDATE)
        return await self._apply_changes(
            user_id, orbit_id, changes, self._creation_via(auth_scopes)
        )

    async def _apply_changes(
        self,
        user_id: UUID,
        orbit_id: UUID,
        changes: LineageBatchIn,
        via: LineageVia,
    ) -> LineageBatchResult:
        created_by_user = (
            await self._get_created_by_user(user_id) if changes.create else ""
        )

        async with self.__repository.transaction() as session:
            deleted, touched_node_ids = await self._delete_edges(
                orbit_id, changes.delete, session
            )
            created = await self._create_edges(
                orbit_id, changes.create, created_by_user, via, session
            )
            await self._update_positions(orbit_id, changes.positions, session)
            if touched_node_ids:
                await self.__repository.delete_edgeless_nodes(
                    orbit_id, session, touched_node_ids
                )

            return LineageBatchResult(created=created, deleted=deleted)

    async def _delete_edges(
        self,
        orbit_id: UUID,
        edge_ids: list[UUID],
        session: AsyncSession,
    ) -> tuple[list[LineageEdge], list[UUID]]:
        delete_ids = list(dict.fromkeys(edge_ids))
        if not delete_ids:
            return [], []

        edges = await self._get_edges(orbit_id, delete_ids, session)
        deleted = [edge.to_edge() for edge in edges]
        touched_node_ids = list(
            dict.fromkeys(
                node_id
                for edge in edges
                for node_id in (edge.source_node_id, edge.target_node_id)
            )
        )
        await self.__repository.delete_edges(orbit_id, delete_ids, session)
        return deleted, touched_node_ids

    async def _create_edges(
        self,
        orbit_id: UUID,
        pairs: list[LineagePair],
        created_by_user: str,
        via: LineageVia,
        session: AsyncSession,
    ) -> list[LineageEdge]:
        if not pairs:
            return []

        node_pairs = await self._resolve_creation_pairs(orbit_id, pairs, session)

        existing_edges = await self.__repository.get_edges_by_pairs(
            orbit_id, node_pairs, session
        )
        self._check_existing_pairs(node_pairs, existing_edges)

        try:
            edges = await self.__repository.create_edges(
                orbit_id, node_pairs, created_by_user, via, session
            )
        except IntegrityError as error:
            raise ApplicationError(
                "Lineage connection already exists",
                status.HTTP_409_CONFLICT,
            ) from error
        return [edge.to_edge() for edge in edges]

    async def _update_positions(
        self,
        orbit_id: UUID,
        positions: list[LineagePosition],
        session: AsyncSession,
    ) -> None:
        if not positions:
            return

        resolved = await self._resolve_positions(orbit_id, positions, session)

        await self.__repository.update_positions(orbit_id, resolved, session)

    async def _resolve_creation_pairs(
        self,
        orbit_id: UUID,
        pairs: list[LineagePair],
        session: AsyncSession,
    ) -> list[LineageNodePair]:
        refs = [ref for pair in pairs for ref in (pair.source, pair.target)]

        artifacts_by_id = await self._get_artifacts(
            orbit_id, self._artifact_ids(refs), session
        )

        nodes_by_id = await self._get_nodes(orbit_id, self._node_ids(refs), session)
        nodes_by_artifact_id = await self._get_or_create_nodes(
            orbit_id, artifacts_by_id, session
        )
        return self._dedupe_pairs(
            (
                self._resolve_node_reference(
                    pair.source, nodes_by_id, nodes_by_artifact_id
                ),
                self._resolve_node_reference(
                    pair.target, nodes_by_id, nodes_by_artifact_id
                ),
            )
            for pair in pairs
        )

    async def _resolve_positions(
        self,
        orbit_id: UUID,
        positions: list[LineagePosition],
        session: AsyncSession,
    ) -> dict[UUID, LineageCoordinates]:
        refs = [position.ref for position in positions]
        artifact_nodes = await self.__repository.get_nodes_by_artifact_ids(
            orbit_id, self._artifact_ids(refs), session
        )

        nodes = await self.__repository.get_nodes_by_ids(
            orbit_id, self._node_ids(refs), session
        )

        nodes_by_id = {node.id: node for node in nodes}
        nodes_by_artifact_id = {
            node.artifact_id: node
            for node in artifact_nodes
            if node.artifact_id is not None
        }

        resolved: dict[UUID, LineageCoordinates] = {}

        for position in positions:
            node = self._find_node(position.ref, nodes_by_id, nodes_by_artifact_id)
            if node is not None:
                resolved[node.id] = (position.x, position.y)

        return resolved

    async def _get_artifacts(
        self,
        orbit_id: UUID,
        artifact_ids: list[UUID],
        session: AsyncSession | None = None,
    ) -> dict[UUID, ArtifactListed]:
        artifacts = await self.__artifact_repository.get_artifacts_by_ids_in_orbit(
            orbit_id, artifact_ids, session
        )

        artifacts_by_id = {artifact.id: artifact for artifact in artifacts}

        if set(artifacts_by_id) != set(artifact_ids):
            raise ArtifactNotFoundError()

        return artifacts_by_id

    async def _get_live_artifacts(
        self, orbit_id: UUID, nodes: Sequence[LineageNodeOrm]
    ) -> dict[UUID, ArtifactListed]:
        live_artifact_ids = [
            node.artifact_id for node in nodes if node.artifact_id is not None
        ]
        artifacts = await self.__artifact_repository.get_artifacts_by_ids_in_orbit(
            orbit_id, live_artifact_ids
        )
        return {artifact.id: artifact for artifact in artifacts}

    async def _get_nodes(
        self,
        orbit_id: UUID,
        node_ids: list[UUID],
        session: AsyncSession,
    ) -> dict[UUID, LineageNodeOrm]:
        nodes = await self.__repository.get_nodes_by_ids(orbit_id, node_ids, session)
        nodes_by_id = {node.id: node for node in nodes}

        if set(nodes_by_id) != set(node_ids):
            raise NotFoundError("Lineage node not found")

        return nodes_by_id

    async def _get_or_create_nodes(
        self,
        orbit_id: UUID,
        artifacts_by_id: dict[UUID, ArtifactListed],
        session: AsyncSession,
    ) -> dict[UUID, LineageNodeOrm]:
        nodes: dict[UUID, LineageNodeOrm] = {}

        for artifact_id in sorted(artifacts_by_id):
            nodes[artifact_id] = await self.__repository.get_or_create_node(
                orbit_id, artifacts_by_id[artifact_id], session
            )

        return nodes

    async def _get_edges(
        self,
        orbit_id: UUID,
        edge_ids: list[UUID],
        session: AsyncSession,
    ) -> list[LineageEdgeOrm]:
        edges = await self.__repository.get_edges_by_ids(orbit_id, edge_ids, session)

        if {edge.id for edge in edges} != set(edge_ids):
            raise NotFoundError("Lineage connection not found")

        return edges

    async def _check_access(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        action: Action,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            action,
            orbit_id,
        )

        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )

        if not orbit:
            raise OrbitNotFoundError()

    async def _get_created_by_user(self, user_id: UUID) -> str:
        user = await self.__user_repository.get_public_user_by_id(user_id)

        if not user:
            raise NotFoundError("User not found")

        return str(user.full_name or user.email)

    async def apply_changes(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        changes: LineageBatchIn,
        auth_scopes: Sequence[str],
    ) -> LineageBatchResult:
        return await self._apply_batch(
            user_id, organization_id, orbit_id, changes, auth_scopes, check_access=True
        )

    async def create_links(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        source_artifact_id: UUID,
        target_artifact_ids: list[UUID],
        auth_scopes: Sequence[str],
        *,
        check_access: bool = True,
    ) -> list[LineageEdge]:
        changes = LineageBatchIn(
            create=[
                LineagePair(
                    source=LineageNodeRef(artifact_id=source_artifact_id),
                    target=LineageNodeRef(artifact_id=target_artifact_id),
                )
                for target_artifact_id in target_artifact_ids
            ]
        )
        result = await self._apply_batch(
            user_id,
            organization_id,
            orbit_id,
            changes,
            auth_scopes,
            check_access=check_access,
        )
        return result.created

    async def link_inputs(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        artifact_id: UUID,
        input_artifact_ids: list[UUID],
        auth_scopes: Sequence[str],
        *,
        check_access: bool = True,
    ) -> list[LineageEdge]:
        changes = LineageBatchIn(
            create=[
                LineagePair(
                    source=LineageNodeRef(artifact_id=input_artifact_id),
                    target=LineageNodeRef(artifact_id=artifact_id),
                )
                for input_artifact_id in dict.fromkeys(input_artifact_ids)
            ]
        )

        if not changes.create:
            return []

        result = await self._apply_batch(
            user_id,
            organization_id,
            orbit_id,
            changes,
            auth_scopes,
            check_access=check_access,
        )

        return result.created

    async def delete_link(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        artifact_id: UUID,
        edge_id: UUID,
        auth_scopes: Sequence[str],
    ) -> LineageEdge:
        await self._check_access(user_id, organization_id, orbit_id, Action.UPDATE)
        await self._get_artifacts(orbit_id, [artifact_id])

        node = await self.__repository.get_node_by_artifact_id(orbit_id, artifact_id)
        edges = await self.__repository.get_edges_by_ids(orbit_id, [edge_id])

        if (
            node is None
            or not edges
            or node.id not in (edges[0].source_node_id, edges[0].target_node_id)
        ):
            raise NotFoundError("Lineage connection not found")

        result = await self._apply_changes(
            user_id,
            orbit_id,
            LineageBatchIn(delete=[edge_id]),
            self._creation_via(auth_scopes),
        )

        return result.deleted[0]

    async def get_graph(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        artifact_id: UUID,
        depth: int | None,
    ) -> LineageGraph:
        await self._check_access(user_id, organization_id, orbit_id, Action.READ)
        await self._get_artifacts(orbit_id, [artifact_id])

        focal_node = await self.__repository.get_node_by_artifact_id(
            orbit_id, artifact_id
        )

        if focal_node is None:
            return LineageGraph(
                nodes=[],
                edges=[],
                focal_artifact_id=artifact_id,
                depth=depth,
                truncated=False,
            )

        nodes, edges, truncated = await self.__repository.traverse(
            orbit_id, focal_node.id, depth
        )
        artifacts_by_id = await self._get_live_artifacts(orbit_id, nodes)

        lineage_nodes = [
            self._build_lineage_node(
                node,
                artifacts_by_id.get(node.artifact_id)
                if node.artifact_id is not None
                else None,
            )
            for node in nodes
        ]

        return LineageGraph(
            nodes=lineage_nodes,
            edges=[edge.to_edge() for edge in edges],
            focal_artifact_id=artifact_id,
            depth=depth,
            truncated=truncated,
        )
