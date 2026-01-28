<a id="luml.api.resources.organizations"></a>

# luml.api.resources.organizations

<a id="luml.api.resources.organizations.OrganizationResource"></a>

## OrganizationResource Objects

```python
class OrganizationResource(OrganizationResourceBase)
```

Resource for managing organizations.

<a id="luml.api.resources.organizations.OrganizationResource.get"></a>

#### get

```python
def get(organization_value: str | None = None) -> Organization | None
```

Get organization by name or ID.

Retrieves organization details by its name or ID.
Search by name is case-sensitive and matches exact organization names.

**Arguments**:

- `organization_value` - The exact name or ID of the organization to retrieve.
  

**Returns**:

  Organization object if found, None if organization
  with the specified name or ID is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - if there are several Organizations
  with that name.
  

**Example**:

```python
luml = LumlClient(api_key="luml_your_key")
org_by_name = luml.organizations.get("My Personal Company")
org_by_id = luml.organizations.get(
    "0199c455-21ec-7c74-8efe-41470e29bae5"
)
```
  
  Example response:
```python
Organization(
    id="0199c455-21ec-7c74-8efe-41470e29bae5",
    name="My Personal Company",
    logo='https://example.com/',
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at=None
)
```

<a id="luml.api.resources.organizations.OrganizationResource.list"></a>

#### list

```python
def list() -> list[Organization]
```

List all organizations.

Retrieves all organizations available for user.

**Returns**:

  List of Organization objects.
  

**Example**:

```python
luml = LumlClient(api_key="luml_your_key")
orgs = luml.organizations.list()
```
  
  Example response:
```python
[
    Organization(
        id="0199c455-21ec-7c74-8efe-41470e29bae5",
        name="My Personal Company",
        logo='https://example.com/',
        created_at='2025-05-21T19:35:17.340408Z',
        updated_at=None
    )
]
```

<a id="luml.api.resources.organizations.AsyncOrganizationResource"></a>

## AsyncOrganizationResource Objects

```python
class AsyncOrganizationResource(OrganizationResourceBase)
```

Resource for managing organizations for async client.

<a id="luml.api.resources.organizations.AsyncOrganizationResource.get"></a>

#### get

```python
async def get(organization_value: str | None = None) -> Organization | None
```

Get organization by name or ID.

Retrieves organization details by its name or ID.
Search by name is case-sensitive and matches exact organization names.

**Arguments**:

- `organization_value` - The exact name or ID of the organization to retrieve.
  

**Returns**:

  Organization object if found, None if organization
  with the specified name or ID is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - if there are several Organizations
  with that name.
  

**Example**:

```python
luml = AsyncLumlClient(api_key="luml_your_key")
async def main():
    org_by_name = await luml.organizations.get("my-company")
    org_by_id = await luml.organizations.get(
        "0199c455-21ec-7c74-8efe-41470e29ba45"
    )
```
  
  Example response:
```python
Organization(
    id="0199c455-21ec-7c74-8efe-41470e29bae5",
    name="My Personal Company",
    logo='https://example.com/',
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at=None
)
```

<a id="luml.api.resources.organizations.AsyncOrganizationResource.list"></a>

#### list

```python
async def list() -> list[Organization]
```

List all organizations.

Retrieves all organizations available for user.

**Returns**:

  List of Organization objects.
  

**Example**:

```python
luml = AsyncLumlClient(api_key="luml_your_key")
async def main():
    orgs = await luml.organizations.list()
```
  
  Example response:
```python
[
    Organization(
        id="0199c455-21ec-7c74-8efe-41470e29bae5",
        name="My Personal Company",
        logo='https://example.com/',
        created_at='2025-05-21T19:35:17.340408Z',
        updated_at=None
    )
]
```

