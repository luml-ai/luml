import copy
import logging

import pytest

from luml_satellite.testing.fake_platform import FakePlatform, default_contract_openapi
from luml_satellite.wire import ContractVerdict, PlatformClient


@pytest.mark.asyncio
async def test_unavailable_contract_warns_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform(legacy=True)
    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        comparison = await client.check_contract()

    assert comparison.verdict is ContractVerdict.UNAVAILABLE
    assert "contract unavailable" in caplog.text
    assert caplog.records[-1].levelno == logging.WARNING


@pytest.mark.asyncio
async def test_missing_operation_reports_older_platform(
    caplog: pytest.LogCaptureFixture,
) -> None:
    openapi = copy.deepcopy(default_contract_openapi())
    del openapi["paths"]["/satellites/v1/tasks"]
    platform = FakePlatform(contract_openapi=openapi)

    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        comparison = await client.check_contract()

    assert comparison.verdict is ContractVerdict.PLATFORM_OLDER
    assert [operation.label for operation in comparison.missing_operations] == [
        "GET /satellites/v1/tasks"
    ]
    assert "missing operations: GET /satellites/v1/tasks" in caplog.text
    assert caplog.records[-1].levelno == logging.ERROR


@pytest.mark.asyncio
async def test_newer_platform_warns_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform(api_version=2)
    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        comparison = await client.check_contract()

    assert comparison.verdict is ContractVerdict.PLATFORM_NEWER
    assert "contract is newer" in caplog.text
    assert caplog.records[-1].levelno == logging.WARNING


@pytest.mark.asyncio
async def test_parameter_names_are_normalized() -> None:
    openapi = copy.deepcopy(default_contract_openapi())
    renamed_paths = {
        path.replace("{deployment_id}", "{deployment}")
        .replace("{task_id}", "{task}")
        .replace("{secret_id}", "{secret}")
        .replace("{artifact_id}", "{artifact}"): value
        for path, value in openapi["paths"].items()
    }
    openapi["paths"] = renamed_paths
    platform = FakePlatform(contract_openapi=openapi)

    async with PlatformClient(
        "http://platform", "test-token", transport=platform.transport
    ) as client:
        comparison = await client.check_contract()

    assert comparison.verdict is ContractVerdict.OK
    assert comparison.missing_operations == ()
