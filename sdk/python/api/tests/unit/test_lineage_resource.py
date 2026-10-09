from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import ConflictError, NotFoundError, PermissionDeniedError
from luml_api._types import Artifact, LineageEdge, LineageGraph
from tests.conftest import TEST_BASE_URL

ARTIFACT_ID = "0199c455-21ee-74c6-b747-19a82f1a1e67"
TARGET_ID = "0199c455-21ee-74c6-b747-19a82f1a1e68"
SECOND_TARGET_ID = "0199c455-21ee-74c6-b747-19a82f1a1e69"
NODE_ID = "0199c455-21ee-74c6-b747-19a82f1a1e70"
TARGET_NODE_ID = "0199c455-21ee-74c6-b747-19a82f1a1e71"
EDGE_ID = "0199c455-21ee-74c6-b747-19a82f1a1e72"


def _edge_json() -> dict[str, object]:
    return {
        "id": EDGE_ID,
        "source": NODE_ID,
        "target": TARGET_NODE_ID,
        "created_by_user": "Ada Lovelace",
        "created_via": "api",
        "created_at": "2026-09-03T12:00:00Z",
    }


def _graph_json(artifact: Artifact) -> dict[str, object]:
    live_artifact = artifact.model_dump(mode="json") | {
        "id": ARTIFACT_ID,
        "created_by_user": "Ada Lovelace",
        "collection_name": "models",
        "deployments": [
            {
                "id": "0199c455-21ee-74c6-b747-19a82f1a1e73",
                "name": "production",
                "status": "active",
                "orbit_id": "0199c455-21ed-7aba-9fe5-5231611220de",
            }
        ],
    }
    return {
        "nodes": [
            {
                "id": NODE_ID,
                "artifact_id": None,
                "type": "dataset",
                "name": "deleted-dataset",
                "collection_name": "training-data",
                "x": -320.0,
                "y": 0.0,
                "is_deleted": True,
                "data": None,
            },
            {
                "id": TARGET_NODE_ID,
                "artifact_id": ARTIFACT_ID,
                "type": "model",
                "name": artifact.name,
                "collection_name": "models",
                "x": 0.0,
                "y": 0.0,
                "is_deleted": False,
                "data": live_artifact,
            },
        ],
        "edges": [_edge_json()],
        "focal_artifact_id": ARTIFACT_ID,
        "depth": 3,
        "truncated": False,
    }


