from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from httpx import URL, InvalidURL

from luml_api._exceptions import (
    CapabilityNotSupportedError,
    ContractViolationError,
    LumlAPIError,
    NotAvailableInVersionError,
    NotFoundError,
    SatelliteOutOfSyncError,
    UnsupportedCapabilityVersionError,
)
from luml_api._types import Deployment


@dataclass(frozen=True)
class MonitoringOperation:
    path: str
    query_parameters: frozenset[str]
    required_fields: frozenset[str]


@dataclass(frozen=True)
class MonitoringApiImplementation:
    version: int
    operations: Mapping[str, MonitoringOperation]


_DIMENSION_PARAMETERS = frozenset(
    {
        "window",
        "compare",
        "severity",
        "granularity",
        "feature",
        "start",
        "end",
        "compare_start",
        "compare_end",
    }
)
_STATE = frozenset({"state"})
_MONITORING_API_V1 = MonitoringApiImplementation(
    version=1,
    operations={
        "header": MonitoringOperation(
            path="header",
            query_parameters=frozenset(),
            required_fields=frozenset({"state", "deployment_id"}),
        ),
        "overview": MonitoringOperation("overview", _DIMENSION_PARAMETERS, _STATE),
        "runtime": MonitoringOperation("runtime", _DIMENSION_PARAMETERS, _STATE),
        "data_quality": MonitoringOperation(
            "data-quality", _DIMENSION_PARAMETERS, _STATE
        ),
        "feature_drift": MonitoringOperation(
            "feature-drift", _DIMENSION_PARAMETERS, _STATE
        ),
        "output_drift": MonitoringOperation(
            "output-drift", _DIMENSION_PARAMETERS, _STATE
        ),
        "reference_profile": MonitoringOperation(
            "reference-profile", _DIMENSION_PARAMETERS, _STATE
        ),
        "alerts": MonitoringOperation("alerts", _DIMENSION_PARAMETERS, _STATE),
        "traces": MonitoringOperation(
            "traces",
            _DIMENSION_PARAMETERS | {"limit", "offset", "sort", "order"},
            _STATE,
        ),
        "trace": MonitoringOperation(
            "traces/{event_id}", _DIMENSION_PARAMETERS, _STATE
        ),
        "worker": MonitoringOperation("worker", frozenset(), _STATE),
    },
)

MONITORING_API_IMPLEMENTATIONS: dict[int, MonitoringApiImplementation] = {
    _MONITORING_API_V1.version: _MONITORING_API_V1
}


class _SatelliteRecord(Protocol):
    id: str
    base_url: str | None
    capabilities: dict[str, dict[str, Any]]
    present_capabilities: list[str]


class _SyncMonitoringClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> object:  # noqa: ANN401
        ...


class _AsyncMonitoringClient(Protocol):
    async def get(self, url: str, **kwargs: Any) -> object:  # noqa: ANN401
        ...


def _trace_page(
    limit: int,
    offset: int,
    sort: str,
    order: str,
    query: dict[str, Any],
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "order": order,
    }
    params.update(query)
    return params


def _dims(
    window: str,
    compare: str,
    severity: str,
    granularity: str,
    feature: str | None,
    query: dict[str, Any],
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "window": window,
        "compare": compare,
        "severity": severity,
        "granularity": granularity,
    }
    if feature is not None:
        params["feature"] = feature
    params.update(query)
    return params


