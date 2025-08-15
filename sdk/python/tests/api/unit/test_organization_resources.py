from unittest.mock import AsyncMock, Mock

import pytest

from dataforce.api._types import Organization
from dataforce.api.resources.organizations import (
    AsyncOrganizationResource,
    OrganizationResource,
)


def test_organization_list(
    mock_sync_client: Mock, sample_organization: Organization
) -> None:
    mock_sync_client.get.return_value = [sample_organization]

    resource = OrganizationResource(mock_sync_client)
    orgs = resource.list()

    mock_sync_client.get.assert_called_once_with("/users/me/organizations")
    assert len(orgs) == 1
    assert orgs[0].name == sample_organization.name


def test_organization_list_no_orgs(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = None

    resource = OrganizationResource(mock_sync_client)
    orgs = resource.list()

    mock_sync_client.get.assert_called_once_with("/users/me/organizations")
    assert len(orgs) == 0


def test_organization_get(
    mock_sync_client: Mock, sample_organization: Organization
) -> None:
    organization_name = sample_organization.name
    organization_id = sample_organization.id

    mock_sync_client.get.return_value = [sample_organization]

    resource = OrganizationResource(mock_sync_client)
    org = resource.get(organization_name)

    mock_sync_client.get.assert_called_once_with("/users/me/organizations")
    assert org.id == organization_id
    assert org.name == organization_name


def test_organization_get_by_name(
    mock_sync_client: Mock, sample_organization: Organization
) -> None:
    organization_name = sample_organization.name
    mock_sync_client.get.return_value = [sample_organization]

    resource = OrganizationResource(mock_sync_client)
    org = resource._get_by_name(organization_name)

    assert org.name == organization_name


@pytest.mark.asyncio
async def test_async_organization_list(
    mock_async_client: AsyncMock, sample_organization: Organization
) -> None:
    organization_name = sample_organization.name
    mock_async_client.get.return_value = [sample_organization]

    resource = AsyncOrganizationResource(mock_async_client)
    orgs = await resource.list()

    mock_async_client.get.assert_called_once_with("/users/me/organizations")
    assert len(orgs) == 1
    assert orgs[0].name == organization_name


@pytest.mark.asyncio
async def test_async_organization_get(
    mock_async_client: AsyncMock, sample_organization: Organization
) -> None:
    organization_name = sample_organization.name
    organization_id = sample_organization.id

    mock_async_client.get.return_value = [sample_organization]

    resource = AsyncOrganizationResource(mock_async_client)
    org = await resource.get(organization_name)

    mock_async_client.get.assert_called_once_with("/users/me/organizations")
    assert isinstance(org, Organization)
    assert org.id == organization_id
    assert org.name == organization_name


@pytest.mark.asyncio
async def test_async_organization_get_by_name(
    mock_async_client: AsyncMock, sample_organization: Organization
) -> None:
    organization_name = sample_organization.name
    mock_async_client.get.return_value = [sample_organization]

    resource = AsyncOrganizationResource(mock_async_client)
    org = await resource._get_by_name(organization_name)

    assert isinstance(org, Organization)
    assert org.name == organization_name


@pytest.mark.asyncio
async def test_async_organization_list_no_orgs(mock_async_client: AsyncMock) -> None:
    mock_async_client.get.return_value = None

    resource = AsyncOrganizationResource(mock_async_client)
    orgs = await resource.list()

    mock_async_client.get.assert_called_once_with("/users/me/organizations")
    assert len(orgs) == 0
