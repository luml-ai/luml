<a id="dataforce.api.resources.bucket_secrets"></a>

# dataforce.api.resources.bucket\_secrets

<a id="dataforce.api.resources.bucket_secrets.BucketSecretResource"></a>

## BucketSecretResource Objects

```python
class BucketSecretResource(BucketSecretResourceBase)
```

Resource for managing Bucket Secrets.

<a id="dataforce.api.resources.bucket_secrets.BucketSecretResource.get"></a>

#### get

```python
def get(secret_value: str) -> BucketSecret | None
```

Get BucketSecret by ID or bucket name.

Retrieves BucketSecret details by its ID or bucket name.
Search by name is case-sensitive and matches exact bucket name.

**Arguments**:

- `secret_value` - The ID or exact bucket name of the bucket secret to retrieve.
  

**Returns**:

  BucketSecret object.
  
  Returns None if bucket secret with the specified id or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - if there are several
  BucketSecret with that bucket name.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  ... bucket_by_name = dfs.bucket_secrets.get("default-bucket")
  ... bucket_by_id = dfs.bucket_secrets.get(
  ...     "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
  ...)
  
  Example response:
  >>> BucketSecret(
  ...    id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...    endpoint='default-endpoint',
  ...    bucket_name='default-bucket',
  ...    secure=None,
  ...    region=None,
  ...    cert_check=None,
  ...    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...    created_at='2025-05-21T19:35:17.340408Z',
  ...    updated_at='2025-08-13T22:44:58.035731Z'
  ...)

<a id="dataforce.api.resources.bucket_secrets.BucketSecretResource.list"></a>

#### list

```python
def list() -> list[BucketSecret]
```

List all bucket secrets in the default organization.

**Returns**:

  List of BucketSecret objects.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> secrets = dfs.bucket_secrets.list()
  
  Example response:
  >>> [
  ...     BucketSecret(
  ...         id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...         endpoint='default-endpoint',
  ...         bucket_name='default-bucket',
  ...         secure=None,
  ...         region=None,
  ...         cert_check=None,
  ...         organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...         created_at='2025-06-18T12:44:54.443715Z',
  ...         updated_at=None
  ...     )
  ...]

<a id="dataforce.api.resources.bucket_secrets.BucketSecretResource.create"></a>

#### create

```python
def create(endpoint: str,
           bucket_name: str,
           access_key: str | None = None,
           secret_key: str | None = None,
           session_token: str | None = None,
           secure: bool | None = None,
           region: str | None = None,
           cert_check: bool | None = None) -> BucketSecret
```

Create new bucket secret in the default organization.

**Arguments**:

- `endpoint` - S3-compatible storage endpoint URL (e.g., 's3.amazonaws.com').
- `bucket_name` - Name of the storage bucket.
- `access_key` - Access key for bucket authentication.
  Optional for some providers.
- `secret_key` - Secret key for bucket authentication.
  Optional for some providers.
- `session_token` - Temporary session token for authentication. Optional.
- `secure` - Use HTTPS for connections.Optional.
- `region` - Storage region identifier (e.g., 'us-east-1'). Optional.
- `cert_check` - Verify SSL certificates.Optional.
  

**Returns**:

- `BucketSecret` - Сreated bucket secret object.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> bucket_secret = dfs.bucket_secrets.create(
  ...     endpoint="s3.amazonaws.com",
  ...     bucket_name="my-data-bucket",
  ...     access_key="AKIAIOSFODNN7EXAMPLE",
  ...     secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  ...     region="us-east-1",
  ...     secure=True
  ... )
  
  Response object:
  >>> BucketSecret(
  ...     id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...     endpoint="s3.amazonaws.com",
  ...     bucket_name="my-data-bucket",
  ...     secure=True,
  ...     region="us-east-1",
  ...     cert_check=True,
  ...     organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     created_at='2025-01-15T10:30:00.123456Z',
  ...     updated_at=None
  ... )

<a id="dataforce.api.resources.bucket_secrets.BucketSecretResource.update"></a>

#### update

```python
def update(secret_id: str,
           endpoint: str | None = None,
           bucket_name: str | None = None,
           access_key: str | None = None,
           secret_key: str | None = None,
           session_token: str | None = None,
           secure: bool | None = None,
           region: str | None = None,
           cert_check: bool | None = None) -> BucketSecret
```

Update existing bucket secret.

Updates the bucket secret's. Only provided parameters will be
updated, others remain unchanged.

**Arguments**:

- `secret_id` - ID of the bucket secret to update.
- `endpoint` - S3-compatible storage endpoint URL (e.g., 's3.amazonaws.com').
- `bucket_name` - Name of the storage bucket.
- `access_key` - Access key for bucket authentication.
- `secret_key` - Secret key for bucket authentication.
- `session_token` - Temporary session token for authentication.
- `secure` - Use HTTPS for connections.
- `region` - Storage region identifier (e.g., 'us-east-1').
- `cert_check` - Verify SSL certificates.
  

**Returns**:

- `BucketSecret` - Updated bucket secret object.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> bucket_secret = dfs.bucket_secrets.update(
  ...     secret_id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...     endpoint="s3.amazonaws.com",
  ...     bucket_name="updated-bucket",
  ...     region="us-west-2",
  ...     secure=True
  ... )
  
  Response object:
  >>> BucketSecret(
  ...     id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...     endpoint="s3.amazonaws.com",
  ...     bucket_name="updated-bucket",
  ...     secure=True,
  ...     region="us-west-2",
  ...     cert_check=True,
  ...     organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     created_at='2025-01-15T10:30:00.123456Z',
  ...     updated_at='2025-01-15T14:22:30.987654Z'
  ... )

<a id="dataforce.api.resources.bucket_secrets.BucketSecretResource.delete"></a>

#### delete

```python
def delete(secret_id: str) -> None
```

Delete bucket secret permanently.

Permanently removes the bucket secret from the organization. This action
cannot be undone. Any orbits using this bucket secret will lose access
to their storage.

**Arguments**:

- `secret_id` - ID of the bucket secret to delete.
  

**Returns**:

- `None` - No return value on successful deletion.
  

