from typing import TYPE_CHECKING

from luml_api._types import Relay, RelayStatus, RelayWithToken, is_uuid
from luml_api._utils import find_by_value

if TYPE_CHECKING:
    from luml_api._client import AsyncLumlClient, LumlClient


class RelayResource:
    """Relays of the configured organization and the managed relays it may use.

    Managed relays are read-only: updating, rotating or deleting one raises
    `PermissionDeniedError`.
    """

    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    def _path(self, relay_id: str | None = None) -> str:
        path = f"/v1/organizations/{self._client.organization}/relays"
        return path if relay_id is None else f"{path}/{relay_id}"

    def list(self) -> list[Relay]:
        """List the organization's own relays and every managed relay."""
        return [Relay.model_validate(relay) for relay in self._client.get(self._path())]

    def get(self, relay_value: str) -> Relay | None:
        """
        Get a relay by ID or exact label.

        Returns:
            Relay, or None when no relay has that label.

        Raises:
            NotFoundError: If no usable relay has that ID.
            MultipleResourcesFoundError: If several relays have that label.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        )
        relay = luml.relays.get("eu")
        relay.kind, relay.online
        ```
        """
        if is_uuid(relay_value):
            return Relay.model_validate(self._client.get(self._path(relay_value)))
        return find_by_value(self.list(), relay_value, lambda r: r.label == relay_value)

    def create(self, label: str, base_domain: str, agent_url: str) -> RelayWithToken:
        """
        Register a relay owned by the organization.

        Args:
            label: Name shown for the relay.
            base_domain: Bare hostname sessions get subdomains of,
                e.g. `tunnel.example.com`.
            agent_url: The `ws://` or `wss://` address agents connect to.

        Returns:
            RelayWithToken: The relay and its plaintext token. The token is
            answered only here; the relay process is configured with it.

        Raises:
            ConflictError: If another relay already uses the base domain.
        """
        return RelayWithToken.model_validate(
            self._client.post(
                self._path(),
                json={
                    "label": label,
                    "base_domain": base_domain,
                    "agent_url": agent_url,
                },
            )
        )

    def update(
        self,
        relay_id: str,
        label: str | None = None,
        base_domain: str | None = None,
        agent_url: str | None = None,
        status: RelayStatus | None = None,
    ) -> Relay:
        """
        Update an own relay; only the given fields change.

        A draining relay keeps serving its sessions but takes no new ones.

        Raises:
            ConflictError: If the base domain or agent address changes while the
                relay has sessions that have not ended.
        """
        return Relay.model_validate(
            self._client.patch(
                self._path(relay_id),
                json=self._client.filter_none(
                    {
                        "label": label,
                        "base_domain": base_domain,
                        "agent_url": agent_url,
                        "status": status,
                    }
                ),
            )
        )

    def rotate_token(self, relay_id: str) -> RelayWithToken:
        """
        Issue a new token for an own relay.

        The previous token keeps working for a short overlap so the relay can be
        restarted with the new one. The plaintext token is answered only here.
        """
        return RelayWithToken.model_validate(
            self._client.post(f"{self._path(relay_id)}/rotate-token")
        )

    def delete(self, relay_id: str) -> None:
        """
        Delete an own relay; orbits assigned to it lose the assignment.

        Raises:
            ConflictError: If the relay has sessions that have not ended.
        """
        return self._client.delete(self._path(relay_id))


class AsyncRelayResource:
    """Async variant of `RelayResource`."""

    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    def _path(self, relay_id: str | None = None) -> str:
        path = f"/v1/organizations/{self._client.organization}/relays"
        return path if relay_id is None else f"{path}/{relay_id}"

    async def list(self) -> list[Relay]:
        """Async variant of `RelayResource.list`."""
        return [
            Relay.model_validate(relay)
            for relay in await self._client.get(self._path())
        ]

    async def get(self, relay_value: str) -> Relay | None:
        """Async variant of `RelayResource.get`."""
        if is_uuid(relay_value):
            return Relay.model_validate(await self._client.get(self._path(relay_value)))
        return find_by_value(
            await self.list(), relay_value, lambda r: r.label == relay_value
        )

    async def create(
        self, label: str, base_domain: str, agent_url: str
    ) -> RelayWithToken:
        """Async variant of `RelayResource.create`."""
        return RelayWithToken.model_validate(
            await self._client.post(
                self._path(),
                json={
                    "label": label,
                    "base_domain": base_domain,
                    "agent_url": agent_url,
                },
            )
        )

    async def update(
        self,
        relay_id: str,
        label: str | None = None,
        base_domain: str | None = None,
        agent_url: str | None = None,
        status: RelayStatus | None = None,
    ) -> Relay:
        """Async variant of `RelayResource.update`."""
        return Relay.model_validate(
            await self._client.patch(
                self._path(relay_id),
                json=self._client.filter_none(
                    {
                        "label": label,
                        "base_domain": base_domain,
                        "agent_url": agent_url,
                        "status": status,
                    }
                ),
            )
        )

    async def rotate_token(self, relay_id: str) -> RelayWithToken:
        """Async variant of `RelayResource.rotate_token`."""
        return RelayWithToken.model_validate(
            await self._client.post(f"{self._path(relay_id)}/rotate-token")
        )

    async def delete(self, relay_id: str) -> None:
        """Async variant of `RelayResource.delete`."""
        return await self._client.delete(self._path(relay_id))
