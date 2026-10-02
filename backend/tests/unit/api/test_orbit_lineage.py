from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from luml.api.organization_routes import organization_all_routers
from luml.infra.exceptions import ApplicationError
from luml.schemas.lineage import (
    LineageBatchIn,
    LineageBatchResult,
    LineageEdge,
    LineageGraph,
    LineageNode,
    LineageVia,
)

from tests.support.auth import API_KEY_USER, SIGNED_IN_USER
from tests.support.ids import ARTIFACT_ID, ORBIT_ID, ORGANIZATION_ID, USER_ID

ARTIFACT_B_ID = UUID("0199c337-09fb-72eb-a8c8-77e55d873463")
NODE_A_ID = UUID("0199c337-0a01-7d9f-9cd8-ee95ab3c4bd1")
NODE_B_ID = UUID("0199c337-0a02-7c1e-8a3b-3f0e1a6d95c4")
EDGE_ID = UUID("0199c337-0a05-7cb3-8d16-c40ab75581b9")
CREATED_AT = datetime(2026, 9, 3, tzinfo=UTC)
ARTIFACT_PATH = (
    f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}"
    f"/artifacts/{ARTIFACT_ID}/lineage"
)
BATCH_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/lineage/batch"


def _edge(via: LineageVia = LineageVia.API) -> LineageEdge:
    return LineageEdge(
        id=EDGE_ID,
        source=NODE_A_ID,
        target=NODE_B_ID,
        created_by_user="Lineage User",
        created_via=via,
        created_at=CREATED_AT,
    )


def _graph(depth: int | None) -> LineageGraph:
    return LineageGraph(
        nodes=[
            LineageNode(
                id=NODE_B_ID,
                artifact_id=None,
                type="dataset",
                name="Deleted dataset",
                collection_name="Datasets",
                x=-320.0,
                y=0.0,
                is_deleted=True,
                data=None,
            )
        ],
        edges=[_edge()],
        focal_artifact_id=ARTIFACT_ID,
        depth=depth,
        truncated=False,
    )


