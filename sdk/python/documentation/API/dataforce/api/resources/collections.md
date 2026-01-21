---
sidebar_label: collections
title: dataforce.api.resources.collections
---

## CollectionResourceBase

```python
class CollectionResourceBase(ABC)
```

Abstract Resource for managing Collections.

## CollectionResource

```python
class CollectionResource(CollectionResourceBase)
```

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

  &gt;&gt;&gt; dfs = DataForceClient(api_key=&quot;dfs_your_key&quot;)
  ... collection_by_name = dfs.collections.get(&quot;My Collection&quot;)
  ... collection_by_id = dfs.collections.get(
  ...     &quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  
  Example response:
  &gt;&gt;&gt; Collection(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     name=&quot;My Collection&quot;,
  ...     description=&quot;Dataset for ML models&quot;,
  ...     collection_type=&#x27;model&#x27;,
  ...     orbit_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     tags=[&quot;ml&quot;, &quot;training&quot;],
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=None
  ... )

#### list

```python
def list() -> list[Collection]
```

List all collections in the default orbit.

**Returns**:

  List of Collection objects.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(api_key=&quot;dfs_your_key&quot;)
  &gt;&gt;&gt; collections = dfs.collections.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     Collection(
  ...         id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...         name=&quot;My Collection&quot;,
  ...         description=&quot;Dataset for ML models&quot;,
  ...         collection_type=&#x27;model&#x27;,
  ...         orbit_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...         tags=[&quot;ml&quot;, &quot;training&quot;],
  ...         created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...         updated_at=None
  ...     )
  ... ]

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
- `collection_type` - Type of collection: &quot;model&quot;, &quot;dataset&quot;.
- `tags` - Optional list of tags for organizing collections.
  

**Returns**:

- `Collection` - Created collection object.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(api_key=&quot;dfs_your_key&quot;)
  &gt;&gt;&gt; collection = dfs.collections.create(
  ...     name=&quot;Training Dataset&quot;,
  ...     description=&quot;Dataset for model training&quot;,
  ...     collection_type=CollectionType.DATASET,
  ...     tags=[&quot;ml&quot;, &quot;training&quot;]
  ... )
  
  Response object:
  &gt;&gt;&gt; Collection(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     name=&quot;Training Dataset&quot;,
  ...     description=&quot;Dataset for model training&quot;,
  ...     collection_type=&#x27;model&#x27;,
  ...     orbit_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     tags=[&quot;ml&quot;, &quot;training&quot;],
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=None
  ... )

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

Updates the collection&#x27;s data. Only provided parameters will be
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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ... )
  &gt;&gt;&gt; collection = dfs.collections.update(
  ...     collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     name=&quot;Updated Dataset&quot;,
  ...     tags=[&quot;ml&quot;, &quot;updated&quot;]
  ... )
  
  &gt;&gt;&gt; dfs.collection = &quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  &gt;&gt;&gt; collection = dfs.collections.update(
  ...     name=&quot;Updated Dataset&quot;,
  ...     description=&quot;Updated description&quot;
  ... )
  
  Response object:
  &gt;&gt;&gt; Collection(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     orbit_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     description=&quot;Updated description&quot;,
  ...     name=&quot;Updated Dataset&quot;,
  ...     collection_type=&#x27;model&#x27;,
  ...     tags=[&quot;ml&quot;, &quot;updated&quot;],
  ...     total_models=43,
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=&#x27;2025-01-15T14:22:30.987654Z&#x27;
  ... )

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;
  ... )
  ... # Delete specific collection by ID
  ... dfs.collections.delete(&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;)
  
  ...  # Set default collection
  ... dfs.collection = &quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... # Delete default collection (collection_id will be autofilled)
  ... dfs.collections.delete()
  

**Warnings**:

  This operation is irreversible. All models, datasets, and data
  within the collection will be permanently lost. Consider backing up
  important data before deletion.

