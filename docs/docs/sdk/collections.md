<a id="luml.api.resources.collections"></a>

# luml.api.resources.collections

<a id="luml.api.resources.collections.CollectionResource"></a>

## CollectionResource Objects

```python
class CollectionResource(CollectionResourceBase, ListedResource)
```

<a id="luml.api.resources.collections.CollectionResource.get"></a>

#### get

```python
def get(collection_value: str | None = None) -> CollectionDetails | None
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
luml = LumlClient(api_key="luml_your_key")
collection_by_name = luml.collections.get("My Collection")
collection_by_id = luml.collections.get(
    "0199c455-21ee-74c6-b747-19a82f1a1e75"
)
```
  
  Example response:
```python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="My Collection",
    description="Dataset for ML models",
    type='model',
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    tags=["ml", "training"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.collections.CollectionResource.list_all"></a>

#### list\_all

```python
def list_all(
    *,
    limit: int | None = 100,
    sort_by: CollectionSortBy | None = None,
    order: SortOrder | None = SortOrder.DESC,
    search: str | None = None,
    types: list[CollectionTypeFilter] | None = None
) -> Iterator[Collection]
```

List all orbit collections with auto-paging.

**Arguments**:

- `limit` - Page size (default: 100).
- `sort_by` - Field to sort by. Options: name, description, created_at.
- `order` - Sort order - "asc" or "desc" (default: "desc").
- `search` - Search string to filter collections by name or tags.
- `types` - Filter by collection types: "model", "dataset", "experiment", "mixed".
  

**Returns**:

  Collection objects from all pages.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de"
)

for collection in luml.collections.list_all(limit=50):
    print(collection.id)

# Search by name or tags
for collection in luml.collections.list_all(search="model"):
    print(collection.name)

# Filter by collection types
for collection in luml.collections.list_all(
    types=[CollectionTypeFilter.MODEL, CollectionTypeFilter.DATASET]
):
    print(collection.name)
```

<a id="luml.api.resources.collections.CollectionResource.list"></a>

#### list

```python
def list(
    *,
    start_after: str | None = None,
    limit: int | None = 100,
    sort_by: CollectionSortBy | None = None,
    order: SortOrder | None = SortOrder.DESC,
    search: str | None = None,
    types: list[CollectionTypeFilter] | None = None
) -> CollectionsList
```

List all collections in the default orbit.

**Arguments**:

- `start_after` - Cursor to start listing from.
- `limit` - Maximum number of collections per page (default: 100).
- `sort_by` - Field to sort by. Options: name, description, created_at.
  If not provided, sorts by creation time.
- `order` - Sort order - "asc" or "desc" (default: "desc").
- `search` - Search string to filter collections by name or tags.
- `types` - Filter by collection types: "model", "dataset", "experiment", "mixed".
  

**Returns**:

  CollectionsList object with items and cursor.
  

**Example**:

```python
luml = LumlClient(api_key="luml_your_key")
result = luml.collections.list()
for collection in result.items:
    print(collection.name)

# Sort by name
result = luml.collections.list(
    sort_by=CollectionSortBy.NAME,
    order=SortOrder.ASC
)

# Search by name or tags
result = luml.collections.list(search="model")

# Filter by collection types
result = luml.collections.list(
    types=[CollectionTypeFilter.MODEL, CollectionTypeFilter.DATASET]
)
```
  
  Example response:
```python
CollectionsList(
    items=[
        Collection(
            id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="My Collection",
            description="Dataset for ML models",
            type='model',
            orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
            tags=["ml", "training"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
    ],
    cursor="WyIwMTliNDYxZmNmZDk3NTNhYjMwODJlMDUxZDkzZjVkZiIsICIyMDI1LTEyLTIyVDEyOjU0OjA4LjYwMTI5OCswMDowMCIsICJjcmVhdGVkX2F0Il0="
)
```

<a id="luml.api.resources.collections.CollectionResource.create"></a>

#### create

```python
def create(
    description: str,
    name: str,
    type: CollectionType,
    tags: List[str] | None = None
) -> Collection
```

Create new collection in the default orbit.

**Arguments**:

- `description` - Description of the collection.
- `name` - Name of the collection.
- `type` - Type of collection: "model", "dataset", "experiment",
  "model_dataset", "dataset_experiment", "model_experiment", "mixed".
- `tags` - Optional list of tags for organizing collections.
  

**Returns**:

- `Collection` - Created collection object.
  

**Example**:

```python
luml = LumlClient(api_key="luml_your_key")
collection = luml.collections.create(
    name="Training Dataset",
    description="Dataset for model training",
    type=CollectionType.DATASET,
    tags=["ml", "training"]
)
```
  
  Response object:
```python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="Training Dataset",
    description="Dataset for model training",
    type='model',
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    tags=["ml", "training"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.collections.CollectionResource.update"></a>

#### update

```python
@validate_collection
def update(
    name: str | None = None,
    description: str | None = None,
    tags: List[str] | None = None,
    *,
    collection_id: str | None = None
) -> Collection
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
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de"
)
collection = luml.collections.update(
    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="Updated Dataset",
    tags=["ml", "updated"]
)

luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
collection = luml.collections.update(
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
    type='model',
    tags=["ml", "updated"],
    total_artifacts=43,
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at='2025-01-15T14:22:30.987654Z'
)
```

<a id="luml.api.resources.collections.CollectionResource.delete"></a>

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
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de"
)
# Delete specific collection by ID
luml.collections.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")

# Set default collection
luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
# Delete default collection (collection_id will be autofilled)
luml.collections.delete()
```
  

**Warnings**:

  This operation is irreversible. All models, datasets, and data
  within the collection will be permanently lost. Consider backing up
  important data before deletion.

<a id="luml.api.resources.collections.AsyncCollectionResource"></a>

