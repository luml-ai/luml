<a id="luml_api.resources.monitoring"></a>

# luml_api.resources.monitoring

<a id="luml_api.resources.monitoring.DeploymentMonitoring"></a>

## DeploymentMonitoring Objects

```python
class DeploymentMonitoring(_MonitoringBase[_SyncMonitoringClient])
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.header"></a>

#### header

```python
def header(**query: Any) -> dict[str, Any]
```

Identity of the deployment as the dashboard header shows it.

**Returns**:

  dict with the deployment's name, status, task type, model name, and the
  timestamps of the last prediction and the last materialized
  monitoring window.
  

**Raises**:

- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
header = monitoring.header()
```
  
**Example response**:
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

<a id="luml_api.resources.monitoring.DeploymentMonitoring.overview"></a>

#### overview

```python
def overview(
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        feature: str | None = None,
        **query: Any
) -> dict[str, Any]
```

Status summary of the deployment: what changed and where to look first.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `compare` - What deltas are computed against: "reference" (the training profile) or "previous" (the preceding period).
- `severity` - Alert severity filter: "all", "warning" or "critical".
- `granularity` - Series bucketing: "auto", "hour" or "day".
- `feature` - Optional feature name to scope the section to.
  

**Returns**:

  dict with status cards, alert banners, runtime series and the top drifted
  features — the chart-ready payload the dashboard's Overview tab renders.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
overview = monitoring.overview(window="7d", severity="critical")
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.runtime"></a>

#### runtime

```python
def runtime(
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        **query: Any
) -> dict[str, Any]
```

Whether the deployed endpoint is technically healthy.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `compare` - What deltas are computed against: "reference" (the training profile) or "previous" (the preceding period).
- `severity` - Alert severity filter: "all", "warning" or "critical".
- `granularity` - Series bucketing: "auto", "hour" or "day".
  

**Returns**:

  dict with request/success/error counts, error rate, latency percentiles,
  timeout and failed-inference counts, the outcome breakdown by HTTP status,
  time series, and the runtime alerts.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
runtime = monitoring.runtime(window="24h")
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.data_quality"></a>

#### data_quality

```python
def data_quality(
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
        **query: Any
) -> dict[str, Any]
```

Whether live inputs still conform to the model contract.

Without ``feature`` the payload covers every feature; with it, the named
feature's trends are included as well.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `severity` - Alert severity filter: "all", "warning" or "critical".
- `feature` - Optional feature name to scope the section to.
  

**Returns**:

  dict with per-feature rates of missing values, type mismatches, range
  violations and unseen categories, plus summaries of the invalid values seen.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
data_quality = monitoring.data_quality(feature="age")
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.feature_drift"></a>

#### feature_drift

```python
def feature_drift(
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
        **query: Any
) -> dict[str, Any]
```

Which inputs changed compared with the training reference.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `severity` - Alert severity filter: "all", "warning" or "critical".
- `feature` - Optional feature name to scope the section to.
  

**Returns**:

  dict with the PSI ranking of all features, the selected feature's
  distributions and PSI history, and the multivariate (PCA) panel.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
feature_drift = monitoring.feature_drift(severity="critical")
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.output_drift"></a>

#### output_drift

```python
def output_drift(
        window: str = "24h",
        severity: str = "all",
        **query: Any
) -> dict[str, Any]
```

Did the model's outputs shift against the training reference.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `severity` - Alert severity filter: "all", "warning" or "critical".
  

**Returns**:

  dict with the output's PSI score and severity, the reference vs
  current distribution of predictions, the PSI history, and the output
  drift alerts. Numerical outputs add the prediction trend (median
  with its p05-p95 band); categorical outputs add the top changed
  classes, each drifted class's share across windows, and — when the
  artifact reports probabilities — the confidence block, per-class
  probability drift and the decision-boundary rate; forecasting
  deployments add per-horizon drift, the headline describing the
  worst horizon.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
output_drift = monitoring.output_drift(window="7d")
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.reference_profile"></a>

#### reference_profile

```python
def reference_profile(
        feature: str | None = None,
        **query: Any
) -> dict[str, Any]
```

The profile the deployment is compared against.

This is the reference profile shipped inside the model artifact: schemas,
baseline distributions and threshold rules.

**Arguments**:

- `feature` - Optional feature name to scope the section to.
  

**Returns**:

  dict with the profile document, or one feature's entry when ``feature``
  is passed.
  

**Raises**:

- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
reference_profile = monitoring.reference_profile()
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.alerts"></a>

#### alerts

```python
def alerts(
        window: str = "24h",
        severity: str = "all",
        **query: Any
) -> dict[str, Any]
```

Open and acknowledged alerts, grouped by metric family.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `severity` - Alert severity filter: "all", "warning" or "critical".
  

**Returns**:

  dict with alert groups (runtime, data quality, feature drift, output drift,
  multivariate); every alert carries its current value, threshold, state and
  metric history.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
alerts = monitoring.alerts(window="7d", severity="critical")
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.traces"></a>

#### traces

```python
def traces(
        window: str = "24h",
        limit: int = 50,
        offset: int = 0,
        sort: str = "ts",
        order: str = "desc",
        **query: Any
) -> dict[str, Any]
```

The local request log: one row per inference call.

Sorting happens on the Satellite before pagination, so a page is a slice of
the fully sorted log — not a sorted slice.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `limit` - Maximum rows per page (up to 200).
- `offset` - Rows to skip, for paging.
- `sort` - Column to order by: "ts" (call time, the default), "latency" (response time) or "status" (HTTP status code).
- `order` - "desc" (default) or "asc".
  

**Returns**:

  dict with the page's rows (event id, timestamp, feature summary, prediction,
  latency, status) and the total count.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.DeploymentMonitoring.trace"></a>

#### trace

```python
def trace(event_id: str, window: str = "24h", **query: Any) -> dict[str, Any]
```

One call with its full payloads and span tree.

The window must cover the call: the Satellite looks the event up inside it.

**Arguments**:

- `event_id` - Event ID of the call, from a ``traces()`` row.
- `window` - Time range the section covers: "24h", "7d" or "30d".
  

**Returns**:

  dict with the call's inputs, output, latency, status and
  OpenTelemetry spans.
  

**Raises**:

- `NotFoundError` - If the event is not found in the window, or the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
trace = monitoring.trace("01a03491-e699-7244-ba1f-84ddc4cde2a1")
```

<a id="luml_api.resources.monitoring.DeploymentMonitoring.worker"></a>

#### worker

```python
def worker(**query: Any) -> dict[str, Any]
```

Whether monitoring itself is keeping up — not a metric about the model.

**Returns**:

  dict with the worker's liveness, processed-window counters, lag behind the
  last closed window, and the history of metric failures.
  

**Raises**:

- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
worker = monitoring.worker()
```

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring"></a>

## AsyncDeploymentMonitoring Objects

```python
class AsyncDeploymentMonitoring(_MonitoringBase[_AsyncMonitoringClient])
```

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.header"></a>

#### header

```python
async def header(**query: Any) -> dict[str, Any]
```

Identity of the deployment as the dashboard header shows it.

**Returns**:

  dict with the deployment's name, status, task type, model name, and the
  timestamps of the last prediction and the last materialized
  monitoring window.
  

**Raises**:

- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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
  
**Example response**:
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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.overview"></a>

#### overview

```python
async def overview(
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        feature: str | None = None,
        **query: Any
) -> dict[str, Any]
```

Status summary of the deployment: what changed and where to look first.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `compare` - What deltas are computed against: "reference" (the training profile) or "previous" (the preceding period).
- `severity` - Alert severity filter: "all", "warning" or "critical".
- `granularity` - Series bucketing: "auto", "hour" or "day".
- `feature` - Optional feature name to scope the section to.
  

**Returns**:

  dict with status cards, alert banners, runtime series and the top drifted
  features — the chart-ready payload the dashboard's Overview tab renders.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.runtime"></a>

#### runtime

```python
async def runtime(
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        **query: Any
) -> dict[str, Any]
```

Whether the deployed endpoint is technically healthy.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `compare` - What deltas are computed against: "reference" (the training profile) or "previous" (the preceding period).
- `severity` - Alert severity filter: "all", "warning" or "critical".
- `granularity` - Series bucketing: "auto", "hour" or "day".
  

**Returns**:

  dict with request/success/error counts, error rate, latency percentiles,
  timeout and failed-inference counts, the outcome breakdown by HTTP status,
  time series, and the runtime alerts.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.data_quality"></a>

#### data_quality

```python
async def data_quality(
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
        **query: Any
) -> dict[str, Any]
```

Whether live inputs still conform to the model contract.

