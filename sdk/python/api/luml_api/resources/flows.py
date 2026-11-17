from typing import TYPE_CHECKING

from luml_api._types import Flow, FlowExposed

if TYPE_CHECKING:
    from luml_api._client import AsyncLumlClient, LumlClient


class FlowResource:
    """The current user's flows on the configured orbit's Flow page."""

    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    def _path(self, flow_id: str | None = None) -> str:
        path = (
            f"/v1/organizations/{self._client.organization}"
            f"/orbits/{self._client.orbit}/flows"
        )
        return path if flow_id is None else f"{path}/{flow_id}"

    def expose(self, name: str) -> FlowExposed:
        """
        Expose a flow in the configured orbit through the orbit's relay.

        Exposing a name the user already has replaces that flow's session, so a
        rerun after a crash keeps one card on the Flow page.

        Returns:
            FlowExposed: The flow, the started session for the agent to serve and
            the address of the orbit's Flow page in the LUML app.

        Raises:
            ConflictError: If the orbit has no relay or its relay is draining.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        exposed = luml.flows.expose("training")
        exposed.app_url
        ```
        """
        return FlowExposed.model_validate(
            self._client.post(self._path(), json={"name": name})
        )

    def list(self) -> list[Flow]:
        """List the current user's flows whose session has not ended."""
        return [Flow.model_validate(flow) for flow in self._client.get(self._path())]

    def get(self, flow_id: str) -> Flow:
        """
        Read one flow.

        Raises:
            NotFoundError: If the flow does not exist or belongs to another user.
        """
        return Flow.model_validate(self._client.get(self._path(flow_id)))

    def remove(self, flow_id: str) -> None:
        """Remove a flow and end its session; its agent exits on its next heartbeat."""
        return self._client.delete(self._path(flow_id))


class AsyncFlowResource:
    """Async variant of `FlowResource`."""

    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    def _path(self, flow_id: str | None = None) -> str:
        path = (
            f"/v1/organizations/{self._client.organization}"
            f"/orbits/{self._client.orbit}/flows"
        )
        return path if flow_id is None else f"{path}/{flow_id}"

    async def expose(self, name: str) -> FlowExposed:
        """Async variant of `FlowResource.expose`."""
        return FlowExposed.model_validate(
            await self._client.post(self._path(), json={"name": name})
        )

    async def list(self) -> list[Flow]:
        """Async variant of `FlowResource.list`."""
        return [
            Flow.model_validate(flow) for flow in await self._client.get(self._path())
        ]

    async def get(self, flow_id: str) -> Flow:
        """Async variant of `FlowResource.get`."""
        return Flow.model_validate(await self._client.get(self._path(flow_id)))

    async def remove(self, flow_id: str) -> None:
        """Async variant of `FlowResource.remove`."""
        return await self._client.delete(self._path(flow_id))