def _created_artifact_json(artifact: Artifact) -> dict[str, object]:
    return {
        "upload_details": {
            "type": "s3",
            "url": "https://storage.example/upload",
            "multipart": False,
            "bucket_location": "test/location",
            "bucket_secret_id": "0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        },
        "artifact": artifact.model_dump(mode="json"),
    }


def _artifact_details() -> Mock:
    return Mock(
        file_name="model.fnnx",
        extra_values={},
        manifest={},
        file_hash="abc123",
        file_index={},
        size=1024,
    )


def _call_lineage_operation(client: LumlClient, operation: str) -> object:
    if operation == "get":
        return client.artifacts.get_lineage(ARTIFACT_ID)
    if operation == "create":
        return client.artifacts.log_lineage(ARTIFACT_ID, [TARGET_ID])
    return client.artifacts.remove_lineage(ARTIFACT_ID, EDGE_ID)


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_lineage_methods(
    client_with_mocks: LumlClient,
    sample_artifact: Artifact,
    respx_mock: MockRouter,
) -> None:
    base_path = (
        f"/v1/organizations/{client_with_mocks.organization}"
        f"/orbits/{client_with_mocks.orbit}/artifacts"
    )
    get_route = respx_mock.get(f"{base_path}/{ARTIFACT_ID}/lineage").mock(
        return_value=httpx.Response(200, json=_graph_json(sample_artifact))
    )
    create_route = respx_mock.post(f"{base_path}/{ARTIFACT_ID}/lineage").mock(
        return_value=httpx.Response(200, json=[_edge_json()])
    )
    delete_route = respx_mock.delete(
        f"{base_path}/{ARTIFACT_ID}/lineage/{EDGE_ID}"
    ).mock(return_value=httpx.Response(200, json=_edge_json()))

    whole_graph = client_with_mocks.artifacts.get_lineage(ARTIFACT_ID)
    graph = client_with_mocks.artifacts.get_lineage(ARTIFACT_ID, depth=3)
    created = client_with_mocks.artifacts.log_lineage(
        ARTIFACT_ID, [TARGET_ID, SECOND_TARGET_ID]
    )
    removed = client_with_mocks.artifacts.remove_lineage(ARTIFACT_ID, EDGE_ID)

    assert isinstance(graph, LineageGraph)
    assert isinstance(whole_graph, LineageGraph)
    assert graph.nodes[0].data is None
    assert graph.nodes[1].data is not None
    assert graph.nodes[1].data.collection_name == "models"
    assert graph.nodes[1].data.deployments[0].name == "production"
    assert "depth" not in get_route.calls[0].request.url.params
    assert get_route.calls.last.request.url.params["depth"] == "3"
    assert all(isinstance(edge, LineageEdge) for edge in created)
    assert create_route.calls.last.request.read() == (
        b'{"target_artifact_ids":["0199c455-21ee-74c6-b747-19a82f1a1e68",'
        b'"0199c455-21ee-74c6-b747-19a82f1a1e69"]}'
    )
    assert isinstance(removed, LineageEdge)
    assert delete_route.called


@pytest.mark.asyncio
@pytest.mark.respx(base_url=TEST_BASE_URL)
async def test_async_lineage_methods(
    async_client_with_mocks: AsyncLumlClient,
    sample_artifact: Artifact,
    respx_mock: MockRouter,
) -> None:
    base_path = (
        f"/v1/organizations/{async_client_with_mocks.organization}"
        f"/orbits/{async_client_with_mocks.orbit}/artifacts"
    )
    get_route = respx_mock.get(f"{base_path}/{ARTIFACT_ID}/lineage").mock(
        return_value=httpx.Response(200, json=_graph_json(sample_artifact))
    )
    create_route = respx_mock.post(f"{base_path}/{ARTIFACT_ID}/lineage").mock(
        return_value=httpx.Response(200, json=[_edge_json()])
    )
    delete_route = respx_mock.delete(
        f"{base_path}/{ARTIFACT_ID}/lineage/{EDGE_ID}"
    ).mock(return_value=httpx.Response(200, json=_edge_json()))

    graph = await async_client_with_mocks.artifacts.get_lineage(ARTIFACT_ID, depth=3)
    created = await async_client_with_mocks.artifacts.log_lineage(
        ARTIFACT_ID, [TARGET_ID, SECOND_TARGET_ID]
    )
    removed = await async_client_with_mocks.artifacts.remove_lineage(
        ARTIFACT_ID, EDGE_ID
    )

    assert isinstance(graph, LineageGraph)
    assert graph.nodes[0].data is None
    assert graph.nodes[1].data is not None
    assert graph.nodes[1].data.collection_name == "models"
    assert graph.nodes[1].data.deployments[0].name == "production"
    assert get_route.calls.last.request.url.params["depth"] == "3"
    assert all(isinstance(edge, LineageEdge) for edge in created)
    assert create_route.calls.last.request.read() == (
        b'{"target_artifact_ids":["0199c455-21ee-74c6-b747-19a82f1a1e68",'
        b'"0199c455-21ee-74c6-b747-19a82f1a1e69"]}'
    )
    assert isinstance(removed, LineageEdge)
    assert delete_route.called


@pytest.mark.parametrize(
    ("status_code", "exception_type"),
    [
        (403, PermissionDeniedError),
        (404, NotFoundError),
        (409, ConflictError),
    ],
)
@pytest.mark.parametrize("operation", ["get", "create", "delete"])
@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_lineage_errors_are_translated(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
    status_code: int,
    exception_type: type[Exception],
    operation: str,
) -> None:
    base_path = (
        f"/v1/organizations/{client_with_mocks.organization}"
        f"/orbits/{client_with_mocks.orbit}/artifacts/{ARTIFACT_ID}/lineage"
    )
    if operation == "get":
        route = respx_mock.get(base_path)
    elif operation == "create":
        route = respx_mock.post(base_path)
    else:
        route = respx_mock.delete(f"{base_path}/{EDGE_ID}")
    route.mock(
        return_value=httpx.Response(status_code, json={"detail": "lineage error"})
    )

    with pytest.raises(exception_type):
        _call_lineage_operation(client_with_mocks, operation)


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_upload_sends_lineage_inputs_and_omits_none(
    client_with_mocks: LumlClient,
    sample_artifact: Artifact,
    respx_mock: MockRouter,
) -> None:
    collection_id = client_with_mocks.collection
    create_route = respx_mock.post(
        f"/v1/organizations/{client_with_mocks.organization}"
        f"/orbits/{client_with_mocks.orbit}/collections/{collection_id}/artifacts"
    ).mock(
        return_value=httpx.Response(200, json=_created_artifact_json(sample_artifact))
    )
    respx_mock.patch(
        f"/v1/organizations/{client_with_mocks.organization}"
        f"/orbits/{client_with_mocks.orbit}/collections/{collection_id}"
        f"/artifacts/{sample_artifact.id}"
    ).mock(
        return_value=httpx.Response(200, json=sample_artifact.model_dump(mode="json"))
    )

    with (
        patch("luml_api.resources.artifacts.ModelFileHandler") as file_handler,
        patch("luml_api.resources.artifacts.UploadService") as upload_service,
    ):
        file_handler.return_value.artifact_details.return_value = _artifact_details()
        upload_service.return_value.upload_file.return_value = Mock(status_code=200)

        client_with_mocks.artifacts.upload("model.fnnx", lineage_inputs=[TARGET_ID])
        client_with_mocks.artifacts.upload("model.fnnx")

    first_body = create_route.calls[0].request.content
    second_body = create_route.calls[1].request.content
    assert b'"lineage_inputs":["0199c455-21ee-74c6-b747-19a82f1a1e68"]' in first_body
    assert b'"lineage_inputs"' not in second_body


@pytest.mark.asyncio
@pytest.mark.respx(base_url=TEST_BASE_URL)
async def test_async_upload_sends_lineage_inputs_and_omits_none(
    async_client_with_mocks: AsyncLumlClient,
    sample_artifact: Artifact,
    respx_mock: MockRouter,
) -> None:
    collection_id = async_client_with_mocks.collection
    create_route = respx_mock.post(
        f"/v1/organizations/{async_client_with_mocks.organization}"
        f"/orbits/{async_client_with_mocks.orbit}/collections/{collection_id}/artifacts"
    ).mock(
        return_value=httpx.Response(200, json=_created_artifact_json(sample_artifact))
    )
    respx_mock.patch(
        f"/v1/organizations/{async_client_with_mocks.organization}"
        f"/orbits/{async_client_with_mocks.orbit}/collections/{collection_id}"
        f"/artifacts/{sample_artifact.id}"
    ).mock(
        return_value=httpx.Response(200, json=sample_artifact.model_dump(mode="json"))
    )

    with (
        patch("luml_api.resources.artifacts.ModelFileHandler") as file_handler,
        patch("luml_api.resources.artifacts.AsyncUploadService") as upload_service,
    ):
        file_handler.return_value.artifact_details.return_value = _artifact_details()
        upload_service.return_value.upload_file = AsyncMock(
            return_value=Mock(status_code=200)
        )

        await async_client_with_mocks.artifacts.upload(
            "model.fnnx", lineage_inputs=[TARGET_ID]
        )
        await async_client_with_mocks.artifacts.upload("model.fnnx")

    first_body = create_route.calls[0].request.content
    second_body = create_route.calls[1].request.content
    assert b'"lineage_inputs":["0199c455-21ee-74c6-b747-19a82f1a1e68"]' in first_body
    assert b'"lineage_inputs"' not in second_body


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_rejected_lineage_input_does_not_start_storage_upload(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
) -> None:
    respx_mock.post(
        f"/v1/organizations/{client_with_mocks.organization}"
        f"/orbits/{client_with_mocks.orbit}"
        f"/collections/{client_with_mocks.collection}/artifacts"
    ).mock(return_value=httpx.Response(404, json={"detail": "Artifact not found"}))

    with (
        patch("luml_api.resources.artifacts.ModelFileHandler") as file_handler,
        patch("luml_api.resources.artifacts.UploadService") as upload_service,
    ):
        file_handler.return_value.artifact_details.return_value = _artifact_details()

        with pytest.raises(NotFoundError):
            client_with_mocks.artifacts.upload("model.fnnx", lineage_inputs=[TARGET_ID])

        upload_service.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.respx(base_url=TEST_BASE_URL)
async def test_async_rejected_lineage_input_does_not_start_storage_upload(
    async_client_with_mocks: AsyncLumlClient,
    respx_mock: MockRouter,
) -> None:
    respx_mock.post(
        f"/v1/organizations/{async_client_with_mocks.organization}"
        f"/orbits/{async_client_with_mocks.orbit}"
        f"/collections/{async_client_with_mocks.collection}/artifacts"
    ).mock(return_value=httpx.Response(404, json={"detail": "Artifact not found"}))

    with (
        patch("luml_api.resources.artifacts.ModelFileHandler") as file_handler,
        patch("luml_api.resources.artifacts.AsyncUploadService") as upload_service,
    ):
        file_handler.return_value.artifact_details.return_value = _artifact_details()

        with pytest.raises(NotFoundError):
            await async_client_with_mocks.artifacts.upload(
                "model.fnnx", lineage_inputs=[TARGET_ID]
            )

        upload_service.assert_not_called()


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_log_lineage_inputs_uses_one_batch(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
) -> None:
    batch_route = respx_mock.post(
        f"/v1/organizations/{client_with_mocks.organization}"
        f"/orbits/{client_with_mocks.orbit}/lineage/batch"
    ).mock(
        return_value=httpx.Response(
            200, json={"created": [_edge_json(), _edge_json()], "deleted": []}
        )
    )

    created = client_with_mocks.artifacts.log_lineage_inputs(
        ARTIFACT_ID, [TARGET_ID, SECOND_TARGET_ID]
    )

    assert len(created) == 2
    assert all(isinstance(edge, LineageEdge) for edge in created)
    assert batch_route.calls.last.request.read() == (
        b'{"create":[{"source":{"artifact_id":"' + TARGET_ID.encode() + b'"},'
        b'"target":{"artifact_id":"' + ARTIFACT_ID.encode() + b'"}},'
        b'{"source":{"artifact_id":"' + SECOND_TARGET_ID.encode() + b'"},'
        b'"target":{"artifact_id":"' + ARTIFACT_ID.encode() + b'"}}]}'
    )


@pytest.mark.asyncio
@pytest.mark.respx(base_url=TEST_BASE_URL)
async def test_async_log_lineage_inputs_uses_one_batch(
    async_client_with_mocks: AsyncLumlClient,
    respx_mock: MockRouter,
) -> None:
    batch_route = respx_mock.post(
        f"/v1/organizations/{async_client_with_mocks.organization}"
        f"/orbits/{async_client_with_mocks.orbit}/lineage/batch"
    ).mock(
        return_value=httpx.Response(
            200, json={"created": [_edge_json()], "deleted": []}
        )
    )

    created = await async_client_with_mocks.artifacts.log_lineage_inputs(
        ARTIFACT_ID, [TARGET_ID]
    )

    assert [edge.id for edge in created] == [EDGE_ID]
    assert batch_route.called
