"""Deployments and their monitoring, reached through the SDK.

The monitoring calls are the point: the Satellite's address comes out of the
deployment record itself, and the sections are read from the Satellite directly —
the Platform never sits in the data path.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from luml_api import (
    CapabilityNotSupportedError,
    ContractViolationError,
    NotAvailableInVersionError,
    SatelliteOutOfSyncError,
    UnprocessableEntityError,
    UnsupportedCapabilityVersionError,
)
from luml_api._exceptions import (
    LumlAPIError,
    NotFoundError,
)
from luml_api.resources.deployments import (
    AsyncDeploymentResource,
    DeploymentResource,
)
from luml_api.resources.monitoring import (
    MONITORING_API_IMPLEMENTATIONS,
    MonitoringApiImplementation,
    MonitoringOperation,
)

ORG = "0199c337-09f2-7af1-af5e-83fd7a5b51a0"
ORBIT = "0199c337-09f3-753e-9def-b27745e69be6"
DEPLOYMENT_ID = "01a033db-bb07-728a-9b5a-628c4cc6df94"
SATELLITE_ID = "0199c9cd-3e36-72c0-b823-040eb8195067"
SATELLITE_URL = "http://satellite.example"
MONITORING_URL = "/machine/deployments/monitoring-root"


def _record(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    record: dict[str, Any] = {
        "id": DEPLOYMENT_ID,
        "orbit_id": ORBIT,
        "satellite_id": SATELLITE_ID,
        "satellite_name": "satellite",
        "name": "insurance regression",
        "artifact_id": "01a01502-ccff-720d-924b-7bbb13859f22",
        "artifact_name": "insurance_regression_v2",
        "collection_id": "0199c8cf-f4be-79ae-9251-b63108fd9009",
        "monitoring_url": MONITORING_URL,
        "status": "active",
        "monitoring_mode": "full",
        "created_at": "2026-08-24T13:00:00Z",
    }
    record.update(overrides)
    return record


def _satellite(**overrides: Any) -> SimpleNamespace:  # noqa: ANN401
    record: dict[str, Any] = {
        "id": SATELLITE_ID,
        "base_url": SATELLITE_URL,
        "capabilities": {
            "monitoring": {
                "version": 1,
                "api_versions": [1],
                "facets": ["deployment:monitoring"],
            }
        },
        "present_capabilities": ["deploy", "monitoring"],
    }
    record.update(overrides)
    return SimpleNamespace(**record)


def _bind_sync_monitoring(
    mock_sync_client: Mock,
    *,
    deployment: dict[str, Any] | None = None,
    satellite: SimpleNamespace | None = None,
) -> Any:  # noqa: ANN401
    mock_sync_client.get.return_value = deployment or _record()
    mock_sync_client.satellites.get.return_value = satellite or _satellite()
    return DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)


async def _bind_async_monitoring(
    mock_async_client: AsyncMock,
    *,
    deployment: dict[str, Any] | None = None,
    satellite: SimpleNamespace | None = None,
) -> Any:  # noqa: ANN401
    mock_async_client.get = AsyncMock(return_value=deployment or _record())
    mock_async_client.satellites.get = AsyncMock(return_value=satellite or _satellite())
    return await AsyncDeploymentResource(mock_async_client).monitoring(DEPLOYMENT_ID)


def _not_found(body: object) -> NotFoundError:
    request = httpx.Request("GET", f"{SATELLITE_URL}{MONITORING_URL}/overview")
    response = httpx.Response(404, request=request, json=body)
    return NotFoundError("not found", response=response, body=body)


def _unprocessable(body: object) -> UnprocessableEntityError:
    request = httpx.Request("GET", f"{SATELLITE_URL}{MONITORING_URL}/overview")
    response = httpx.Response(422, request=request, json=body)
    return UnprocessableEntityError("invalid query", response=response, body=body)


def test_deployment_get_by_name_goes_through_the_listing(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.return_value = [_record()]

    deployment = DeploymentResource(mock_sync_client).get("insurance regression")

    mock_sync_client.get.assert_called_once_with(
        f"/v1/organizations/{ORG}/orbits/{ORBIT}/deployments"
    )
    assert deployment is not None
    assert deployment.monitoring_mode == "full"


def test_deployment_get_by_id_addresses_it_directly(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = _record()

    deployment = DeploymentResource(mock_sync_client).get(DEPLOYMENT_ID)

    mock_sync_client.get.assert_called_once_with(
        f"/v1/organizations/{ORG}/orbits/{ORBIT}/deployments/{DEPLOYMENT_ID}"
    )
    assert deployment is not None
    assert deployment.satellite_id == SATELLITE_ID
    assert deployment.monitoring_url == MONITORING_URL


def test_monitoring_resolves_the_satellite_from_the_deployment(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.side_effect = [
        _record(),
        {"state": "ok", "cards": []},
    ]
    mock_sync_client.satellites.get.return_value = _satellite()

    monitoring = DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID)
    overview = monitoring.overview(window="7d", severity="critical")

    section_call = mock_sync_client.get.call_args_list[-1]
    assert section_call.args[0] == f"{SATELLITE_URL}{MONITORING_URL}/overview"
    assert section_call.kwargs["params"]["window"] == "7d"
    assert section_call.kwargs["params"]["severity"] == "critical"
    assert overview["state"] == "ok"
    mock_sync_client.satellites.get.assert_called_once_with(SATELLITE_ID)


def test_monitoring_sections_share_one_address_scheme(mock_sync_client: Mock) -> None:
    monitoring = _bind_sync_monitoring(mock_sync_client)

    mock_sync_client.get.reset_mock()
    mock_sync_client.get.side_effect = None
    mock_sync_client.get.return_value = {"state": "ok"}
    monitoring.runtime()
    monitoring.data_quality(feature="age")
    monitoring.output_drift(severity="critical")
    monitoring.alerts(severity="warning")
    monitoring.traces(limit=5, offset=10, sort="latency", order="asc")
    monitoring.trace("evt-1")
    monitoring.worker()

    urls = [call.args[0] for call in mock_sync_client.get.call_args_list]
    base = f"{SATELLITE_URL}{MONITORING_URL}"
    assert urls == [
        f"{base}/runtime",
        f"{base}/data-quality",
        f"{base}/output-drift",
        f"{base}/alerts",
        f"{base}/traces",
        f"{base}/traces/evt-1",
        f"{base}/worker",
    ]
    dq_params = mock_sync_client.get.call_args_list[1].kwargs["params"]
    assert dq_params["feature"] == "age"
    traces_params = mock_sync_client.get.call_args_list[4].kwargs["params"]
    assert traces_params["limit"] == 5
    assert traces_params["sort"] == "latency"
    assert traces_params["order"] == "asc"


def test_monitoring_refuses_a_satellite_without_an_address(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(
        mock_sync_client,
        satellite=_satellite(base_url=None),
    )

    with pytest.raises(LumlAPIError, match="no reachable base URL"):
        monitoring.overview()


def test_monitoring_forwards_query_values_and_dimensions_it_does_not_know(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(mock_sync_client)
    mock_sync_client.get.reset_mock()
    mock_sync_client.get.return_value = {"state": "ok", "cards": []}

    answer = monitoring.overview(
        window="90d",
        start="2026-08-01T00:00:00Z",
        end="2026-08-02T00:00:00Z",
        future_dimension="value",
    )

    assert answer == {"state": "ok", "cards": []}
    assert mock_sync_client.get.call_args.kwargs["params"] == {
        "window": "90d",
        "compare": "reference",
        "severity": "all",
        "granularity": "auto",
        "start": "2026-08-01T00:00:00Z",
        "end": "2026-08-02T00:00:00Z",
        "future_dimension": "value",
    }

    monitoring.traces(sort="color", order="sideways")
    trace_params = mock_sync_client.get.call_args.kwargs["params"]
    assert trace_params["sort"] == "color"
    assert trace_params["order"] == "sideways"


def test_monitoring_surfaces_the_satellites_query_validation_error(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(mock_sync_client)
    mock_sync_client.get.reset_mock()
    error = _unprocessable({"detail": "invalid window"})
    mock_sync_client.get.side_effect = error

    with pytest.raises(UnprocessableEntityError) as raised:
        monitoring.overview(window="later")

    assert raised.value is error
    assert mock_sync_client.get.call_args.kwargs["params"]["window"] == "later"


def test_monitoring_requires_a_present_capability_before_requesting(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(
        mock_sync_client,
        satellite=_satellite(present_capabilities=["deploy"]),
    )
    mock_sync_client.get.reset_mock()

    with pytest.raises(
        CapabilityNotSupportedError,
        match=rf"Satellite {SATELLITE_ID}.*monitoring",
    ):
        monitoring.overview()

    mock_sync_client.get.assert_not_called()


def test_monitoring_rejects_api_versions_with_no_common_version(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(
        mock_sync_client,
        satellite=_satellite(
            capabilities={
                "monitoring": {
                    "version": 1,
                    "api_versions": [3],
                    "facets": ["deployment:monitoring"],
                }
            }
        ),
    )
    mock_sync_client.get.reset_mock()

    with pytest.raises(UnsupportedCapabilityVersionError) as raised:
        monitoring.overview()

    assert raised.value.sdk_versions == (1,)
    assert raised.value.satellite_versions == (3,)
    assert "SDK supports [1]" in str(raised.value)
    assert "Satellite advertises [3]" in str(raised.value)
    mock_sync_client.get.assert_not_called()


def test_monitoring_requires_the_deployment_to_report_its_url(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(
        mock_sync_client,
        deployment=_record(monitoring_url=None),
    )
    mock_sync_client.get.reset_mock()

    with pytest.raises(
        CapabilityNotSupportedError,
        match=rf"Deployment {DEPLOYMENT_ID}.*off or not yet reported",
    ):
        monitoring.overview()

    mock_sync_client.get.assert_not_called()


def test_monitoring_selects_the_highest_common_api_version(
    mock_sync_client: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version_two = MonitoringApiImplementation(
        version=2,
        operations={
            "overview": MonitoringOperation(
                path="overview-v2",
                query_parameters=frozenset({"window"}),
                required_fields=frozenset({"state", "api_version"}),
            )
        },
    )
    monkeypatch.setitem(MONITORING_API_IMPLEMENTATIONS, 2, version_two)
    monitoring = _bind_sync_monitoring(
        mock_sync_client,
        satellite=_satellite(
            capabilities={
                "monitoring": {
                    "version": 1,
                    "api_versions": [1, 2, 3],
                    "facets": ["deployment:monitoring"],
                }
            }
        ),
    )
    mock_sync_client.get.reset_mock()
    mock_sync_client.get.return_value = {"state": "ok", "api_version": 2}

    assert monitoring.overview()["api_version"] == 2
    assert mock_sync_client.get.call_args.args[0] == (
        f"{SATELLITE_URL}{MONITORING_URL}/overview-v2"
    )


def test_monitoring_reports_a_method_missing_from_the_selected_version(
    mock_sync_client: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version_two = MonitoringApiImplementation(
        version=2,
        operations={
            "overview": MonitoringOperation(
                path="overview",
                query_parameters=frozenset(),
                required_fields=frozenset({"state"}),
            )
        },
    )
    monkeypatch.setitem(MONITORING_API_IMPLEMENTATIONS, 2, version_two)
    monitoring = _bind_sync_monitoring(
        mock_sync_client,
        satellite=_satellite(
            capabilities={"monitoring": {"version": 1, "api_versions": [2]}}
        ),
    )
    mock_sync_client.get.reset_mock()

    with pytest.raises(
        NotAvailableInVersionError,
        match="worker.*version 2",
    ):
        monitoring.worker()

    mock_sync_client.get.assert_not_called()


def test_monitoring_rejects_a_response_missing_v1_required_structure(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(mock_sync_client)
    mock_sync_client.get.reset_mock()
    mock_sync_client.get.return_value = {"cards": []}

    with pytest.raises(ContractViolationError) as raised:
        monitoring.overview()

    assert SATELLITE_ID in str(raised.value)
    assert "overview" in str(raised.value)
    assert raised.value.api_version == 1
    assert raised.value.response == {"cards": []}


def test_monitoring_rejects_a_header_without_its_deployment_id(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(mock_sync_client)
    mock_sync_client.get.reset_mock()
    mock_sync_client.get.return_value = {"state": "ok"}

    with pytest.raises(ContractViolationError, match="deployment_id"):
        monitoring.header()


def test_unknown_native_route_is_mapped_to_out_of_sync(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(mock_sync_client)
    mock_sync_client.get.reset_mock()
    mock_sync_client.get.side_effect = _not_found(
        {"detail": "Not Found", "code": "unknown_route"}
    )

    with pytest.raises(SatelliteOutOfSyncError, match="restart or re-pair") as raised:
        monitoring.overview()

    assert raised.value.satellite_id == SATELLITE_ID
    assert raised.value.operation == "overview"
    assert raised.value.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"detail": "not hosted", "code": "deployment_not_hosted"},
        {"detail": "trace not found"},
    ],
)
def test_other_native_not_found_responses_keep_their_existing_meaning(
    mock_sync_client: Mock,
    body: dict[str, str],
) -> None:
    monitoring = _bind_sync_monitoring(mock_sync_client)
    mock_sync_client.get.reset_mock()
    error = _not_found(body)
    mock_sync_client.get.side_effect = error

    with pytest.raises(NotFoundError) as raised:
        monitoring.overview()

    assert raised.value is error


@pytest.mark.asyncio
async def test_async_monitoring_mirrors_the_sync_flow(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get = AsyncMock(
        side_effect=[
            _record(),
            {"state": "ok"},
        ]
    )
    mock_async_client.satellites.get = AsyncMock(return_value=_satellite())

    monitoring = await AsyncDeploymentResource(mock_async_client).monitoring(
        DEPLOYMENT_ID
    )
    overview = await monitoring.overview()

    section_call = mock_async_client.get.call_args_list[-1]
    assert section_call.args[0] == f"{SATELLITE_URL}{MONITORING_URL}/overview"
    assert overview["state"] == "ok"


@pytest.mark.asyncio
async def test_async_monitoring_applies_preflight_before_satellite_requests(
    mock_async_client: AsyncMock,
) -> None:
    monitoring = await _bind_async_monitoring(
        mock_async_client,
        satellite=_satellite(present_capabilities=["deploy"]),
    )
    mock_async_client.get.reset_mock()

    with pytest.raises(CapabilityNotSupportedError):
        await monitoring.overview()

    mock_async_client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_monitoring_forwards_unknown_query_dimensions(
    mock_async_client: AsyncMock,
) -> None:
    monitoring = await _bind_async_monitoring(mock_async_client)
    mock_async_client.get.reset_mock()
    mock_async_client.get.return_value = {"state": "ok", "future": True}

    answer = await monitoring.overview(start="then", end="now")

    assert answer["future"] is True
    params = mock_async_client.get.await_args.kwargs["params"]
    assert params["start"] == "then"
    assert params["end"] == "now"


@pytest.mark.asyncio
async def test_async_unknown_native_route_is_mapped_to_out_of_sync(
    mock_async_client: AsyncMock,
) -> None:
    monitoring = await _bind_async_monitoring(mock_async_client)
    mock_async_client.get.reset_mock()
    mock_async_client.get.side_effect = _not_found(
        {"detail": "Not Found", "code": "unknown_route"}
    )

    with pytest.raises(SatelliteOutOfSyncError, match="restart or re-pair"):
        await monitoring.overview()


def test_deployment_list_is_empty_when_the_platform_says_nothing(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.return_value = None

    assert DeploymentResource(mock_sync_client).list() == []


def test_deployment_get_by_name_returns_none_when_absent(
    mock_sync_client: Mock,
) -> None:
    mock_sync_client.get.return_value = [_record()]

    assert DeploymentResource(mock_sync_client).get("no such deployment") is None


def test_monitoring_accepts_a_deployment_name_not_just_an_id(
    mock_sync_client: Mock,
) -> None:
    """The dashboard is opened by name; the SDK should not demand more."""
    mock_sync_client.get.return_value = [_record()]
    mock_sync_client.satellites.get.return_value = _satellite()

    monitoring = DeploymentResource(mock_sync_client).monitoring("insurance regression")

    assert monitoring.deployment_id == DEPLOYMENT_ID


def test_monitoring_normalizes_a_trailing_slash_in_the_satellite_url(
    mock_sync_client: Mock,
) -> None:
    """The stand stores base URLs like "http://localhost/" — no double slashes."""
    mock_sync_client.get.side_effect = [_record(), {"state": "ok"}]
    mock_sync_client.satellites.get.return_value = _satellite(
        base_url=SATELLITE_URL + "/"
    )

    DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID).worker()

    url = mock_sync_client.get.call_args_list[-1].args[0]
    assert url == f"{SATELLITE_URL}{MONITORING_URL}/worker"


def test_monitoring_accepts_an_absolute_reported_url(
    mock_sync_client: Mock,
) -> None:
    monitoring_url = "https://monitoring.example/custom/root"
    mock_sync_client.get.side_effect = [
        _record(monitoring_url=monitoring_url),
        {"state": "ok"},
    ]
    mock_sync_client.satellites.get.return_value = _satellite(base_url=None)

    DeploymentResource(mock_sync_client).monitoring(DEPLOYMENT_ID).worker()

    assert mock_sync_client.get.call_args_list[-1].args[0] == (
        f"{monitoring_url}/worker"
    )


def test_reference_profile_scopes_to_one_feature_when_asked(
    mock_sync_client: Mock,
) -> None:
    monitoring = _bind_sync_monitoring(mock_sync_client)

    mock_sync_client.get.reset_mock()
    mock_sync_client.get.side_effect = None
    mock_sync_client.get.return_value = {"state": "ok"}
    monitoring.reference_profile(feature="age")
    monitoring.reference_profile()

    scoped = mock_sync_client.get.call_args_list[0].kwargs["params"]
    unscoped = mock_sync_client.get.call_args_list[1].kwargs["params"]
    assert scoped["feature"] == "age"
    # absent, not null: the whole document is addressed by leaving the feature out
    assert "feature" not in unscoped


@pytest.mark.asyncio
async def test_async_monitoring_refuses_a_satellite_without_an_address(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get = AsyncMock(return_value=_record())
    mock_async_client.satellites.get = AsyncMock(return_value=_satellite(base_url=""))
    monitoring = await AsyncDeploymentResource(mock_async_client).monitoring(
        DEPLOYMENT_ID
    )

    with pytest.raises(LumlAPIError, match="no reachable base URL"):
        await monitoring.overview()


@pytest.mark.asyncio
async def test_async_get_by_name_goes_through_the_listing(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get = AsyncMock(return_value=[_record()])

    deployment = await AsyncDeploymentResource(mock_async_client).get(
        "insurance regression"
    )

    assert deployment is not None
    assert deployment.id == DEPLOYMENT_ID