**Example**:

  >>> dfs = DataForceClient(
  ...     api_key="dfs_your_key",
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> dfs.bucket_secrets.delete("0199c455-21f2-7131-9a20-da66246845c7")
  

**Warnings**:

  This operation is irreversible. Orbits using this bucket secret
  will lose access to their storage. Ensure no active orbits depend
  on this bucket secret before deletion.

<a id="dataforce.api.resources.bucket_secrets.AsyncBucketSecretResource"></a>

## AsyncBucketSecretResource Objects

```python
class AsyncBucketSecretResource(BucketSecretResourceBase)
```

Resource for managing Bucket Secrets for async client.

<a id="dataforce.api.resources.bucket_secrets.AsyncBucketSecretResource.get"></a>

#### get

```python
async def get(secret_value: str) -> BucketSecret | None
```

Get BucketSecret by ID or bucket name.

Retrieves BucketSecret details by its ID or bucket name.
Search by name is case-sensitive and matches exact bucket name.

**Arguments**:

- `secret_value` - The ID or exact bucket name of the bucket secret to retrieve.
  

**Returns**:

  BucketSecret object.
  
  Returns None if bucket secret with the specified id or name is not found.
  

**Raises**:

- `MultipleResourcesFoundError` - if there are several
  BucketSecret with that bucket name.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     bucket_by_name = await dfs.bucket_secrets.get("default-bucket")
  ...     bucket_by_id = await dfs.bucket_secrets.get(
  ...         "0199c45c-1b0b-7c82-890d-e31ab10d1e5d"
  ...     )
  
  Example response:
  >>> BucketSecret(
  ...         id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...         endpoint='default-endpoint',
  ...         bucket_name='default-bucket',
  ...         secure=None,
  ...         region=None,
  ...         cert_check=None,
  ...         organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...         created_at='2025-05-21T19:35:17.340408Z',
  ...         updated_at='2025-08-13T22:44:58.035731Z'
  ... )

<a id="dataforce.api.resources.bucket_secrets.AsyncBucketSecretResource.list"></a>

#### list

```python
async def list() -> list[BucketSecret]
```

List all bucket secrets in the default organization.

**Returns**:

  List of BucketSecret objects.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     secrets = await dfs.bucket_secrets.list()
  
  Example response:
  >>> [
  ...     BucketSecret(
  ...         id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...         endpoint='default-endpoint',
  ...         bucket_name='default-bucket',
  ...         secure=None,
  ...         region=None,
  ...         cert_check=None,
  ...         organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...         created_at='2025-06-18T12:44:54.443715Z',
  ...         updated_at=None
  ...     )
  ...]

<a id="dataforce.api.resources.bucket_secrets.AsyncBucketSecretResource.create"></a>

#### create

```python
async def create(endpoint: str,
                 bucket_name: str,
                 access_key: str | None = None,
                 secret_key: str | None = None,
                 session_token: str | None = None,
                 secure: bool | None = None,
                 region: str | None = None,
                 cert_check: bool | None = None) -> BucketSecret
```

Create new bucket secret in the default organization.

**Arguments**:

- `endpoint` - S3-compatible storage endpoint URL (e.g., 's3.amazonaws.com').
- `bucket_name` - Name of the storage bucket.
- `access_key` - Access key for bucket authentication.
  Optional for some providers.
- `secret_key` - Secret key for bucket authentication.
  Optional for some providers.
- `session_token` - Temporary session token for authentication. Optional.
- `secure` - Use HTTPS for connections.Optional.
- `region` - Storage region identifier (e.g., 'us-east-1'). Optional.
- `cert_check` - Verify SSL certificates.Optional.
  

**Returns**:

- `BucketSecret` - Сreated bucket secret object.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     bucket_secret = await dfs.bucket_secrets.create(
  ...         endpoint="s3.amazonaws.com",
  ...         bucket_name="my-data-bucket",
  ...         access_key="AKIAIOSFODNN7EXAMPLE",
  ...         secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  ...         region="us-east-1",
  ...         secure=True
  ...     )
  
  Response object:
  >>> BucketSecret(
  ...     id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...     endpoint="s3.amazonaws.com",
  ...     bucket_name="my-data-bucket",
  ...     secure=True,
  ...     region="us-east-1",
  ...     cert_check=True,
  ...     organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     created_at='2025-01-15T10:30:00.123456Z',
  ...     updated_at=None
  ... )

<a id="dataforce.api.resources.bucket_secrets.AsyncBucketSecretResource.update"></a>

#### update

```python
async def update(secret_id: str,
                 endpoint: str | None = None,
                 bucket_name: str | None = None,
                 access_key: str | None = None,
                 secret_key: str | None = None,
                 session_token: str | None = None,
                 secure: bool | None = None,
                 region: str | None = None,
                 cert_check: bool | None = None) -> BucketSecret
```

Update existing bucket secret.

Updates the bucket secret's. Only provided parameters will be
updated, others remain unchanged.

**Arguments**:

- `secret_id` - ID of the bucket secret to update.
- `endpoint` - S3-compatible storage endpoint URL (e.g., 's3.amazonaws.com').
- `bucket_name` - Name of the storage bucket.
- `access_key` - Access key for bucket authentication.
- `secret_key` - Secret key for bucket authentication.
- `session_token` - Temporary session token for authentication.
- `secure` - Use HTTPS for connections.
- `region` - Storage region identifier (e.g., 'us-east-1').
- `cert_check` - Verify SSL certificates.
  

**Returns**:

- `BucketSecret` - Updated bucket secret object.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     bucket_secret = await dfs.bucket_secrets.update(
  ...         id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...         endpoint="s3.amazonaws.com",
  ...         bucket_name="updated-bucket",
  ...         region="us-west-2",
  ...         secure=True
  ...     )
  
  Response object:
  >>> BucketSecret(
  ...     id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
  ...     endpoint="s3.amazonaws.com",
  ...     bucket_name="updated-bucket",
  ...     secure=True,
  ...     region="us-west-2",
  ...     cert_check=True,
  ...     organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     created_at='2025-01-15T10:30:00.123456Z',
  ...     updated_at='2025-01-15T14:22:30.987654Z'
  ... )

<a id="dataforce.api.resources.bucket_secrets.AsyncBucketSecretResource.delete"></a>

#### delete

```python
async def delete(secret_id: str) -> None
```

Delete bucket secret permanently.

Permanently removes the bucket secret from the organization. This action
cannot be undone. Any orbits using this bucket secret will lose access
to their storage.

**Arguments**:

- `secret_id` - ID of the bucket secret to delete.
  

**Returns**:

- `None` - No return value on successful deletion.
  

**Example**:

  >>> dfs = AsyncDataForceClient(
  ...     api_key="dfs_your_key",
  ... )
  ... dfs.setup_config(
  ...     organization="0199c455-21ec-7c74-8efe-41470e29bae5",
  ...     orbit="0199c455-21ed-7aba-9fe5-5231611220de",
  ...     collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
  ... )
  >>> async def main():
  ...     await dfs.bucket_secrets.delete(
  ...         "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
  ...     )
  

**Warnings**:

  This operation is irreversible. Orbits using this bucket secret
  will lose access to their storage. Ensure no active orbits depend
  on this bucket secret before deletion.

