import copy
from collections.abc import Mapping
from typing import Any, Protocol, cast

from kubernetes_asyncio import client
from kubernetes_asyncio.client.exceptions import ApiException


class KubernetesApiClient(Protocol):
    async def apply(self, manifest: Mapping[str, Any]) -> None: ...

    async def get(self, kind: str, name: str) -> dict[str, Any] | None: ...

    async def delete(self, kind: str, name: str) -> bool: ...

    async def list(self, kind: str, label_selector: str) -> list[dict[str, Any]]: ...

    async def pod_logs(self, pod_name: str, container_name: str, tail_lines: int) -> str: ...

    async def aclose(self) -> None: ...


class KubernetesApi:
    def __init__(
        self,
        namespace: str,
        *,
        api_client: client.ApiClient | None = None,
        field_manager: str = "luml-satellite",
    ) -> None:
        self.namespace = namespace
        self.field_manager = field_manager
        self._api_client = api_client or client.ApiClient()
        self._owns_client = api_client is None
        self._apps = client.AppsV1Api(self._api_client)
        self._core = client.CoreV1Api(self._api_client)
        self._networking = client.NetworkingV1Api(self._api_client)
        self._batch = client.BatchV1Api(self._api_client)

    async def apply(self, manifest: Mapping[str, Any]) -> None:
        kind, name = _identity(manifest)
        body = dict(manifest)
        if kind == "Deployment":
            await self._apps.patch_namespaced_deployment(  # type: ignore[call-arg]
                name,
                self.namespace,
                body,
                field_manager=self.field_manager,
                force=True,
                _content_type="application/apply-patch+yaml",
            )
        elif kind == "Secret":
            await self._core.patch_namespaced_secret(  # type: ignore[call-arg]
                name,
                self.namespace,
                body,
                field_manager=self.field_manager,
                force=True,
                _content_type="application/apply-patch+yaml",
            )
        elif kind == "Service":
            await self._core.patch_namespaced_service(  # type: ignore[call-arg]
                name,
                self.namespace,
                body,
                field_manager=self.field_manager,
                force=True,
                _content_type="application/apply-patch+yaml",
            )
        elif kind == "Ingress":
            await self._networking.patch_namespaced_ingress(  # type: ignore[call-arg]
                name,
                self.namespace,
                body,
                field_manager=self.field_manager,
                force=True,
                _content_type="application/apply-patch+yaml",
            )
        elif kind == "Job":
            await self._batch.patch_namespaced_job(  # type: ignore[call-arg]
                name,
                self.namespace,
                body,
                field_manager=self.field_manager,
                force=True,
                _content_type="application/apply-patch+yaml",
            )
        else:
            raise ValueError(f"unsupported Kubernetes object kind: {kind}")

    async def get(self, kind: str, name: str) -> dict[str, Any] | None:
        result: object
        try:
            if kind == "Deployment":
                result = await self._apps.read_namespaced_deployment(name, self.namespace)
            elif kind == "Secret":
                result = await self._core.read_namespaced_secret(name, self.namespace)
            elif kind == "Service":
                result = await self._core.read_namespaced_service(name, self.namespace)
            elif kind == "Ingress":
                result = await self._networking.read_namespaced_ingress(name, self.namespace)
            elif kind == "Job":
                result = await self._batch.read_namespaced_job(name, self.namespace)
            else:
                raise ValueError(f"unsupported Kubernetes object kind: {kind}")
        except ApiException as error:
            if error.status == 404:
                return None
            raise
        return _serialized(self._api_client, result)

    async def delete(self, kind: str, name: str) -> bool:
        try:
            if kind == "Deployment":
                await self._apps.delete_namespaced_deployment(
                    name,
                    self.namespace,
                    propagation_policy="Foreground",
                )
            elif kind == "Secret":
                await self._core.delete_namespaced_secret(
                    name,
                    self.namespace,
                    propagation_policy="Foreground",
                )
            elif kind == "Service":
                await self._core.delete_namespaced_service(
                    name,
                    self.namespace,
                    propagation_policy="Foreground",
                )
            elif kind == "Ingress":
                await self._networking.delete_namespaced_ingress(
                    name,
                    self.namespace,
                    propagation_policy="Foreground",
                )
            elif kind == "Job":
                await self._batch.delete_namespaced_job(
                    name,
                    self.namespace,
                    propagation_policy="Foreground",
                )
            else:
                raise ValueError(f"unsupported Kubernetes object kind: {kind}")
        except ApiException as error:
            if error.status == 404:
                return False
            raise
        return True

    async def list(self, kind: str, label_selector: str) -> list[dict[str, Any]]:
        result: object
        if kind == "Deployment":
            result = await self._apps.list_namespaced_deployment(
                self.namespace,
                label_selector=label_selector,
            )
        elif kind == "Pod":
            result = await self._core.list_namespaced_pod(
                self.namespace,
                label_selector=label_selector,
            )
        else:
            raise ValueError(f"unsupported Kubernetes list kind: {kind}")
        serialized = _serialized(self._api_client, result)
        items = serialized.get("items", [])
        if not isinstance(items, list):
            return []
        return [cast(dict[str, Any], item) for item in items if isinstance(item, dict)]

    async def pod_logs(self, pod_name: str, container_name: str, tail_lines: int) -> str:
        try:
            result = await self._core.read_namespaced_pod_log(
                pod_name,
                self.namespace,
                container=container_name,
                tail_lines=tail_lines,
            )
        except ApiException as error:
            if error.status == 404:
                return ""
            raise
        return str(result or "")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._api_client.close()


