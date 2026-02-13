<a id="luml.api.resources.bucket_secrets"></a>

# luml.api.resources.bucket_secrets

<a id="luml.api.resources.bucket_secrets.BucketSecretResource"></a>

## BucketSecretResource Objects

```python
class BucketSecretResource(BucketSecretResourceBase)
```

Resource for managing Bucket Secrets.

<a id="luml.api.resources.bucket_secrets.BucketSecretResource.get"></a>

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

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
bucket_by_name = luml.bucket_secrets.get("default-bucket")
bucket_by_id = luml.bucket_secrets.get(
    "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
    )
```
  
  Example response:
```python
BucketSecret(
    id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
    endpoint='default-endpoint',
    bucket_name='default-bucket',
    secure=None,
    region=None,
    cert_check=None,
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    created_at='2025-05-21T19:35:17.340408Z',
    updated_at='2025-08-13T22:44:58.035731Z'
    )
```

<a id="luml.api.resources.bucket_secrets.BucketSecretResource.list"></a>

#### list

```python
def list() -> list[BucketSecret]
```

List all bucket secrets in the default organization.

**Returns**:

  List of BucketSecret objects.
  

**Example**:

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
secrets = luml.bucket_secrets.list()
```
  
  Example response:
```python
[
    BucketSecret(
        id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        endpoint='default-endpoint',
        bucket_name='default-bucket',
        secure=None,
        region=None,
        cert_check=None,
        organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
        created_at='2025-06-18T12:44:54.443715Z',
        updated_at=None
    )
]
```

