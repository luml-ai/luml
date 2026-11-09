<a id="luml_api._client"></a>

# luml_api._client

<a id="luml_api._client.AsyncLumlClient"></a>

## AsyncLumlClient Objects

```python
class AsyncLumlClient(LumlClientBase, AsyncBaseClient)
```

<a id="luml_api._client.AsyncLumlClient.setup_config"></a>

#### setup_config

```python
async def setup_config(
        *,
        organization: str | None = None,
        orbit: str | None = None,
        collection: str | None = None
) -> None
```

Method for setting default values for AsyncLumlClient

**Arguments**:

- `organization` - Default organization to use for operations. Can be set by organization ID or name.
- `orbit` - Default orbit to use for operations. Can be set by organization ID or name.
- `collection` - Default collection to use for operations. Can be set by organization ID or name.
  

**Example**:

```python
luml = AsyncLumlClient(api_key="luml_api_key")
async def main():
    await luml.setup_config(
        "0199c455-21ec-7c74-8efe-41470e29bae5",
        "0199c455-21ed-7aba-9fe5-5231611220de",
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
```

<a id="luml_api._client.AsyncLumlClient.organizations"></a>

#### organizations

```python
@cached_property
def organizations() -> "AsyncOrganizationResource"
```

Organizations interface.

<a id="luml_api._client.AsyncLumlClient.bucket_secrets"></a>

#### bucket_secrets

```python
@cached_property
def bucket_secrets() -> "AsyncBucketSecretResource"
```

Bucket Secrets interface.

<a id="luml_api._client.AsyncLumlClient.orbits"></a>

#### orbits

```python
@cached_property
def orbits() -> "AsyncOrbitResource"
```

Orbits interface.

<a id="luml_api._client.AsyncLumlClient.collections"></a>

#### collections

```python
@cached_property
def collections() -> "AsyncCollectionResource"
```

Collections interface.

<a id="luml_api._client.AsyncLumlClient.artifacts"></a>

#### artifacts

```python
@cached_property
def artifacts() -> "AsyncArtifactResource"
```

Artifacts interface.

<a id="luml_api._client.AsyncLumlClient.tracks"></a>

#### tracks

```python
@cached_property
def tracks() -> "AsyncTrackResource"
```

Tracks interface.

<a id="luml_api._client.AsyncLumlClient.deployments"></a>

#### deployments

```python
@cached_property
def deployments() -> "AsyncDeploymentResource"
```

Deployments and their monitoring.

<a id="luml_api._client.AsyncLumlClient.satellites"></a>

#### satellites

```python
@cached_property
def satellites() -> "AsyncSatelliteResource"
```

Satellites and their advertised operations.

<a id="luml_api._client.AsyncLumlClient.live_sessions"></a>

#### live_sessions

```python
@cached_property
def live_sessions() -> "AsyncLiveSessionResource"
```

Live sessions exposed through a relay.

<a id="luml_api._client.AsyncLumlClient.flows"></a>

#### flows

```python
@cached_property
def flows() -> "AsyncFlowResource"
```

Flows on the orbit's Flow page, each served through a live session.

<a id="luml_api._client.AsyncLumlClient.relays"></a>

#### relays

```python
@cached_property
def relays() -> "AsyncRelayResource"
```

Relays that serve live sessions.

<a id="luml_api._client.LumlClient"></a>

## LumlClient Objects

```python
class LumlClient(LumlClientBase, SyncBaseClient)
```

<a id="luml_api._client.LumlClient.organizations"></a>

#### organizations

```python
@cached_property
def organizations() -> "OrganizationResource"
```

Organizations interface.

<a id="luml_api._client.LumlClient.bucket_secrets"></a>

#### bucket_secrets

```python
@cached_property
def bucket_secrets() -> "BucketSecretResource"
```

Bucket Secrets interface.

<a id="luml_api._client.LumlClient.orbits"></a>

#### orbits

```python
@cached_property
def orbits() -> "OrbitResource"
```

Orbits interface.

<a id="luml_api._client.LumlClient.collections"></a>

#### collections

```python
@cached_property
def collections() -> "CollectionResource"
```

Collections interface.

<a id="luml_api._client.LumlClient.artifacts"></a>

#### artifacts

```python
@cached_property
def artifacts() -> "ArtifactResource"
```

Artifacts interface.

<a id="luml_api._client.LumlClient.tracks"></a>

#### tracks

```python
@cached_property
def tracks() -> "TrackResource"
```

Tracks interface.

<a id="luml_api._client.LumlClient.deployments"></a>

#### deployments

```python
@cached_property
def deployments() -> "DeploymentResource"
```

Deployments and their monitoring.

<a id="luml_api._client.LumlClient.satellites"></a>

#### satellites

```python
@cached_property
def satellites() -> "SatelliteResource"
```

Satellites and their advertised operations.

<a id="luml_api._client.LumlClient.live_sessions"></a>

#### live_sessions

```python
@cached_property
def live_sessions() -> "LiveSessionResource"
```

Live sessions exposed through a relay.

<a id="luml_api._client.LumlClient.flows"></a>

#### flows

```python
@cached_property
def flows() -> "FlowResource"
```

Flows on the orbit's Flow page, each served through a live session.

<a id="luml_api._client.LumlClient.relays"></a>

#### relays

```python
@cached_property
def relays() -> "RelayResource"
```

Relays that serve live sessions.

