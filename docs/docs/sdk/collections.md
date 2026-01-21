<a id="dataforce.api.resources.collections"></a>

# dataforce.api.resources.collections

<a id="dataforce.api.resources.collections.CollectionResource"></a>

## CollectionResource Objects

```python
class CollectionResource(CollectionResourceBase)
```

<a id="dataforce.api.resources.collections.CollectionResource.get"></a>

#### get

```python
@validate_collection
def get(collection_value: str | None = None) -> Collection | None
```

Get collection by id or name.

Retrieves collection details by its id or name.
Collection is related to default orbit.
Search by name is case-sensitive and matches exact collection name.

**Arguments**:

- `collection_value` - The exact id or name of the collection to retrieve.
  

**Returns**:

  Collection object.
  
  Returns None if collection with the specified name or id is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - If there are several collections
  with that name / id.
  

**Example**:

```python
    dfs = DataForceClient(api_key="dfs_your_key")
    collection_by_name = dfs.collections.get("My Collection")
    collection_by_id = dfs.collections.get
    (
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
```
  
  Example response:
```python
    Collection(
        id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        name="My Collection",
        description="Dataset for ML models",
        collection_type='model',
        orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
        tags=["ml", "training"],
        created_at='2025-01-15T10:30:00.123456Z',
        updated_at=None
        )
```

<a id="dataforce.api.resources.collections.CollectionResource.list"></a>

#### list

```python
def list() -> list[Collection]
```

List all collections in the default orbit.

**Returns**:

  List of Collection objects.
  

**Example**:

```python
    dfs = DataForceClient(api_key="dfs_your_key")
    collections = dfs.collections.list()
```
  
  Example response:
    ``` python
    Collection(
        id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        name="My Collection",
        description="Dataset for ML models",
        collection_type='model',
        orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
        tags=["ml", "training"],
        created_at='2025-01-15T10:30:00.123456Z',
        updated_at=None
        )
    ```

<a id="dataforce.api.resources.collections.CollectionResource.create"></a>

#### create

```python
def create(description: str,
           name: str,
           collection_type: CollectionType,
           tags: builtins.list[str] | None = None) -> Collection
```

Create new collection in the default orbit.

**Arguments**:

- `description` - Description of the collection.
- `name` - Name of the collection.
- `collection_type` - Type of collection: "model", "dataset".
- `tags` - Optional list of tags for organizing collections.
  

**Returns**:

- `Collection` - Created collection object.
  

**Example**:

``` python
    dfs = DataForceClient(api_key="dfs_your_key")
    collection = dfs.collections.create(
        name="Training Dataset",
        description="Dataset for model training",
        collection_type=CollectionType.DATASET,
        tags=["ml", "training"]
        )
```
  
  Response object:
``` python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="Training Dataset",
    description="Dataset for model training",
    collection_type='model',
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    tags=["ml", "training"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="dataforce.api.resources.collections.CollectionResource.update"></a>

#### update

```python
@validate_collection
def update(name: str | None = None,
           description: str | None = None,
           tags: builtins.list[str] | None = None,
           *,
           collection_id: str | None = None) -> Collection
```

Update collection by ID or use default collection if collection_id not provided.

Updates the collection's data. Only provided parameters will be
updated, others remain unchanged. If collection_id is None,
the default collection from client will be used.

**Arguments**:

- `name` - New name for the collection.
- `description` - New description for the collection.
- `tags` - New list of tags.
- `collection_id` - ID of the collection to update. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `Collection` - Updated collection object.
  

**Example**:

```python
dfs = DataForceClient(
api_key="dfs_your_key",
organization="0199c455-21ec-7c74-8efe-41470e29bae5",
orbit="0199c455-21ed-7aba-9fe5-5231611220de"
)
collection = dfs.collections.update(
collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
name="Updated Dataset",
tags=["ml", "updated"]
)

dfs.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
collection = dfs.collections.update(
name="Updated Dataset",
description="Updated description"
)
    ```
  
  Response object:
```python
Collection(
        id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
        description="Updated description",
        name="Updated Dataset",
        collection_type='model',
        tags=["ml", "updated"],
        total_models=43,
        created_at='2025-01-15T10:30:00.123456Z',
        updated_at='2025-01-15T14:22:30.987654Z'
    )
```

<a id="dataforce.api.resources.collections.CollectionResource.delete"></a>

#### delete

```python
@validate_collection
def delete(collection_id: str | None = None) -> None
```

Delete collection by ID or use default collection if collection_id not provided.

Permanently removes the collection and all its models.
This action cannot be undone.
If collection_id is None, the default collection from client will be used.

**Arguments**:

- `collection_id` - ID of the collection to delete. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `None` - No return value on successful deletion.
  

**Example**:

```python
dfs = DataForceClient(
    api_key="dfs_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de"
    )
# Delete specific collection by ID
dfs.collections.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")