class _MonitoringBase[ClientT: (_SyncMonitoringClient, _AsyncMonitoringClient)]:
    """Monitoring sections of one deployment, read from its Satellite.

    Requests go straight to the Satellite that hosts the deployment — monitoring data
    never passes through the Platform — authenticated with the same API key the client
    already holds. Every method returns the chart-ready payload the dashboard renders,
    exactly as the Satellite's OpenAPI schema describes it.
    """

    def __init__(
        self,
        client: ClientT,
        satellite: _SatelliteRecord,
        deployment: Deployment,
    ) -> None:
        self._client: ClientT = client
        self._satellite: _SatelliteRecord = satellite
        self._deployment: Deployment = deployment
        self._implementation: MonitoringApiImplementation | None = None
        self.deployment_id: str = deployment.id

    def _select_implementation(self) -> MonitoringApiImplementation:
        if "monitoring" not in self._satellite.present_capabilities:
            raise CapabilityNotSupportedError(
                "monitoring",
                self._satellite.id,
                message=(
                    f"Satellite {self._satellite.id} does not have a supported "
                    "monitoring capability according to the Platform"
                ),
            )
        if self._implementation is not None:
            return self._implementation

        declaration = self._satellite.capabilities.get("monitoring", {})
        raw_versions = declaration.get("api_versions", [])
        satellite_versions = (
            tuple(
                version
                for version in raw_versions
                if isinstance(version, int) and not isinstance(version, bool)
            )
            if isinstance(raw_versions, list)
            else ()
        )
        common_versions = set(satellite_versions).intersection(
            MONITORING_API_IMPLEMENTATIONS
        )
        if not common_versions:
            raise UnsupportedCapabilityVersionError(
                "monitoring",
                self._satellite.id,
                MONITORING_API_IMPLEMENTATIONS,
                satellite_versions,
            )
        self._implementation = MONITORING_API_IMPLEMENTATIONS[max(common_versions)]
        return self._implementation

    def _monitoring_root(self) -> str:
        monitoring_url = self._deployment.monitoring_url
        if not monitoring_url:
            raise CapabilityNotSupportedError(
                "monitoring",
                self._satellite.id,
                deployment_id=self._deployment.id,
                message=(
                    f"Deployment {self._deployment.id} has no monitoring URL; "
                    "monitoring is off or not yet reported by its Satellite"
                ),
            )

        try:
            target = URL(monitoring_url)
            if target.is_absolute_url:
                return str(target).rstrip("/")
            if not self._satellite.base_url:
                raise LumlAPIError(
                    f"Satellite {self._satellite.id} has no reachable base URL "
                    "configured, so its relative monitoring URL cannot be addressed"
                )
            base = URL(f"{self._satellite.base_url.rstrip('/')}/")
            if not base.is_absolute_url:
                raise InvalidURL("Satellite base URL must be absolute")
            return str(base.join(monitoring_url)).rstrip("/")
        except InvalidURL as error:
            raise LumlAPIError(
                f"Deployment {self._deployment.id} has an invalid monitoring URL "
                f"{monitoring_url!r}"
            ) from error

    def _request_details(
        self,
        operation_name: str,
        path_values: Mapping[str, str] | None = None,
    ) -> tuple[str, MonitoringOperation, MonitoringApiImplementation]:
        implementation = self._select_implementation()
        root = self._monitoring_root()
        operation = implementation.operations.get(operation_name)
        if operation is None:
            raise NotAvailableInVersionError(
                "monitoring", operation_name, implementation.version
            )
        path = operation.path.format(**(path_values or {}))
        return f"{root}/{path}", operation, implementation

    def _validate_response(
        self,
        operation_name: str,
        operation: MonitoringOperation,
        implementation: MonitoringApiImplementation,
        response: object,
    ) -> dict[str, Any]:
        if not isinstance(response, dict):
            raise ContractViolationError(
                self._satellite.id,
                operation_name,
                implementation.version,
                response,
                (),
            )
        missing_fields = operation.required_fields.difference(response)
        if missing_fields:
            raise ContractViolationError(
                self._satellite.id,
                operation_name,
                implementation.version,
                response,
                missing_fields,
            )
        return cast(dict[str, Any], response)

    def _out_of_sync_error(
        self,
        error: NotFoundError,
        operation_name: str,
        implementation: MonitoringApiImplementation,
    ) -> SatelliteOutOfSyncError | None:
        if isinstance(error.body, dict) and error.body.get("code") == "unknown_route":
            return SatelliteOutOfSyncError(
                self._satellite.id,
                operation_name,
                implementation.version,
                response=error.response,
                body=error.body,
            )
        return None


