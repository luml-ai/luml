<a id="dataforce.api.resources.organizations"></a>

# dataforce.api.resources.organizations

<a id="dataforce.api.resources.organizations.OrganizationResource"></a>

## OrganizationResource Objects

```python
class OrganizationResource(OrganizationResourceBase)
```

Resource for managing organizations.

<a id="dataforce.api.resources.organizations.OrganizationResource.get"></a>

#### get

```python
@validate_organization
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

  >>> dfs = DataForceClient(api_key="dfs_your_key")
  ... org_by_name = dfs.organizations.get("My Personal Company")
  ... org_by_id = dfs.organizations.get(
  ...     "0199c455-21ec-7c74-8efe-41470e29bae5"
  ... )
  
  Example response:
  >>> Organization(
  ...    id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...    name="My Personal Company",
  ...    logo='https://example.com/',
  ...    created_at='2025-05-21T19:35:17.340408Z',
  ...    updated_at=None
  ...)

<a id="dataforce.api.resources.organizations.OrganizationResource.list"></a>

#### list

```python
def list() -> list[Organization]
```

List all organizations.

Retrieves all organizations available for user.

**Returns**:

  List of Organization objects.
  

**Example**:

  >>> dfs = DataForceClient(api_key="dfs_your_key")
  >>> orgs = dfs.organizations.list()
  
  Example response:
  >>> [
  ...     Organization(
  ...         id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...         name="My Personal Company",
  ...         logo='https://example.com/',
  ...         created_at='2025-05-21T19:35:17.340408Z',
  ...         updated_at=None
  ...     )
  ...]

<a id="dataforce.api.resources.organizations.AsyncOrganizationResource"></a>

## AsyncOrganizationResource Objects

```python
class AsyncOrganizationResource(OrganizationResourceBase)
```

Resource for managing organizations for async client.

<a id="dataforce.api.resources.organizations.AsyncOrganizationResource.get"></a>

#### get

```python
@validate_organization
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

  >>> dfs = AsyncDataForceClient(api_key="dfs_your_key")
  >>> async def main():
  ...     org_by_name = await dfs.organizations.get("my-company")
  ...     org_by_id = await dfs.organizations.get(123)
  
  Example response:
  >>> Organization(
  ...    id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...    name="My Personal Company",
  ...    logo='https://example.com/',
  ...    created_at='2025-05-21T19:35:17.340408Z',
  ...    updated_at=None
  ...)

<a id="dataforce.api.resources.organizations.AsyncOrganizationResource.list"></a>

#### list

```python
async def list() -> list[Organization]
```

List all organizations.

Retrieves all organizations available for user.

**Returns**:

  List of Organization objects.
  

**Example**:

  >>> dfs = AsyncDataForceClient(api_key="dfs_your_key")
  >>> async def main():
  ...     orgs = await dfs.organizations.list()
  
  Example response:
  >>> [
  ...     Organization(
  ...         id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...         name="My Personal Company",
  ...         logo='https://example.com/',
  ...         created_at='2025-05-21T19:35:17.340408Z',
  ...         updated_at=None
  ...     )
  ...]