## AsyncCollectionResource

```python
class AsyncCollectionResource(CollectionResourceBase)
```

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(api_key=&quot;dfs_your_key&quot;)
  &gt;&gt;&gt; async def main():
  ...     collection_by_name = await dfs.collections.get(
  ...         &quot;My Collection&quot;
  ...     )
  ...     collection_by_id = await dfs.collections.get(
  ...         &quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ...     )
  
  Example response:
  &gt;&gt;&gt; Collection(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     name=&quot;My Collection&quot;,
  ...     description=&quot;Dataset for ML models&quot;,
  ...     collection_type=&#x27;model&#x27;,
  ...     orbit_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     tags=[&quot;ml&quot;, &quot;training&quot;],
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=None
  ... )

#### list

```python
async def list() -> list[Collection]
```

List all collections in the default orbit.

**Returns**:

  List of Collection objects.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(api_key=&quot;dfs_your_key&quot;)
  &gt;&gt;&gt; async def main():
  ...     collections = await dfs.collections.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     Collection(
  ...         id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...         name=&quot;My Collection&quot;,
  ...         description=&quot;Dataset for ML models&quot;,
  ...         collection_type=&#x27;model&#x27;,
  ...         orbit_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...         tags=[&quot;ml&quot;, &quot;training&quot;],
  ...         created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...         updated_at=None
  ...     )
  ... ]

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
- `collection_type` - Type of collection: &quot;model&quot;, &quot;dataset&quot;.
- `tags` - Optional list of tags for organizing collections.
  

**Returns**:

- `Collection` - Created collection object.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(api_key=&quot;dfs_your_key&quot;)
  &gt;&gt;&gt; async def main():
  ...     collection = await dfs.collections.create(
  ...         name=&quot;Training Dataset&quot;,
  ...         description=&quot;Dataset for model training&quot;,
  ...         collection_type=CollectionType.DATASET,
  ...         tags=[&quot;ml&quot;, &quot;training&quot;]
  ...     )
  
  Response object:
  &gt;&gt;&gt; Collection(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     name=&quot;Training Dataset&quot;,
  ...     description=&quot;Dataset for model training&quot;,
  ...     collection_type=&#x27;model&#x27;,
  ...     orbit_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     tags=[&quot;ml&quot;, &quot;training&quot;],
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=None
  ... )

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

Updates the collection&#x27;s data. Only provided parameters will be
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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ... )
  &gt;&gt;&gt; async def main():
  ...     collection = await dfs.collections.update(
  ...         collection_id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...         name=&quot;Updated Dataset&quot;,
  ...         tags=[&quot;ml&quot;, &quot;updated&quot;]
  ...     )
  ...
  ...     dfs.collection = &quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ...     collection = await dfs.collections.update(
  ...         name=&quot;Updated Dataset&quot;,
  ...         description=&quot;Updated description&quot;
  ...     )
  
  Response object:
  &gt;&gt;&gt; Collection(
  ...     id=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;,
  ...     orbit_id=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     description=&quot;Updated description&quot;,
  ...     name=&quot;Updated Dataset&quot;,
  ...     collection_type=&#x27;model&#x27;,
  ...     tags=[&quot;ml&quot;, &quot;updated&quot;],
  ...     total_models=43,
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=&#x27;2025-01-15T14:22:30.987654Z&#x27;
  ... )

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ... )
  &gt;&gt;&gt; async def main():
  ...     # Delete specific collection by ID
  ...     await dfs.collections.delete(
  ....        &quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ...     )
  ...
  ...     # Set default collection
  ...     dfs.collection = &quot;0199c455-21ee-74c6-b747-19a82f1a1e56&quot;
  ...     # Delete default collection
  ...     await dfs.collections.delete()
  

**Warnings**:

  This operation is irreversible. All models, datasets, and data
  within the collection will be permanently lost. Consider backing up
  important data before deletion.

