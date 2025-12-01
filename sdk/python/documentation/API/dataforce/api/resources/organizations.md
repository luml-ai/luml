---
sidebar_label: organizations
title: dataforce.api.resources.organizations
---

## OrganizationResourceBase

```python
class OrganizationResourceBase(ABC)
```

Abstract Resource for managing Organizations.

## OrganizationResource

```python
class OrganizationResource(OrganizationResourceBase)
```

Resource for managing organizations.

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

  &gt;&gt;&gt; dfs = DataForceClient(api_key=&quot;dfs_your_key&quot;)
  ... org_by_name = dfs.organizations.get(&quot;My Personal Company&quot;)
  ... org_by_id = dfs.organizations.get(
  ...     &quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;
  ... )
  
  Example response:
  &gt;&gt;&gt; Organization(
  ...    id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    name=&quot;My Personal Company&quot;,
  ...    logo=&#x27;https://example.com/&#x27;,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=None
  ...)

#### list

```python
def list() -> list[Organization]
```

List all organizations.

Retrieves all organizations available for user.

**Returns**:

  List of Organization objects.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(api_key=&quot;dfs_your_key&quot;)
  &gt;&gt;&gt; orgs = dfs.organizations.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     Organization(
  ...         id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...         name=&quot;My Personal Company&quot;,
  ...         logo=&#x27;https://example.com/&#x27;,
  ...         created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...         updated_at=None
  ...     )
  ...]

## AsyncOrganizationResource

```python
class AsyncOrganizationResource(OrganizationResourceBase)
```

Resource for managing organizations for async client.

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(api_key=&quot;dfs_your_key&quot;)
  &gt;&gt;&gt; async def main():
  ...     org_by_name = await dfs.organizations.get(&quot;my-company&quot;)
  ...     org_by_id = await dfs.organizations.get(123)
  
  Example response:
  &gt;&gt;&gt; Organization(
  ...    id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    name=&quot;My Personal Company&quot;,
  ...    logo=&#x27;https://example.com/&#x27;,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=None
  ...)

#### list

```python
async def list() -> list[Organization]
```

List all organizations.

Retrieves all organizations available for user.

**Returns**:

  List of Organization objects.
  

**Example**:

  &gt;&gt;&gt; dfs = AsyncDataForceClient(api_key=&quot;dfs_your_key&quot;)
  &gt;&gt;&gt; async def main():
  ...     orgs = await dfs.organizations.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     Organization(
  ...         id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...         name=&quot;My Personal Company&quot;,
  ...         logo=&#x27;https://example.com/&#x27;,
  ...         created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...         updated_at=None
  ...     )
  ...]

