<a id="luml_api.resources.satellites"></a>

# luml_api.resources.satellites

<a id="luml_api.resources.satellites.SatelliteResource"></a>

## SatelliteResource Objects

```python
class SatelliteResource()
```

Satellites of the configured orbit, as the Platform records them.

<a id="luml_api.resources.satellites.SatelliteResource.get"></a>

#### get

```python
def get(satellite_id: str) -> Satellite
```

Read one Satellite record from the Platform.

The record carries the capability document the Satellite declared when it
paired and the Platform-computed `present_capabilities` list. The returned
handle can also describe and call the Satellite's own API: `operations()`
lists its endpoints from the stored OpenAPI document, and `request()`
performs one call against the Satellite.

**Arguments**:

- `satellite_id` - Id of the Satellite.
  

**Returns**:

- `Satellite` - The Satellite record bound to the Platform and machine APIs.
  

**Raises**:

- `NotFoundError` - If the orbit has no Satellite with this id.
  

**Example**:

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

<a id="luml_api.resources.satellites.AsyncSatelliteResource"></a>

## AsyncSatelliteResource Objects

```python
class AsyncSatelliteResource()
```

Async variant of `SatelliteResource`.

<a id="luml_api.resources.satellites.AsyncSatelliteResource.get"></a>

#### get

```python
async def get(satellite_id: str) -> AsyncSatellite
```

Read one Satellite record from the Platform.

Async variant of `SatelliteResource.get`.

**Arguments**:

- `satellite_id` - Id of the Satellite.
  

**Returns**:

- `AsyncSatellite` - The Satellite record bound to the Platform and machine APIs.
  

**Raises**:

- `NotFoundError` - If the orbit has no Satellite with this id.