class InMemoryKubernetesApi:
    def __init__(self, namespace: str = "default", *, auto_ready: bool = True) -> None:
        self.namespace = namespace
        self.auto_ready = auto_ready
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.apply_calls: list[tuple[str, str]] = []
        self.delete_calls: list[tuple[str, str]] = []
        self.list_calls: list[tuple[str, str]] = []
        self.logs: dict[tuple[str, str], str] = {}
        self.blocked_deletions: set[tuple[str, str]] = set()
        self.delete_delays: dict[tuple[str, str], int] = {}
        self._pending_deletions: dict[tuple[str, str], int] = {}
        self.closed = False

    async def apply(self, manifest: Mapping[str, Any]) -> None:
        kind, name = _identity(manifest)
        item = copy.deepcopy(dict(manifest))
        if kind == "Deployment" and self.auto_ready:
            replicas = _nested_int(item, "spec", "replicas") or 1
            item["status"] = {
                "replicas": replicas,
                "readyReplicas": replicas,
                "availableReplicas": replicas,
            }
        self.objects[(kind, name)] = item
        self.apply_calls.append((kind, name))

    async def get(self, kind: str, name: str) -> dict[str, Any] | None:
        key = (kind, name)
        if key in self._pending_deletions:
            remaining = self._pending_deletions[key]
            if remaining <= 0:
                self._remove_object(key)
                self._pending_deletions.pop(key, None)
            else:
                self._pending_deletions[key] = remaining - 1
        item = self.objects.get(key)
        return copy.deepcopy(item) if item is not None else None

    async def delete(self, kind: str, name: str) -> bool:
        key = (kind, name)
        self.delete_calls.append(key)
        if key not in self.objects:
            return False
        if key in self.blocked_deletions:
            return True
        delay = self.delete_delays.get(key, 0)
        if delay > 0:
            self._pending_deletions[key] = delay
        else:
            self._remove_object(key)
        return True

    async def list(self, kind: str, label_selector: str) -> list[dict[str, Any]]:
        self.list_calls.append((kind, label_selector))
        expected = _parse_selector(label_selector)
        return [
            copy.deepcopy(item)
            for (item_kind, _), item in self.objects.items()
            if item_kind == kind and _labels_match(item, expected)
        ]

    async def pod_logs(self, pod_name: str, container_name: str, tail_lines: int) -> str:
        lines = self.logs.get((pod_name, container_name), "").splitlines(keepends=True)
        return "".join(lines[-tail_lines:])

    async def aclose(self) -> None:
        self.closed = True

    def put(self, manifest: Mapping[str, Any]) -> None:
        kind, name = _identity(manifest)
        self.objects[(kind, name)] = copy.deepcopy(dict(manifest))

    def object(self, kind: str, name: str) -> dict[str, Any] | None:
        item = self.objects.get((kind, name))
        return copy.deepcopy(item) if item is not None else None

    def _remove_object(self, key: tuple[str, str]) -> None:
        item = self.objects.pop(key, None)
        if item is None or key[0] != "Deployment":
            return
        labels = _mapping(_mapping(item.get("metadata")).get("labels"))
        deployment_id = labels.get("luml.ai/deployment-id")
        if deployment_id is None:
            return
        pod_keys = [
            pod_key
            for pod_key, pod in self.objects.items()
            if pod_key[0] == "Pod"
            and _mapping(_mapping(pod.get("metadata")).get("labels")).get("luml.ai/deployment-id")
            == deployment_id
        ]
        for pod_key in pod_keys:
            self.objects.pop(pod_key, None)


def _identity(manifest: Mapping[str, Any]) -> tuple[str, str]:
    kind = manifest.get("kind")
    metadata = manifest.get("metadata")
    name = metadata.get("name") if isinstance(metadata, Mapping) else None
    if not isinstance(kind, str) or not kind:
        raise ValueError("Kubernetes object has no kind")
    if not isinstance(name, str) or not name:
        raise ValueError("Kubernetes object has no metadata.name")
    return kind, name


def _serialized(api_client: client.ApiClient, value: object) -> dict[str, Any]:
    serialized = api_client.sanitize_for_serialization(value)
    if not isinstance(serialized, dict):
        raise TypeError("Kubernetes API returned a non-object response")
    return cast(dict[str, Any], serialized)


def _parse_selector(selector: str) -> dict[str, str]:
    expected: dict[str, str] = {}
    for expression in selector.split(","):
        if not expression:
            continue
        key, separator, value = expression.partition("=")
        if not separator:
            raise ValueError(f"unsupported label selector: {expression}")
        expected[key] = value
    return expected


def _labels_match(item: Mapping[str, Any], expected: Mapping[str, str]) -> bool:
    metadata = item.get("metadata")
    labels = metadata.get("labels") if isinstance(metadata, Mapping) else None
    if not isinstance(labels, Mapping):
        return not expected
    return all(labels.get(key) == value for key, value in expected.items())


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _nested_int(item: Mapping[str, Any], *keys: str) -> int | None:
    value: object = item
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value if isinstance(value, int) else None