# Set default collection
dfs.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
# Delete default collection (collection_id will be autofilled)
dfs.collections.delete()
```
  

**Warnings**:

  This operation is irreversible. All models, datasets, and data
  within the collection will be permanently lost. Consider backing up
  important data before deletion.

<a id="dataforce.api.resources.collections.AsyncCollectionResource"></a>

## AsyncCollectionResource Objects

```python
class AsyncCollectionResource(CollectionResourceBase)
```

<a id="dataforce.api.resources.collections.AsyncCollectionResource.get"></a>

#### get

```python
@validate_collection
async def get(collection_value: str | None = None) -> Collection | None
```

Get collection by id or name.

Retrieves collection details by its id or name.
Collection is related to default orbit.
Search by name is case-sensitive and matches exact collection name.

**Arguments**:

- `collection_value` - The exact id or name of the collection to retrieve.
  

**Returns**:

  Collection object.
  
  Returns None if collection with the specified name or id is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - If there are several collections
  with that name / id.
  

**Example**:

```python
dfs = AsyncDataForceClient(api_key="dfs_your_key")
async def main():
    collection_by_name = await dfs.collections.get(
        "My Collection"
    )
    collection_by_id = await dfs.collections.get(
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
```
  
  Example response:
```python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="My Collection",
    description="Dataset for ML models",
    collection_type='model',
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    tags=["ml", "training"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="dataforce.api.resources.collections.AsyncCollectionResource.list"></a>

#### list

```python
async def list() -> list[Collection]
```

List all collections in the default orbit.

**Returns**:

  List of Collection objects.
  

**Example**:

```python
dfs = AsyncDataForceClient(api_key="dfs_your_key")
async def main():
    collections = await dfs.collections.list()
```
  
  Example response:
```python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="My Collection",
    description="Dataset for ML models",
    collection_type='model',
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    tags=["ml", "training"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="dataforce.api.resources.collections.AsyncCollectionResource.create"></a>

#### create

```python
async def create(description: str,
                 name: str,
                 collection_type: CollectionType,
                 tags: builtins.list[str] | None = None) -> Collection
```

Create new collection in the default orbit.

**Arguments**:

- `description` - Description of the collection.
- `name` - Name of the collection.
- `collection_type` - Type of collection: "model", "dataset".
- `tags` - Optional list of tags for organizing collections.
  

**Returns**:

- `Collection` - Created collection object.
  

**Example**:

```python
dfs = AsyncDataForceClient(api_key="dfs_your_key")
async def main():
    collection = await dfs.collections.create(
        name="Training Dataset",
        description="Dataset for model training",
        collection_type=CollectionType.DATASET,
        tags=["ml", "training"]
    )
```
  
  Response object:
```python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="Training Dataset",
    description="Dataset for model training",
    collection_type='model',
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    tags=["ml", "training"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="dataforce.api.resources.collections.AsyncCollectionResource.update"></a>

#### update

```python
@validate_collection
async def update(name: str | None = None,
                 description: str | None = None,
                 tags: builtins.list[str] | None = None,
                 *,
                 collection_id: str | None = None) -> Collection
```

Update collection by ID or use default collection if collection_id not provided.

Updates the collection's data. Only provided parameters will be
updated, others remain unchanged. If collection_id is None,
the default collection from client will be used.

**Arguments**:

- `name` - New name for the collection.
- `description` - New description for the collection.
- `tags` - New list of tags.
- `collection_id` - ID of the collection to update. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `Collection` - Updated collection object.
  

**Example**:

```python
dfs = AsyncDataForceClient(
    api_key="dfs_your_key",
)
dfs.setup_config(
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
async def main():
    collection = await dfs.collections.update(
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        name="Updated Dataset",
        tags=["ml", "updated"]
    )

    dfs.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
    collection = await dfs.collections.update(
        name="Updated Dataset",
        description="Updated description"
    )
```
  
  Response object:
```python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    description="Updated description",
    name="Updated Dataset",
    collection_type='model',
    tags=["ml", "updated"],
    total_models=43,
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at='2025-01-15T14:22:30.987654Z'
)
```

<a id="dataforce.api.resources.collections.AsyncCollectionResource.delete"></a>

#### delete

```python
@validate_collection
async def delete(collection_id: str | None = None) -> None
```

Delete collection by ID or use default collection if collection_id not provided.

Permanently removes the collection and all its models.
This action cannot be undone.
If collection_id is None, the default collection from client will be used.

**Arguments**:

- `collection_id` - ID of the collection to delete. If not provided,
  uses the default collection set in the client.
  

**Returns**:

- `None` - No return value on successful deletion.
  

**Example**:

```python
dfs = AsyncDataForceClient(
    api_key="dfs_your_key",
)
dfs.setup_config(
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
)
async def main():
    # Delete specific collection by ID
    await dfs.collections.delete(
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )

    # Set default collection
    dfs.collection = "0199c455-21ee-74c6-b747-19a82f1a1e56"
    # Delete default collection
    await dfs.collections.delete()
```
  

**Warnings**:

  This operation is irreversible. All models, datasets, and data
  within the collection will be permanently lost. Consider backing up
  important data before deletion.