Without ``feature`` the payload covers every feature; with it, the named
feature's trends are included as well.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `severity` - Alert severity filter: "all", "warning" or "critical".
- `feature` - Optional feature name to scope the section to.
  

**Returns**:

  dict with per-feature rates of missing values, type mismatches, range
  violations and unseen categories, plus summaries of the invalid values seen.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.feature_drift"></a>

#### feature_drift

```python
async def feature_drift(
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
        **query: Any
) -> dict[str, Any]
```

Which inputs changed compared with the training reference.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `severity` - Alert severity filter: "all", "warning" or "critical".
- `feature` - Optional feature name to scope the section to.
  

**Returns**:

  dict with the PSI ranking of all features, the selected feature's
  distributions and PSI history, and the multivariate (PCA) panel.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.output_drift"></a>

#### output_drift

```python
async def output_drift(
        window: str = "24h",
        severity: str = "all",
        **query: Any
) -> dict[str, Any]
```

Did the model's outputs shift against the training reference.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `severity` - Alert severity filter: "all", "warning" or "critical".
  

**Returns**:

  dict with the output's PSI score and severity, the reference vs
  current distribution of predictions, the PSI history, and the output
  drift alerts. Numerical outputs add the prediction trend (median
  with its p05-p95 band); categorical outputs add the top changed
  classes, each drifted class's share across windows, and — when the
  artifact reports probabilities — the confidence block, per-class
  probability drift and the decision-boundary rate; forecasting
  deployments add per-horizon drift, the headline describing the
  worst horizon.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.reference_profile"></a>

#### reference_profile

```python
async def reference_profile(
        feature: str | None = None,
        **query: Any
) -> dict[str, Any]
```

The profile the deployment is compared against.

This is the reference profile shipped inside the model artifact: schemas,
baseline distributions and threshold rules.

**Arguments**:

- `feature` - Optional feature name to scope the section to.
  

**Returns**:

  dict with the profile document, or one feature's entry when ``feature``
  is passed.
  

**Raises**:

- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.alerts"></a>

#### alerts

```python
async def alerts(
        window: str = "24h",
        severity: str = "all",
        **query: Any
) -> dict[str, Any]
```

Open and acknowledged alerts, grouped by metric family.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `severity` - Alert severity filter: "all", "warning" or "critical".
  

**Returns**:

  dict with alert groups (runtime, data quality, feature drift, output drift,
  multivariate); every alert carries its current value, threshold, state and
  metric history.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.traces"></a>

#### traces

```python
async def traces(
        window: str = "24h",
        limit: int = 50,
        offset: int = 0,
        sort: str = "ts",
        order: str = "desc",
        **query: Any
) -> dict[str, Any]
```

The local request log: one row per inference call.

Sorting happens on the Satellite before pagination, so a page is a slice of
the fully sorted log — not a sorted slice.

**Arguments**:

- `window` - Time range the section covers: "24h", "7d" or "30d".
- `limit` - Maximum rows per page (up to 200).
- `offset` - Rows to skip, for paging.
- `sort` - Column to order by: "ts" (call time, the default), "latency" (response time) or "status" (HTTP status code).
- `order` - "desc" (default) or "asc".
  

**Returns**:

  dict with the page's rows (event id, timestamp, feature summary, prediction,
  latency, status) and the total count.
  

**Raises**:

- `UnprocessableEntityError` - If the Satellite rejects a query parameter.
- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.trace"></a>

#### trace

```python
async def trace(
        event_id: str,
        window: str = "24h",
        **query: Any
) -> dict[str, Any]
```

One call with its full payloads and span tree.

The window must cover the call: the Satellite looks the event up inside it.

**Arguments**:

- `event_id` - Event ID of the call, from a ``traces()`` row.
- `window` - Time range the section covers: "24h", "7d" or "30d".
  

**Returns**:

  dict with the call's inputs, output, latency, status and
  OpenTelemetry spans.
  

**Raises**:

- `NotFoundError` - If the event is not found in the window, or the Satellite does not host this deployment.
  

**Example**:

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

<a id="luml_api.resources.monitoring.AsyncDeploymentMonitoring.worker"></a>

#### worker

```python
async def worker(**query: Any) -> dict[str, Any]
```

Whether monitoring itself is keeping up — not a metric about the model.

**Returns**:

  dict with the worker's liveness, processed-window counters, lag behind the
  last closed window, and the history of metric failures.
  

**Raises**:

- `NotFoundError` - If the Satellite does not host this deployment.
  

**Example**:

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

