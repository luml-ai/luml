<a id="luml_api.resources.deployments"></a>

# luml_api.resources.deployments

<a id="luml_api.resources.deployments.DeploymentResource"></a>

## DeploymentResource Objects

```python
class DeploymentResource(DeploymentResourceBase)
```

Resource for reading Deployments and their monitoring.

<a id="luml_api.resources.deployments.DeploymentResource.get"></a>

#### get

```python
def get(deployment_value: str) -> Deployment | None
```

Get a deployment by ID or exact name.

Search by name is case-sensitive, matches the exact deployment name, and goes
through the orbit's deployment listing; an ID is addressed directly.

**Arguments**:

- `deployment_value` - The ID or exact name of the deployment to retrieve.
  

**Returns**:

  Deployment object.
  
  Returns None if a deployment with the specified ID or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - If several deployments share that name.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
deployment_by_name = luml.deployments.get("insurance regression")
deployment_by_id = luml.deployments.get(
    "01a033db-bb07-728a-9b5a-628c4cc6df94"
)
```
  
**Example response**:
```python
Deployment(
    id="01a033db-bb07-728a-9b5a-628c4cc6df94",
    orbit_id="0199c8cf-4d35-783b-9f81-cb3cec788074",
    satellite_id="0199c9cd-3e36-72c0-b823-040eb8195067",
    satellite_name="satellite",
    name="insurance regression",
    artifact_id="01a01502-ccff-720d-924b-7bbb13859f22",
    artifact_name="insurance_regression_v2",
    collection_id="0199c8cf-f4be-79ae-9251-b63108fd9009",
    inference_url="/deployments/01a033db-bb07-728a-9b5a-628c4cc6df94",
    status="active",
    monitoring_mode="full",
    created_at="2026-08-24T13:00:00Z",
)
```

<a id="luml_api.resources.deployments.DeploymentResource.list"></a>

#### list

```python
def list() -> list[Deployment]
```

List all deployments in the default orbit.

Each row carries the deployment's monitoring mode, so a caller can tell what
is monitored without further requests.

**Returns**:

  List of Deployment objects.
  
  Returns an empty list when the orbit has no deployments.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
for deployment in luml.deployments.list():
    print(deployment.name, deployment.status, deployment.monitoring_mode)
```

<a id="luml_api.resources.deployments.DeploymentResource.monitoring"></a>

#### monitoring

```python
def monitoring(deployment_value: str) -> DeploymentMonitoring
```

Monitoring sections of a deployment, read from its Satellite.

The Satellite's address is resolved from the deployment record itself
(deployment -> satellite -> base URL), so the caller needs nothing beyond the
deployment's name or ID. Section calls then go to the Satellite directly with
the client's API key; monitoring data never passes through the Platform.

**Arguments**:

- `deployment_value` - The ID or exact name of the deployment.
  

**Returns**:

  DeploymentMonitoring accessor bound to the deployment, with one method per
  dashboard section.
  

**Raises**:

- `LumlAPIError` - If the deployment is not found.
- `MultipleResourcesFoundError` - If several deployments share that name.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
monitoring = luml.deployments.monitoring("insurance regression")
overview = monitoring.overview(window="7d")
alerts = monitoring.alerts(severity="critical")
```

<a id="luml_api.resources.deployments.AsyncDeploymentResource"></a>

## AsyncDeploymentResource Objects

```python
class AsyncDeploymentResource(DeploymentResourceBase)
```

Async resource for reading Deployments and their monitoring.

<a id="luml_api.resources.deployments.AsyncDeploymentResource.get"></a>

#### get

```python
async def get(deployment_value: str) -> Deployment | None
```

Get a deployment by ID or exact name.

Search by name is case-sensitive, matches the exact deployment name, and goes
through the orbit's deployment listing; an ID is addressed directly.

**Arguments**:

- `deployment_value` - The ID or exact name of the deployment to retrieve.
  

**Returns**:

  Deployment object.
  
  Returns None if a deployment with the specified ID or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - If several deployments share that name.
  

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
    deployment_by_name = luml.deployments.get("insurance regression")
    deployment_by_id = luml.deployments.get(
        "01a033db-bb07-728a-9b5a-628c4cc6df94"
    )
```
  
**Example response**:
```python
Deployment(
    id="01a033db-bb07-728a-9b5a-628c4cc6df94",
    orbit_id="0199c8cf-4d35-783b-9f81-cb3cec788074",
    satellite_id="0199c9cd-3e36-72c0-b823-040eb8195067",
    satellite_name="satellite",
    name="insurance regression",
    artifact_id="01a01502-ccff-720d-924b-7bbb13859f22",
    artifact_name="insurance_regression_v2",
    collection_id="0199c8cf-f4be-79ae-9251-b63108fd9009",
    inference_url="/deployments/01a033db-bb07-728a-9b5a-628c4cc6df94",
    status="active",
    monitoring_mode="full",
    created_at="2026-08-24T13:00:00Z",
)
```

<a id="luml_api.resources.deployments.AsyncDeploymentResource.list"></a>

#### list

```python
async def list() -> list[Deployment]
```

List all deployments in the default orbit.

Each row carries the deployment's monitoring mode, so a caller can tell what
is monitored without further requests.

**Returns**:

  List of Deployment objects.
  
  Returns an empty list when the orbit has no deployments.
  

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
    for deployment in luml.deployments.list():
        print(deployment.name, deployment.status, deployment.monitoring_mode)
```

<a id="luml_api.resources.deployments.AsyncDeploymentResource.monitoring"></a>

#### monitoring

```python
async def monitoring(deployment_value: str) -> AsyncDeploymentMonitoring
```

Monitoring sections of a deployment, read from its Satellite.

The Satellite's address is resolved from the deployment record itself
(deployment -> satellite -> base URL), so the caller needs nothing beyond the
deployment's name or ID. Section calls then go to the Satellite directly with
the client's API key; monitoring data never passes through the Platform.

**Arguments**:

- `deployment_value` - The ID or exact name of the deployment.
  

**Returns**:

  DeploymentMonitoring accessor bound to the deployment, with one method per
  dashboard section.
  

**Raises**:

- `LumlAPIError` - If the deployment is not found.
- `MultipleResourcesFoundError` - If several deployments share that name.
  

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
    monitoring = luml.deployments.monitoring("insurance regression")
    overview = monitoring.overview(window="7d")
    alerts = monitoring.alerts(severity="critical")
```