## AsyncCollectionResource Objects

```python
class AsyncCollectionResource(CollectionResourceBase, ListedResource)
```

<a id="luml.api.resources.collections.AsyncCollectionResource.get"></a>

#### get

```python
async def get(collection_value: str | None = None) -> CollectionDetails | None
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
luml = AsyncLumlClient(api_key="luml_your_key")
async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    collection_by_name = await luml.collections.get(
        "My Collection"
    )
    collection_by_id = await luml.collections.get(
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
```
  
  Example response:
```python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="My Collection",
    description="Dataset for ML models",
    type='model',
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    tags=["ml", "training"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.collections.AsyncCollectionResource.list_all"></a>

#### list\_all

```python
def list_all(
    *,
    limit: int | None = 100,
    sort_by: CollectionSortBy | None = None,
    order: SortOrder | None = SortOrder.DESC,
    search: str | None = None,
    types: list[CollectionTypeFilter] | None = None
) -> AsyncIterator[Collection]
```

List all orbit collections with auto-paging.

**Arguments**:

- `limit` - Page size (default: 100).
- `sort_by` - Field to sort by. Options: name, description, created_at.
- `order` - Sort order - "asc" or "desc" (default: "desc").
- `search` - Search string to filter collections by name or tags.
- `types` - Filter by collection types: "model", "dataset", "experiment", "mixed".
  

**Returns**:

  Collection objects from all pages.
  

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

    async for collection in luml.collections.list_all(limit=50):
        print(collection.id)

    # Search by name or tags
    async for collection in luml.collections.list_all(search="model"):
        print(collection.name)

    # Filter by collection types
    async for collection in luml.collections.list_all(
        types=[CollectionTypeFilter.MODEL, CollectionTypeFilter.DATASET]
    ):
        print(collection.name)
```

<a id="luml.api.resources.collections.AsyncCollectionResource.list"></a>

#### list

```python
async def list(
    *,
    start_after: str | None = None,
    limit: int | None = 100,
    sort_by: CollectionSortBy | None = None,
    order: SortOrder | None = SortOrder.DESC,
    search: str | None = None,
    types: list[CollectionTypeFilter] | None = None
) -> CollectionsList
```

List all collections in the default orbit.

**Arguments**:

- `start_after` - Cursor to start listing from.
- `limit` - Maximum number of collections per page (default: 100).
- `sort_by` - Field to sort by. Options: name, description, created_at.
  If not provided, sorts by creation time.
- `order` - Sort order - "asc" or "desc" (default: "desc").
- `search` - Search string to filter collections by name or tags.
- `types` - Filter by collection types: "model", "dataset", "experiment", "mixed".
  

**Returns**:

  CollectionsList object with items and cursor.
  

**Example**:

```python
luml = AsyncLumlClient(api_key="luml_your_key")
async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    result = await luml.collections.list()
    for collection in result.items:
        print(collection.name)

    # Sort by name
    result = await luml.collections.list(
        sort_by=CollectionSortBy.NAME,
        order=SortOrder.ASC
    )

    # Search by name or tags
    result = await luml.collections.list(search="model")

    # Filter by collection types
    result = await luml.collections.list(
        types=[CollectionTypeFilter.MODEL, CollectionTypeFilter.DATASET]
    )
```
  
  Example response:
```python
CollectionsList(
    items=[
        Collection(
            id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="My Collection",
            description="Dataset for ML models",
            type='model',
            orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
            tags=["ml", "training"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
    ],
    cursor="WyIwMTliNDYxZmNmZDk3NTNhYjMwODJlMDUxZDkzZjVkZiIsICIyMDI1LTEyLTIyVDEyOjU0OjA4LjYwMTI5OCswMDowMCIsICJjcmVhdGVkX2F0Il0="
)
```

<a id="luml.api.resources.collections.AsyncCollectionResource.create"></a>

#### create

```python
async def create(
    description: str,
    name: str,
    type: CollectionType,
    tags: List[str] | None = None
) -> Collection
```

Create new collection in the default orbit.

**Arguments**:

- `description` - Description of the collection.
- `name` - Name of the collection.
- `type` - Type of collection: "model", "dataset", "experiment",
  "model_dataset", "dataset_experiment", "model_experiment", "mixed".
- `tags` - Optional list of tags for organizing collections.
  

**Returns**:

- `Collection` - Created collection object.
  

**Example**:

```python
luml = AsyncLumlClient(api_key="luml_your_key")

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    collection = await luml.collections.create(
        name="Training Dataset",
        description="Dataset for model training",
        type=CollectionType.DATASET,
        tags=["ml", "training"]
    )
```
  
  Response object:
```python
Collection(
    id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    name="Training Dataset",
    description="Dataset for model training",
    type='model',
    orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
    tags=["ml", "training"],
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.collections.AsyncCollectionResource.update"></a>

#### update

```python
@validate_collection
async def update(
    name: str | None = None,
    description: str | None = None,
    tags: List[str] | None = None,
    *,
    collection_id: str | None = None
) -> Collection
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
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    collection = await luml.collections.update(
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        name="Updated Dataset",
        tags=["ml", "updated"]
    )

    luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
    collection = await luml.collections.update(
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
    type='model',
    tags=["ml", "updated"],
    total_artifacts=43,
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at='2025-01-15T14:22:30.987654Z'
)
```

<a id="luml.api.resources.collections.AsyncCollectionResource.delete"></a>

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
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    )

    # Delete specific collection by ID
    await luml.collections.delete(
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )

    # Set default collection
    luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e56"
    # Delete default collection
    await luml.collections.delete()
```
  

**Warnings**:

  This operation is irreversible. All models, datasets, and data
  within the collection will be permanently lost. Consider backing up
  important data before deletion.

