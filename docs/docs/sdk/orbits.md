<a id="luml.api.resources.orbits"></a>

# luml.api.resources.orbits

<a id="luml.api.resources.orbits.OrbitResource"></a>

## OrbitResource Objects

```python
class OrbitResource(OrbitResourceBase)
```

Resource for managing Orbits.

<a id="luml.api.resources.orbits.OrbitResource.get"></a>

#### get

```python
def get(orbit_value: str | None = None) -> Orbit | None
```

Get orbit by ID or name.

Retrieves orbit details by its ID or name.
Search by name is case-sensitive and matches exact orbit name.

**Arguments**:

- `orbit_value` - The ID or exact name of the orbit to retrieve.
  

**Returns**:

  Orbit object.
  
  Returns None if orbit with the specified id or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - if there are several
  Orbits with that name.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
orbit_by_name = luml.orbits.get("Default Orbit")
orbit_by_id = luml.orbits.get("0199c455-21ed-7aba-9fe5-5231611220de")
```
  
  Example response:
```python
Orbit(
    id="0199c455-21ed-7aba-9fe5-5231611220de",
    name="Default Orbit",
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    total_members=2,
    total_collections=9,
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at='2025-08-13T22:44:58.035731Z'
)
```

<a id="luml.api.resources.orbits.OrbitResource.list"></a>

#### list

```python
def list() -> list[Orbit]
```

List all orbits related to default organization.

**Returns**:

  List of Orbits objects.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
orgs = luml.orbits.list()
```
  
  Example response:
```python
[
    Orbit(
        id="0199c455-21ed-7aba-9fe5-5231611220de",
        name="Default Orbit",
        organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
        bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
        total_members=2,
        total_collections=9,
        created_at='2025-05-21T19:35:17.340408Z',
        updated_at='2025-08-13T22:44:58.035731Z'
    )
]
```

<a id="luml.api.resources.orbits.OrbitResource.create"></a>

#### create

```python
def create(name: str, bucket_secret_id: str) -> Orbit
```

Create new orbit in the default organization.

**Arguments**:

- `name` - Name of the orbit.
- `bucket_secret_id` - ID of the bucket secret.
  The bucket secret must exist before orbit creation.
  

**Returns**:

- `Orbit` - Newly created orbit object with generated ID and timestamps.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
orbit = luml.orbits.create(
    name="ML Models",
    bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de"
)
```
  
  Response object:
```python
Orbit(
    id="0199c455-21ed-7aba-9fe5-5231611220de",
    name="Default Orbit",
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    total_members=2,
    total_collections=9,
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at='2025-08-13T22:44:58.035731Z'
)
```

<a id="luml.api.resources.orbits.OrbitResource.update"></a>

#### update

```python
def update(
    name: str | None = None,
    bucket_secret_id: str | None = None
) -> Orbit
```

Update default orbit configuration.

Updates current orbit's name, bucket secret. Only provided
parameters will be updated, others remain unchanged.

**Arguments**:

- `name` - New name for the orbit. If None, name remains unchanged.
- `bucket_secret_id` - New bucket secret for storage configuration.
  The bucket secret must exist. If None, bucket secret remains unchanged.
  

**Returns**:

- `Orbit` - Updated orbit object.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
orbit = luml.orbits.update(name="New Orbit Name")

orbit = luml.orbits.update(
    name="New Orbit Name",
    bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de"
)
```
  
  Response object:
```python
Orbit(
    id="0199c455-21ed-7aba-9fe5-5231611220de",
    name="Default Orbit",
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    total_members=2,
    total_collections=9,
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at='2025-08-13T22:44:58.035731Z'
)
```
  

**Notes**:

  This method updates the orbit set as default in the client.

<a id="luml.api.resources.orbits.OrbitResource.delete"></a>

#### delete

```python
def delete(orbit_id: str) -> None
```

Delete orbit by ID.

Permanently removes the orbit and all its associated data including
collections, models, and configurations. This action cannot be undone.

**Returns**:

- `None` - No return value on successful deletion.
  

**Raises**:

- `LumlAPIError` - If try to delete default orbit.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
luml.orbits.delete("0199c455-21ed-7aba-9fe5-5231611220de")
```
  

**Warnings**:

  This operation is irreversible. All collections, models, and data
  within the orbit will be permanently lost. Consider backing up
  important data before deletion.

<a id="luml.api.resources.orbits.AsyncOrbitResource"></a>

## AsyncOrbitResource Objects

```python
class AsyncOrbitResource(OrbitResourceBase)
```

Resource for managing Orbits for async client.

<a id="luml.api.resources.orbits.AsyncOrbitResource.get"></a>

#### get

```python
async def get(orbit_value: str | None = None) -> Orbit | None
```

Get orbit by ID or name.

Retrieves orbit details by its ID or name.
Search by name is case-sensitive and matches exact orbit name.

**Arguments**:

- `orbit_value` - The ID or exact name of the orbit to retrieve.
  

**Returns**:

  Orbit object.
  
  Returns None if orbit with the specified id or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - if there are several
  Orbits with that name.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)
luml.setup_config(
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
async def main():
    orbit_by_name = await luml.orbits.get("Default Orbit")
    orbit_by_id = await luml.orbits.get(
        "0199c455-21ed-7aba-9fe5-5231611220de"
    )
```
  
  Example response:
```python
Orbit(
    id="0199c455-21ed-7aba-9fe5-5231611220de",
    name="Default Orbit",
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    total_members=2,
    total_collections=9,
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at='2025-08-13T22:44:58.035731Z'
)
```

<a id="luml.api.resources.orbits.AsyncOrbitResource.list"></a>

#### list

```python
async def list() -> list[Orbit]
```

List all orbits related to default organization.

**Returns**:

  List of Orbits objects.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)
luml.setup_config(
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
async def main():
    orgs = await luml.orbits.list()
```
  
  Example response:
```python
[
    Orbit(
        id="0199c455-21ed-7aba-9fe5-5231611220de",
        name="Default Orbit",
        organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
        bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
        total_members=2,
        total_collections=9,
        created_at='2025-05-21T19:35:17.340408Z',
        updated_at='2025-08-13T22:44:58.035731Z'
    )
]
```

<a id="luml.api.resources.orbits.AsyncOrbitResource.create"></a>

#### create

```python
async def create(name: str, bucket_secret_id: str) -> Orbit
```

Create new orbit in the default organization.

**Arguments**:

- `name` - Name of the orbit.
- `bucket_secret_id` - ID of the bucket secret.
  The bucket secret must exist before orbit creation.
  

**Returns**:

- `Orbit` - Newly created orbit object with generated ID and timestamps.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)
luml.setup_config(
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
async def main():
    orbit = await luml.orbits.create(
        name="ML Models",
        bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de"
    )
```
  
  Response object:
```python
Orbit(
    id="0199c455-21ed-7aba-9fe5-5231611220de",
    name="Default Orbit",
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    total_members=2,
    total_collections=9,
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at='2025-08-13T22:44:58.035731Z'
)
```

<a id="luml.api.resources.orbits.AsyncOrbitResource.update"></a>

#### update

```python
async def update(
    name: str | None = None,
    bucket_secret_id: str | None = None
) -> Orbit
```

Update default orbit configuration.

Updates current orbit's name, bucket secret. Only provided
parameters will be updated, others remain unchanged.

**Arguments**:

- `name` - New name for the orbit. If None, name remains unchanged.
- `bucket_secret_id` - New bucket secret for storage configuration.
  The bucket secret must exist. If None, bucket secret remains unchanged.
  

**Returns**:

- `Orbit` - Updated orbit object.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)
luml.setup_config(
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
async def main():
    orbit = await luml.orbits.update(name="New Orbit Name")

    orbit = await luml.orbits.update(
        name="New Orbit Name",
        bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de"
    )
```
  
  Response object:
```python
Orbit(
    id="0199c455-21ed-7aba-9fe5-5231611220de",
    name="Default Orbit",
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    total_members=2,
    total_collections=9,
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at='2025-08-13T22:44:58.035731Z'
)
```
  

**Notes**:

  This method updates the orbit set as default in the client.

<a id="luml.api.resources.orbits.AsyncOrbitResource.delete"></a>

#### delete

```python
async def delete(orbit_id: str) -> None
```

Delete orbit by ID.

Permanently removes the orbit and all its associated data including
collections, models, and configurations. This action cannot be undone.

**Returns**:

- `None` - No return value on successful deletion.
  

**Raises**:

- `LumlAPIError` - If try to delete default orbit.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)
luml.setup_config(
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
async def main():
    await luml.orbits.delete("0199c475-8339-70ec-b032-7b3f5d59fdc1")
```
  

**Warnings**:

  This operation is irreversible. All collections, models, and data
  within the orbit will be permanently lost. Consider backing up
  important data before deletion.

