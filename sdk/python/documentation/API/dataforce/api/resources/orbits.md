---
sidebar_label: orbits
title: dataforce.api.resources.orbits
---

## OrbitResourceBase

```python
class OrbitResourceBase(ABC)
```

Abstract Resource for managing Orbits.

## OrbitResource

```python
class OrbitResource(OrbitResourceBase)
```

Resource for managing Orbits.

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  ... orbit_by_name = dfs.orbits.get(&quot;Default Orbit&quot;)
  ... orbit_by_id = dfs.orbits.get(&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;)
  
  Example response:
  &gt;&gt;&gt; Orbit(
  ...    id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    name=&quot;Default Orbit&quot;,
  ...    organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    total_members=2,
  ...    total_collections=9,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...)

#### list

```python
def list() -> list[Orbit]
```

List all orbits related to default organization.

**Returns**:

  List of Orbits objects.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; orgs = dfs.orbits.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     Orbit(
  ...         id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...         name=&quot;Default Orbit&quot;,
  ...         organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...         bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...         total_members=2,
  ...         total_collections=9,
  ...         created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...         updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...     )
  ...]

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; orbit = dfs.orbits.create(
  ...     name=&quot;ML Models&quot;,
  ...     bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ... )
  
  Response object:
  &gt;&gt;&gt; Orbit(
  ...    id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    name=&quot;Default Orbit&quot;,
  ...    organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    total_members=2,
  ...    total_collections=9,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...)

#### update

```python
def update(name: str | None = None,
           bucket_secret_id: str | None = None) -> Orbit
```

Update default orbit configuration.

Updates current orbit&#x27;s name, bucket secret. Only provided
parameters will be updated, others remain unchanged.

**Arguments**:

- `name` - New name for the orbit. If None, name remains unchanged.
- `bucket_secret_id` - New bucket secret for storage configuration.
  The bucket secret must exist. If None, bucket secret remains unchanged.
  

**Returns**:

- `Orbit` - Updated orbit object.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; orbit = dfs.orbits.update(name=&quot;New Orbit Name&quot;)
  
  &gt;&gt;&gt; orbit = dfs.orbits.update(
  ...     name=&quot;New Orbit Name&quot;,
  ...     bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ... )
  
  Response object:
  &gt;&gt;&gt; Orbit(
  ...    id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    name=&quot;Default Orbit&quot;,
  ...    organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    total_members=2,
  ...    total_collections=9,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...)
  

**Notes**:

  This method updates the orbit set as default in the client.

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

- `DataForceAPIError` - If try to delete default orbit.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  ... dfs.orbits.delete(&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;)
  

**Warnings**:

  This operation is irreversible. All collections, models, and data
  within the orbit will be permanently lost. Consider backing up
  important data before deletion.

## AsyncOrbitResource

```python
class AsyncOrbitResource(OrbitResourceBase)
```

Resource for managing Orbits for async client.

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     orbit_by_name = await dfs.orbits.get(&quot;Default Orbit&quot;)
  ...     orbit_by_id = await dfs.orbits.get(
  ...         &quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ...     )
  
  Example response:
  &gt;&gt;&gt; Orbit(
  ...    id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    name=&quot;Default Orbit&quot;,
  ...    organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    total_members=2,
  ...    total_collections=9,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...)

#### list

```python
async def list() -> list[Orbit]
```

List all orbits related to default organization.

**Returns**:

  List of Orbits objects.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     orgs = await dfs.orbits.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     Orbit(
  ...         id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...         name=&quot;Default Orbit&quot;,
  ...         organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...         bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...         total_members=2,
  ...         total_collections=9,
  ...         created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...         updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...     )
  ...]

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     orbit = await dfs.orbits.create(
  ...         name=&quot;ML Models&quot;,
  ...         bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ...     )
  
  Response object:
  &gt;&gt;&gt; Orbit(
  ...    id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    name=&quot;Default Orbit&quot;,
  ...    organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    total_members=2,
  ...    total_collections=9,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...)

#### update

```python
async def update(name: str | None = None,
                 bucket_secret_id: str | None = None) -> Orbit
```

Update default orbit configuration.

Updates current orbit&#x27;s name, bucket secret. Only provided
parameters will be updated, others remain unchanged.

**Arguments**:

- `name` - New name for the orbit. If None, name remains unchanged.
- `bucket_secret_id` - New bucket secret for storage configuration.
  The bucket secret must exist. If None, bucket secret remains unchanged.
  

**Returns**:

- `Orbit` - Updated orbit object.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     orbit = await dfs.orbits.update(name=&quot;New Orbit Name&quot;)
  ...
  ...     orbit = await dfs.orbits.update(
  ...         name=&quot;New Orbit Name&quot;,
  ...         bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ...     )
  
  Response object:
  &gt;&gt;&gt; Orbit(
  ...    id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    name=&quot;Default Orbit&quot;,
  ...    organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    bucket_secret_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...    total_members=2,
  ...    total_collections=9,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...)
  

**Notes**:

  This method updates the orbit set as default in the client.

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

- `DataForceAPIError` - If try to delete default orbit.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     await dfs.orbits.delete(&quot;0199c475-8339-70ec-b032-7b3f5d59fdc1&quot;)
  

**Warnings**:

  This operation is irreversible. All collections, models, and data
  within the orbit will be permanently lost. Consider backing up
  important data before deletion.