class DeploymentMonitoring(_MonitoringBase[_SyncMonitoringClient]):
    def _get(
        self,
        operation_name: str,
        params: dict[str, Any] | None = None,
        path_values: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        url, operation, implementation = self._request_details(
            operation_name, path_values
        )
        try:
            response = (
                self._client.get(url, params=params)
                if params
                else self._client.get(url)
            )
        except NotFoundError as error:
            mapped = self._out_of_sync_error(error, operation_name, implementation)
            if mapped is not None:
                raise mapped from error
            raise
        return self._validate_response(
            operation_name, operation, implementation, response
        )

    def header(self, **query: Any) -> dict[str, Any]:  # noqa: ANN401
        """
        Identity of the deployment as the dashboard header shows it.

        Returns:
            dict with the deployment's name, status, task type, model name, and the
            timestamps of the last prediction and the last materialized
            monitoring window.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        header = monitoring.header()
        ```

        Example response:
        ```python
        {
            "state": "ok",
            "deployment_id": "01a033db-bb07-728a-9b5a-628c4cc6df94",
            "name": "insurance regression",
            "status": "active",
            "task_type": "regression",
            "model_name": "insurance_regression_v2",
            "satellite": "satellite",
            "last_prediction_at": "2026-08-24T16:19:32.140034Z",
            "last_monitored_at": "2026-08-24T16:20:00Z",
            "profile_status": "ready",
        }
        ```
        """
        return self._get("header", query)

    def overview(
        self,
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        feature: str | None = None,
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Status summary of the deployment: what changed and where to look first.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            compare: What deltas are computed against: "reference" (the
                training profile) or "previous" (the preceding period).
            severity: Alert severity filter: "all", "warning" or "critical".
            granularity: Series bucketing: "auto", "hour" or "day".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with status cards, alert banners, runtime series and the top drifted
            features — the chart-ready payload the dashboard's Overview tab renders.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        overview = monitoring.overview(window="7d", severity="critical")
        ```
        """
        return self._get(
            "overview",
            _dims(window, compare, severity, granularity, feature, query),
        )

    def runtime(
        self,
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Whether the deployed endpoint is technically healthy.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            compare: What deltas are computed against: "reference" (the
                training profile) or "previous" (the preceding period).
            severity: Alert severity filter: "all", "warning" or "critical".
            granularity: Series bucketing: "auto", "hour" or "day".

        Returns:
            dict with request/success/error counts, error rate, latency percentiles,
            timeout and failed-inference counts, the outcome breakdown by HTTP status,
            time series, and the runtime alerts.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        runtime = monitoring.runtime(window="24h")
        ```
        """
        return self._get(
            "runtime",
            _dims(window, compare, severity, granularity, None, query),
        )

    def data_quality(
        self,
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Whether live inputs still conform to the model contract.

        Without ``feature`` the payload covers every feature; with it, the named
        feature's trends are included as well.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with per-feature rates of missing values, type mismatches, range
            violations and unseen categories, plus summaries of the invalid values seen.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        data_quality = monitoring.data_quality(feature="age")
        ```
        """
        return self._get(
            "data_quality",
            _dims(window, "reference", severity, "auto", feature, query),
        )

    def feature_drift(
        self,
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Which inputs changed compared with the training reference.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with the PSI ranking of all features, the selected feature's
            distributions and PSI history, and the multivariate (PCA) panel.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        feature_drift = monitoring.feature_drift(severity="critical")
        ```
        """
        return self._get(
            "feature_drift",
            _dims(window, "reference", severity, "auto", feature, query),
        )

    def output_drift(
        self,
        window: str = "24h",
        severity: str = "all",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Did the model's outputs shift against the training reference.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".

        Returns:
            dict with the output's PSI score and severity, the reference vs
            current distribution of predictions, the PSI history, and the output
            drift alerts. Numerical outputs add the prediction trend (median
            with its p05-p95 band); categorical outputs add the top changed
            classes, each drifted class's share across windows, and — when the
            artifact reports probabilities — the confidence block, per-class
            probability drift and the decision-boundary rate; forecasting
            deployments add per-horizon drift, the headline describing the
            worst horizon.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        output_drift = monitoring.output_drift(window="7d")
        ```
        """
        return self._get(
            "output_drift",
            _dims(window, "reference", severity, "auto", None, query),
        )

    def reference_profile(
        self,
        feature: str | None = None,
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        The profile the deployment is compared against.

        This is the reference profile shipped inside the model artifact: schemas,
        baseline distributions and threshold rules.

        Args:
            feature: Optional feature name to scope the section to.

        Returns:
            dict with the profile document, or one feature's entry when ``feature``
            is passed.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        reference_profile = monitoring.reference_profile()
        ```
        """
        return self._get(
            "reference_profile",
            _dims("24h", "reference", "all", "auto", feature, query),
        )

    def alerts(
        self,
        window: str = "24h",
        severity: str = "all",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Open and acknowledged alerts, grouped by metric family.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".

        Returns:
            dict with alert groups (runtime, data quality, feature drift, output drift,
            multivariate); every alert carries its current value, threshold, state and
            metric history.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        alerts = monitoring.alerts(window="7d", severity="critical")
        ```
        """
        return self._get(
            "alerts",
            _dims(window, "reference", severity, "auto", None, query),
        )

    def traces(
        self,
        window: str = "24h",
        limit: int = 50,
        offset: int = 0,
        sort: str = "ts",
        order: str = "desc",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        The local request log: one row per inference call.

        Sorting happens on the Satellite before pagination, so a page is a slice of
        the fully sorted log — not a sorted slice.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            limit: Maximum rows per page (up to 200).
            offset: Rows to skip, for paging.
            sort: Column to order by: "ts" (call time, the default), "latency"
                (response time) or "status" (HTTP status code).
            order: "desc" (default) or "asc".

        Returns:
            dict with the page's rows (event id, timestamp, feature summary, prediction,
            latency, status) and the total count.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        latest = monitoring.traces(limit=20)
        slowest = monitoring.traces(sort="latency", order="desc", limit=10)
        ```
        """
        params = _dims(window, "reference", "all", "auto", None, {})
        params.update(_trace_page(limit, offset, sort, order, query))
        return self._get("traces", params)

    def trace(
        self,
        event_id: str,
        window: str = "24h",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        One call with its full payloads and span tree.

        The window must cover the call: the Satellite looks the event up inside it.

        Args:
            event_id: Event ID of the call, from a ``traces()`` row.
            window: Time range the section covers: "24h", "7d" or "30d".

        Returns:
            dict with the call's inputs, output, latency, status and
            OpenTelemetry spans.

        Raises:
            NotFoundError: If the event is not found in the window, or the
                Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        trace = monitoring.trace("01a03491-e699-7244-ba1f-84ddc4cde2a1")
        ```
        """
        return self._get(
            "trace",
            _dims(window, "reference", "all", "auto", None, query),
            {"event_id": event_id},
        )

    def worker(self, **query: Any) -> dict[str, Any]:  # noqa: ANN401
        """
        Whether monitoring itself is keeping up — not a metric about the model.

        Returns:
            dict with the worker's liveness, processed-window counters, lag behind the
            last closed window, and the history of metric failures.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        worker = monitoring.worker()
        ```
        """
        return self._get("worker", query)


class AsyncDeploymentMonitoring(_MonitoringBase[_AsyncMonitoringClient]):
    async def _get(
        self,
        operation_name: str,
        params: dict[str, Any] | None = None,
        path_values: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        url, operation, implementation = self._request_details(
            operation_name, path_values
        )
        try:
            response = (
                await self._client.get(url, params=params)
                if params
                else await self._client.get(url)
            )
        except NotFoundError as error:
            mapped = self._out_of_sync_error(error, operation_name, implementation)
            if mapped is not None:
                raise mapped from error
            raise
        return self._validate_response(
            operation_name, operation, implementation, response
        )

    async def header(self, **query: Any) -> dict[str, Any]:  # noqa: ANN401
        """
        Identity of the deployment as the dashboard header shows it.

        Returns:
            dict with the deployment's name, status, task type, model name, and the
            timestamps of the last prediction and the last materialized
            monitoring window.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            header = await monitoring.header()
        ```

        Example response:
        ```python
        {
            "state": "ok",
            "deployment_id": "01a033db-bb07-728a-9b5a-628c4cc6df94",
            "name": "insurance regression",
            "status": "active",
            "task_type": "regression",
            "model_name": "insurance_regression_v2",
            "satellite": "satellite",
            "last_prediction_at": "2026-08-24T16:19:32.140034Z",
            "last_monitored_at": "2026-08-24T16:20:00Z",
            "profile_status": "ready",
        }
        ```
        """
        return await self._get("header", query)

    async def overview(
        self,
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        feature: str | None = None,
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Status summary of the deployment: what changed and where to look first.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            compare: What deltas are computed against: "reference" (the
                training profile) or "previous" (the preceding period).
            severity: Alert severity filter: "all", "warning" or "critical".
            granularity: Series bucketing: "auto", "hour" or "day".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with status cards, alert banners, runtime series and the top drifted
            features — the chart-ready payload the dashboard's Overview tab renders.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            overview = await monitoring.overview(window="7d", severity="critical")
        ```
        """
        return await self._get(
            "overview",
            _dims(window, compare, severity, granularity, feature, query),
        )

    async def runtime(
        self,
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Whether the deployed endpoint is technically healthy.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            compare: What deltas are computed against: "reference" (the
                training profile) or "previous" (the preceding period).
            severity: Alert severity filter: "all", "warning" or "critical".
            granularity: Series bucketing: "auto", "hour" or "day".

        Returns:
            dict with request/success/error counts, error rate, latency percentiles,
            timeout and failed-inference counts, the outcome breakdown by HTTP status,
            time series, and the runtime alerts.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            runtime = await monitoring.runtime(window="24h")
        ```
        """
        return await self._get(
            "runtime",
            _dims(window, compare, severity, granularity, None, query),
        )

    async def data_quality(
        self,
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Whether live inputs still conform to the model contract.

        Without ``feature`` the payload covers every feature; with it, the named
        feature's trends are included as well.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with per-feature rates of missing values, type mismatches, range
            violations and unseen categories, plus summaries of the invalid values seen.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            data_quality = await monitoring.data_quality(feature="age")
        ```
        """
        return await self._get(
            "data_quality",
            _dims(window, "reference", severity, "auto", feature, query),
        )

    async def feature_drift(
        self,
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Which inputs changed compared with the training reference.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with the PSI ranking of all features, the selected feature's
            distributions and PSI history, and the multivariate (PCA) panel.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            feature_drift = await monitoring.feature_drift(severity="critical")
        ```
        """
        return await self._get(
            "feature_drift",
            _dims(window, "reference", severity, "auto", feature, query),
        )

    async def output_drift(
        self,
        window: str = "24h",
        severity: str = "all",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Did the model's outputs shift against the training reference.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".

        Returns:
            dict with the output's PSI score and severity, the reference vs
            current distribution of predictions, the PSI history, and the output
            drift alerts. Numerical outputs add the prediction trend (median
            with its p05-p95 band); categorical outputs add the top changed
            classes, each drifted class's share across windows, and — when the
            artifact reports probabilities — the confidence block, per-class
            probability drift and the decision-boundary rate; forecasting
            deployments add per-horizon drift, the headline describing the
            worst horizon.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            output_drift = await monitoring.output_drift(window="7d")
        ```
        """
        return await self._get(
            "output_drift",
            _dims(window, "reference", severity, "auto", None, query),
        )

    async def reference_profile(
        self,
        feature: str | None = None,
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        The profile the deployment is compared against.

        This is the reference profile shipped inside the model artifact: schemas,
        baseline distributions and threshold rules.

        Args:
            feature: Optional feature name to scope the section to.

        Returns:
            dict with the profile document, or one feature's entry when ``feature``
            is passed.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            reference_profile = await monitoring.reference_profile()
        ```
        """
        return await self._get(
            "reference_profile",
            _dims("24h", "reference", "all", "auto", feature, query),
        )

    async def alerts(
        self,
        window: str = "24h",
        severity: str = "all",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Open and acknowledged alerts, grouped by metric family.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".

        Returns:
            dict with alert groups (runtime, data quality, feature drift, output drift,
            multivariate); every alert carries its current value, threshold, state and
            metric history.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            alerts = await monitoring.alerts(window="7d", severity="critical")
        ```
        """
        return await self._get(
            "alerts",
            _dims(window, "reference", severity, "auto", None, query),
        )

    async def traces(
        self,
        window: str = "24h",
        limit: int = 50,
        offset: int = 0,
        sort: str = "ts",
        order: str = "desc",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        The local request log: one row per inference call.

        Sorting happens on the Satellite before pagination, so a page is a slice of
        the fully sorted log — not a sorted slice.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            limit: Maximum rows per page (up to 200).
            offset: Rows to skip, for paging.
            sort: Column to order by: "ts" (call time, the default), "latency"
                (response time) or "status" (HTTP status code).
            order: "desc" (default) or "asc".

        Returns:
            dict with the page's rows (event id, timestamp, feature summary, prediction,
            latency, status) and the total count.

        Raises:
            UnprocessableEntityError: If the Satellite rejects a query parameter.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            latest = await monitoring.traces(limit=20)
            slowest = await monitoring.traces(sort="latency", order="desc", limit=10)
        ```
        """
        params = _dims(window, "reference", "all", "auto", None, {})
        params.update(_trace_page(limit, offset, sort, order, query))
        return await self._get("traces", params)

    async def trace(
        self,
        event_id: str,
        window: str = "24h",
        **query: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        One call with its full payloads and span tree.

        The window must cover the call: the Satellite looks the event up inside it.

        Args:
            event_id: Event ID of the call, from a ``traces()`` row.
            window: Time range the section covers: "24h", "7d" or "30d".

        Returns:
            dict with the call's inputs, output, latency, status and
            OpenTelemetry spans.

        Raises:
            NotFoundError: If the event is not found in the window, or the
                Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            trace = await monitoring.trace("01a03491-e699-7244-ba1f-84ddc4cde2a1")
        ```
        """
        return await self._get(
            "trace",
            _dims(window, "reference", "all", "auto", None, query),
            {"event_id": event_id},
        )

    async def worker(self, **query: Any) -> dict[str, Any]:  # noqa: ANN401
        """
        Whether monitoring itself is keeping up — not a metric about the model.

        Returns:
            dict with the worker's liveness, processed-window counters, lag behind the
            last closed window, and the history of metric failures.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            worker = await monitoring.worker()
        ```
        """
        return await self._get("worker", query)