class TestOrbitLineage:
    @pytest.mark.parametrize(
        ("query", "depth"), [("", None), ("?depth=3", 3), ("?depth=6", 6)]
    )
    @patch(
        "luml.handlers.lineage.LineageHandler.get_graph",
        new_callable=AsyncMock,
    )
    def test_get_lineage_uses_default_or_requested_depth(
        self,
        mock_get_graph: AsyncMock,
        query: str,
        depth: int | None,
        client: TestClient,
    ) -> None:
        mock_get_graph.return_value = _graph(depth)

        response = client.get(f"{ARTIFACT_PATH}{query}")

        assert response.status_code == 200
        assert response.json()["depth"] == depth
        assert response.json()["nodes"][0]["data"] is None
        mock_get_graph.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_ID,
            depth,
        )

    @pytest.mark.parametrize("depth", [0, -1])
    @patch(
        "luml.handlers.lineage.LineageHandler.get_graph",
        new_callable=AsyncMock,
    )
    def test_get_lineage_rejects_depth_outside_bounds(
        self, mock_get_graph: AsyncMock, depth: int, client: TestClient
    ) -> None:
        response = client.get(ARTIFACT_PATH, params={"depth": depth})

        assert response.status_code == 422
        mock_get_graph.assert_not_awaited()

    @pytest.mark.parametrize(
        ("principal", "scope", "via"),
        [
            (SIGNED_IN_USER, "jwt", LineageVia.UI),
            (API_KEY_USER, "api_key", LineageVia.API),
        ],
        ids=["jwt", "api_key"],
        indirect=["principal"],
    )
    @patch(
        "luml.handlers.lineage.LineageHandler.create_links",
        new_callable=AsyncMock,
    )
    def test_create_lineage_forwards_auth_scopes(
        self,
        mock_create_links: AsyncMock,
        scope: str,
        via: LineageVia,
        client: TestClient,
    ) -> None:
        mock_create_links.return_value = [_edge(via)]

        response = client.post(
            ARTIFACT_PATH,
            json={"target_artifact_ids": [str(ARTIFACT_B_ID), str(ARTIFACT_B_ID)]},
        )

        assert response.status_code == 200
        assert response.json()[0]["created_via"] == via.value
        mock_create_links.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_ID,
            [ARTIFACT_B_ID, ARTIFACT_B_ID],
            ["authenticated", scope],
        )

    @patch(
        "luml.handlers.lineage.LineageHandler.delete_link",
        new_callable=AsyncMock,
    )
    def test_delete_lineage_forwards_artifact_and_edge_ids(
        self, mock_delete_link: AsyncMock, client: TestClient
    ) -> None:
        mock_delete_link.return_value = _edge(LineageVia.UI)

        response = client.delete(f"{ARTIFACT_PATH}/{EDGE_ID}")

        assert response.status_code == 200
        assert response.json()["id"] == str(EDGE_ID)
        mock_delete_link.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            ARTIFACT_ID,
            EDGE_ID,
            ["authenticated", "jwt"],
        )

    @pytest.mark.parametrize(
        ("principal", "scope", "via"),
        [
            (SIGNED_IN_USER, "jwt", LineageVia.UI),
            (API_KEY_USER, "api_key", LineageVia.API),
        ],
        ids=["jwt", "api_key"],
        indirect=["principal"],
    )
    @patch(
        "luml.handlers.lineage.LineageHandler.apply_changes",
        new_callable=AsyncMock,
    )
    def test_batch_parses_changes_and_forwards_auth_scopes(
        self,
        mock_apply_changes: AsyncMock,
        scope: str,
        via: LineageVia,
        client: TestClient,
    ) -> None:
        body = {
            "create": [
                {
                    "source": {"artifact_id": str(ARTIFACT_ID)},
                    "target": {"node_id": str(NODE_B_ID)},
                }
            ],
            "delete": [str(EDGE_ID)],
            "positions": [
                {
                    "ref": {"node_id": str(NODE_A_ID)},
                    "x": 10.0,
                    "y": 20.0,
                }
            ],
        }
        mock_apply_changes.return_value = LineageBatchResult(
            created=[_edge(via)], deleted=[]
        )

        response = client.post(BATCH_PATH, json=body)

        assert response.status_code == 200
        mock_apply_changes.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LineageBatchIn.model_validate(body),
            ["authenticated", scope],
        )

    @pytest.mark.parametrize(
        "reference",
        [
            {},
            {"artifact_id": str(ARTIFACT_ID), "node_id": str(NODE_A_ID)},
        ],
    )
    @patch(
        "luml.handlers.lineage.LineageHandler.apply_changes",
        new_callable=AsyncMock,
    )
    def test_batch_rejects_an_ambiguous_node_reference(
        self,
        mock_apply_changes: AsyncMock,
        reference: dict[str, str],
        client: TestClient,
    ) -> None:
        response = client.post(
            BATCH_PATH,
            json={
                "create": [
                    {
                        "source": reference,
                        "target": {"artifact_id": str(ARTIFACT_B_ID)},
                    }
                ]
            },
        )

        assert response.status_code == 422
        mock_apply_changes.assert_not_awaited()

    @pytest.mark.parametrize(
        ("status_code", "message"),
        [
            (404, "Artifact not found"),
            (409, "Lineage connection already exists"),
            (403, "Not enough rights"),
        ],
    )
    @patch(
        "luml.handlers.lineage.LineageHandler.create_links",
        new_callable=AsyncMock,
    )
    def test_lineage_errors_use_the_standard_detail_response(
        self,
        mock_create_links: AsyncMock,
        status_code: int,
        message: str,
        client: TestClient,
    ) -> None:
        mock_create_links.side_effect = ApplicationError(message, status_code)

        response = client.post(
            ARTIFACT_PATH,
            json={"target_artifact_ids": [str(ARTIFACT_B_ID)]},
        )

        assert response.status_code == status_code
        assert response.json() == {"detail": message}

    def test_lineage_router_is_registered_for_organizations(self) -> None:
        paths = {
            route.path
            for route in organization_all_routers.routes
            if isinstance(route, APIRoute)
        }

        assert (
            "/organizations/{organization_id}/orbits/{orbit_id}"
            "/artifacts/{artifact_id}/lineage"
        ) in paths
        assert (
            "/organizations/{organization_id}/orbits/{orbit_id}/lineage/batch"
        ) in paths

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    @patch(
        "luml.handlers.lineage.LineageHandler.apply_changes",
        new_callable=AsyncMock,
    )
    def test_batch_rejects_non_finite_positions(
        self, mock_apply_changes: AsyncMock, value: str, client: TestClient
    ) -> None:
        body = (
            '{"positions": [{"ref": {"node_id": "'
            + str(NODE_A_ID)
            + '"}, "x": '
            + value
            + ', "y": 0}]}'
        )

        response = client.post(
            BATCH_PATH, content=body, headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422
        assert response.json()["detail"][0]["msg"] == "Input should be a finite number"
        mock_apply_changes.assert_not_awaited()

    @patch(
        "luml.handlers.lineage.LineageHandler.create_links",
        new_callable=AsyncMock,
    )
    def test_create_lineage_requires_at_least_one_target(
        self, mock_create_links: AsyncMock, client: TestClient
    ) -> None:
        response = client.post(ARTIFACT_PATH, json={"target_artifact_ids": []})

        assert response.status_code == 422
        mock_create_links.assert_not_awaited()

    @pytest.mark.parametrize(
        ("path", "body"),
        [
            (BATCH_PATH, {"delete": [str(EDGE_ID)] * 1001}),
            (
                BATCH_PATH,
                {
                    "positions": [{"ref": {"node_id": str(NODE_A_ID)}, "x": 0, "y": 0}]
                    * 1001
                },
            ),
            (ARTIFACT_PATH, {"target_artifact_ids": [str(ARTIFACT_B_ID)] * 1001}),
        ],
        ids=["delete", "positions", "targets"],
    )
    @patch(
        "luml.handlers.lineage.LineageHandler.create_links",
        new_callable=AsyncMock,
    )
    @patch(
        "luml.handlers.lineage.LineageHandler.apply_changes",
        new_callable=AsyncMock,
    )
    def test_oversized_payloads_are_rejected(
        self,
        mock_apply_changes: AsyncMock,
        mock_create_links: AsyncMock,
        path: str,
        body: dict[str, object],
        client: TestClient,
    ) -> None:
        response = client.post(path, json=body)

        assert response.status_code == 422
        mock_apply_changes.assert_not_awaited()
        mock_create_links.assert_not_awaited()