<a id="luml.api.resources.bucket_secrets.BucketSecretResource.create"></a>

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

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
bucket_secret = luml.bucket_secrets.create(
    endpoint="s3.amazonaws.com",
    bucket_name="my-data-bucket",
    access_key="AKIAIOSFODNN7EXAMPLE",
    secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    region="us-east-1",
    secure=True
)
```
  
  Response object:
```python
BucketSecret(
    id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
    endpoint="s3.amazonaws.com",
    bucket_name="my-data-bucket",
    secure=True,
    region="us-east-1",
    cert_check=True,
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.bucket_secrets.BucketSecretResource.update"></a>

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

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
bucket_secret = luml.bucket_secrets.update(
    secret_id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
    endpoint="s3.amazonaws.com",
    bucket_name="updated-bucket",
    region="us-west-2",
    secure=True
)
```
  
  Response object:
```python
BucketSecret(
    id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
    endpoint="s3.amazonaws.com",
    bucket_name="updated-bucket",
    secure=True,
    region="us-west-2",
    cert_check=True,
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at='2025-01-15T14:22:30.987654Z'
)
```

<a id="luml.api.resources.bucket_secrets.BucketSecretResource.delete"></a>

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

```python
luml = LumlClient(
    api_key="luml_your_key",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
)
luml.bucket_secrets.delete("0199c455-21f2-7131-9a20-da66246845c7")
```
  

**Warnings**:

  This operation is irreversible. Orbits using this bucket secret
  will lose access to their storage. Ensure no active orbits depend
  on this bucket secret before deletion.

<a id="luml.api.resources.bucket_secrets.BucketSecretResource.get_multipart_upload_urls"></a>

#### get_multipart_upload_urls

```python
def get_multipart_upload_urls(
        bucket_id: str,
        bucket_location: str,
        size: int,
        upload_id: str | None = None) -> MultiPartUploadDetails
```

Get presigned URLs for multipart upload parts.

After initiating a multipart upload and receiving an upload_id,
use this method to get presigned URLs for uploading each part.

**Arguments**:

- `bucket_id` - ID of the bucket secret.
- `bucket_location` - Location/path in the bucket.
- `size` - Total file size in bytes.
- `upload_id` - Upload ID received from multipart initiation.
  

**Returns**:

  MultiPartUploadDetails with parts URLs and complete URL.
  
  

**Example**:

    ```python
    luml = AsyncDataForceClient(api_key="luml_your_key")

    async def main():
        await luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75")

        bucket_secret_id = "0199c45c-1b0b-7c82-890d-e31ab10d1e5d"
        bucket_location =
        "orbit-0199c455-21ed-7aba-9fe5-5231611220de/collection-0199c455-2
        1ee-74c6-b747-19a82f1a1e75/my_model_name"

        multipart_data = luml.bucket_secrets.get_multipart_upload_urls(
                bucket_secret_id,
                bucket_location,
                3874658765,
                "some_upload_id")
    ```

<a id="luml.api.resources.bucket_secrets.AsyncBucketSecretResource"></a>

## AsyncBucketSecretResource Objects

```python
class AsyncBucketSecretResource(BucketSecretResourceBase)
```

Resource for managing Bucket Secrets for async client.

<a id="luml.api.resources.bucket_secrets.AsyncBucketSecretResource.get"></a>

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

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
         organization="0199c455-21ec-7c74-8efe-41470e29bae5",
         orbit="0199c455-21ed-7aba-9fe5-5231611220de",
         collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    bucket_by_name = await luml.bucket_secrets.get("default-bucket")
    bucket_by_id = await luml.bucket_secrets.get(
        "0199c45c-1b0b-7c82-890d-e31ab10d1e5d"
    )
```
  
  Example response:
```python
BucketSecret(
        id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        endpoint='default-endpoint',
        bucket_name='default-bucket',
        secure=None,
        region=None,
        cert_check=None,
        organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
        created_at='2025-05-21T19:35:17.340408Z',
        updated_at='2025-08-13T22:44:58.035731Z'
)
```

<a id="luml.api.resources.bucket_secrets.AsyncBucketSecretResource.list"></a>

#### list

```python
async def list() -> list[BucketSecret]
```

List all bucket secrets in the default organization.

**Returns**:

  List of BucketSecret objects.
  

**Example**:

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    secrets = await luml.bucket_secrets.list()
```
  
  Example response:
```python
[
    BucketSecret(
        id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        endpoint='default-endpoint',
        bucket_name='default-bucket',
        secure=None,
        region=None,
        cert_check=None,
        organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
        created_at='2025-06-18T12:44:54.443715Z',
        updated_at=None
    )
]
```

<a id="luml.api.resources.bucket_secrets.AsyncBucketSecretResource.get_multipart_upload_urls"></a>

#### get_multipart_upload_urls

```python
async def get_multipart_upload_urls(
        bucket_id: str,
        bucket_location: str,
        size: int,
        upload_id: str | None = None) -> MultiPartUploadDetails
```

Get presigned URLs for multipart upload parts.

After initiating a multipart upload and receiving an upload_id,
use this method to get presigned URLs for uploading each part.

**Arguments**:

- `bucket_id` - ID of the bucket secret.
- `bucket_location` - Location/path in the bucket.
- `size` - Total file size in bytes.
- `upload_id` - Upload ID received from multipart initiation.
  

**Returns**:

  MultiPartUploadDetails with parts URLs and complete URL.
  
  

**Example**:

    ```python
    luml = AsyncDataForceClient(api_key="luml_your_key")

    async def main():
        await luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75")

        bucket_secret_id = "0199c45c-1b0b-7c82-890d-e31ab10d1e5d"
        bucket_location =
        "orbit-0199c455-21ed-7aba-9fe5-5231611220de/collection-0199c
        455-21ee-74c6-b747-19a82f1a1e75/my_model_name"

        multipart_data = await luml.bucket_secrets.get_multipart_upload_urls(
                bucket_secret_id,
                bucket_location,
                3874658765,
                "some_upload_id")
    ```

<a id="luml.api.resources.bucket_secrets.AsyncBucketSecretResource.create"></a>

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

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
     )
    bucket_secret = await luml.bucket_secrets.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-data-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
        secure=True
    )
```
  
  Response object:
```python
BucketSecret(
    id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
    endpoint="s3.amazonaws.com",
    bucket_name="my-data-bucket",
    secure=True,
    region="us-east-1",
    cert_check=True,
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at=None
)
```

<a id="luml.api.resources.bucket_secrets.AsyncBucketSecretResource.update"></a>

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

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    bucket_secret = await luml.bucket_secrets.update(
        id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        endpoint="s3.amazonaws.com",
        bucket_name="updated-bucket",
        region="us-west-2",
        secure=True
    )
```
  
  Response object:
```python
BucketSecret(
    id="0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
    endpoint="s3.amazonaws.com",
    bucket_name="updated-bucket",
    secure=True,
    region="us-west-2",
    cert_check=True,
    organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
    created_at='2025-01-15T10:30:00.123456Z',
    updated_at='2025-01-15T14:22:30.987654Z'
)
```

<a id="luml.api.resources.bucket_secrets.AsyncBucketSecretResource.delete"></a>

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

```python
luml = AsyncLumlClient(
    api_key="luml_your_key",
)

async def main():
    await luml.setup_config(
        organization="0199c455-21ec-7c74-8efe-41470e29bae5",
        orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    await luml.bucket_secrets.delete(
        "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
    )
```
  

**Warnings**:

  This operation is irreversible. Orbits using this bucket secret
  will lose access to their storage. Ensure no active orbits depend
  on this bucket secret before deletion.

