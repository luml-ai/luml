from typing import TYPE_CHECKING

from luml_api._types import AsyncSatellite, Satellite

if TYPE_CHECKING:
    from luml_api._client import AsyncLumlClient, LumlClient


class SatelliteResource:
    """Satellites of the configured orbit, as the Platform records them."""

    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    def _path(self, satellite_id: str) -> str:
        return (
            f"/v1/organizations/{self._client.organization}"
            f"/orbits/{self._client.orbit}/satellites/{satellite_id}"
        )

    def get(self, satellite_id: str) -> Satellite:
        """
        Read one Satellite record from the Platform.

        The record carries the capability document the Satellite declared when it
        paired and the Platform-computed `present_capabilities` list. The returned
        handle can also describe and call the Satellite's own API: `operations()`
        lists its endpoints from the stored OpenAPI document, and `request()`
        performs one call against the Satellite.

        Args:
            satellite_id: Id of the Satellite.

        Returns:
            Satellite: The Satellite record bound to the Platform and machine APIs.

        Raises:
            NotFoundError: If the orbit has no Satellite with this id.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        satellite = luml.satellites.get("0199c9cd-3e36-72c0-b823-040eb8195067")
        satellite.present_capabilities
        # ["deploy", "monitoring"]
        ```
        """
        path = self._path(satellite_id)
        satellite = Satellite.model_validate(self._client.get(path))
        satellite._bind(self._client, f"{path}/openapi")
        return satellite


class AsyncSatelliteResource:
    """Async variant of `SatelliteResource`."""

    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    def _path(self, satellite_id: str) -> str:
        return (
            f"/v1/organizations/{self._client.organization}"
            f"/orbits/{self._client.orbit}/satellites/{satellite_id}"
        )

    async def get(self, satellite_id: str) -> AsyncSatellite:
        """
        Read one Satellite record from the Platform.

        Async variant of `SatelliteResource.get`.

        Args:
            satellite_id: Id of the Satellite.

        Returns:
            AsyncSatellite: The Satellite record bound to the Platform and machine
            APIs.

        Raises:
            NotFoundError: If the orbit has no Satellite with this id.
        """
        path = self._path(satellite_id)
        satellite = AsyncSatellite.model_validate(await self._client.get(path))
        satellite._bind(self._client, f"{path}/openapi")
        return satellite
