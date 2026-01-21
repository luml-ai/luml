---
sidebar_label: bucket_secrets
title: dataforce.api.resources.bucket_secrets
---

## BucketSecretResourceBase

```python
class BucketSecretResourceBase(ABC)
```

Abstract base class for bucket secret resource operations.

## BucketSecretResource

```python
class BucketSecretResource(BucketSecretResourceBase)
```

Resource for managing Bucket Secrets.

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  ... bucket_by_name = dfs.bucket_secrets.get(&quot;default-bucket&quot;)
  ... bucket_by_id = dfs.bucket_secrets.get(
  ...     &quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;
  ...)
  
  Example response:
  &gt;&gt;&gt; BucketSecret(
  ...    id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...    endpoint=&#x27;default-endpoint&#x27;,
  ...    bucket_name=&#x27;default-bucket&#x27;,
  ...    secure=None,
  ...    region=None,
  ...    cert_check=None,
  ...    organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...    created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...    updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ...)

#### list

```python
def list() -> list[BucketSecret]
```

List all bucket secrets in the default organization.

**Returns**:

  List of BucketSecret objects.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; secrets = dfs.bucket_secrets.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     BucketSecret(
  ...         id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...         endpoint=&#x27;default-endpoint&#x27;,
  ...         bucket_name=&#x27;default-bucket&#x27;,
  ...         secure=None,
  ...         region=None,
  ...         cert_check=None,
  ...         organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...         created_at=&#x27;2025-06-18T12:44:54.443715Z&#x27;,
  ...         updated_at=None
  ...     )
  ...]

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

- `endpoint` - S3-compatible storage endpoint URL (e.g., &#x27;s3.amazonaws.com&#x27;).
- `bucket_name` - Name of the storage bucket.
- `access_key` - Access key for bucket authentication.
  Optional for some providers.
- `secret_key` - Secret key for bucket authentication.
  Optional for some providers.
- `session_token` - Temporary session token for authentication. Optional.
- `secure` - Use HTTPS for connections.Optional.
- `region` - Storage region identifier (e.g., &#x27;us-east-1&#x27;). Optional.
- `cert_check` - Verify SSL certificates.Optional.
  

**Returns**:

- `BucketSecret` - Сreated bucket secret object.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; bucket_secret = dfs.bucket_secrets.create(
  ...     endpoint=&quot;s3.amazonaws.com&quot;,
  ...     bucket_name=&quot;my-data-bucket&quot;,
  ...     access_key=&quot;AKIAIOSFODNN7EXAMPLE&quot;,
  ...     secret_key=&quot;wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY&quot;,
  ...     region=&quot;us-east-1&quot;,
  ...     secure=True
  ... )
  
  Response object:
  &gt;&gt;&gt; BucketSecret(
  ...     id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...     endpoint=&quot;s3.amazonaws.com&quot;,
  ...     bucket_name=&quot;my-data-bucket&quot;,
  ...     secure=True,
  ...     region=&quot;us-east-1&quot;,
  ...     cert_check=True,
  ...     organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=None
  ... )

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

Updates the bucket secret&#x27;s. Only provided parameters will be
updated, others remain unchanged.

**Arguments**:

- `secret_id` - ID of the bucket secret to update.
- `endpoint` - S3-compatible storage endpoint URL (e.g., &#x27;s3.amazonaws.com&#x27;).
- `bucket_name` - Name of the storage bucket.
- `access_key` - Access key for bucket authentication.
- `secret_key` - Secret key for bucket authentication.
- `session_token` - Temporary session token for authentication.
- `secure` - Use HTTPS for connections.
- `region` - Storage region identifier (e.g., &#x27;us-east-1&#x27;).
- `cert_check` - Verify SSL certificates.
  

**Returns**:

- `BucketSecret` - Updated bucket secret object.
  

**Example**:

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; bucket_secret = dfs.bucket_secrets.update(
  ...     secret_id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...     endpoint=&quot;s3.amazonaws.com&quot;,
  ...     bucket_name=&quot;updated-bucket&quot;,
  ...     region=&quot;us-west-2&quot;,
  ...     secure=True
  ... )
  
  Response object:
  &gt;&gt;&gt; BucketSecret(
  ...     id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...     endpoint=&quot;s3.amazonaws.com&quot;,
  ...     bucket_name=&quot;updated-bucket&quot;,
  ...     secure=True,
  ...     region=&quot;us-west-2&quot;,
  ...     cert_check=True,
  ...     organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=&#x27;2025-01-15T14:22:30.987654Z&#x27;
  ... )

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

  &gt;&gt;&gt; dfs = DataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; dfs.bucket_secrets.delete(&quot;0199c455-21f2-7131-9a20-da66246845c7&quot;)
  

**Warnings**:

  This operation is irreversible. Orbits using this bucket secret
  will lose access to their storage. Ensure no active orbits depend
  on this bucket secret before deletion.

## AsyncBucketSecretResource

```python
class AsyncBucketSecretResource(BucketSecretResourceBase)
```

Resource for managing Bucket Secrets for async client.

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     bucket_by_name = await dfs.bucket_secrets.get(&quot;default-bucket&quot;)
  ...     bucket_by_id = await dfs.bucket_secrets.get(
  ...         &quot;0199c45c-1b0b-7c82-890d-e31ab10d1e5d&quot;
  ...     )
  
  Example response:
  &gt;&gt;&gt; BucketSecret(
  ...         id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...         endpoint=&#x27;default-endpoint&#x27;,
  ...         bucket_name=&#x27;default-bucket&#x27;,
  ...         secure=None,
  ...         region=None,
  ...         cert_check=None,
  ...         organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...         created_at=&#x27;2025-05-21T19:35:17.340408Z&#x27;,
  ...         updated_at=&#x27;2025-08-13T22:44:58.035731Z&#x27;
  ... )

#### list

```python
async def list() -> list[BucketSecret]
```

List all bucket secrets in the default organization.

**Returns**:

  List of BucketSecret objects.
  

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
  ...     secrets = await dfs.bucket_secrets.list()
  
  Example response:
  &gt;&gt;&gt; [
  ...     BucketSecret(
  ...         id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...         endpoint=&#x27;default-endpoint&#x27;,
  ...         bucket_name=&#x27;default-bucket&#x27;,
  ...         secure=None,
  ...         region=None,
  ...         cert_check=None,
  ...         organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...         created_at=&#x27;2025-06-18T12:44:54.443715Z&#x27;,
  ...         updated_at=None
  ...     )
  ...]

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

- `endpoint` - S3-compatible storage endpoint URL (e.g., &#x27;s3.amazonaws.com&#x27;).
- `bucket_name` - Name of the storage bucket.
- `access_key` - Access key for bucket authentication.
  Optional for some providers.
- `secret_key` - Secret key for bucket authentication.
  Optional for some providers.
- `session_token` - Temporary session token for authentication. Optional.
- `secure` - Use HTTPS for connections.Optional.
- `region` - Storage region identifier (e.g., &#x27;us-east-1&#x27;). Optional.
- `cert_check` - Verify SSL certificates.Optional.
  

**Returns**:

- `BucketSecret` - Сreated bucket secret object.
  

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
  ...     bucket_secret = await dfs.bucket_secrets.create(
  ...         endpoint=&quot;s3.amazonaws.com&quot;,
  ...         bucket_name=&quot;my-data-bucket&quot;,
  ...         access_key=&quot;AKIAIOSFODNN7EXAMPLE&quot;,
  ...         secret_key=&quot;wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY&quot;,
  ...         region=&quot;us-east-1&quot;,
  ...         secure=True
  ...     )
  
  Response object:
  &gt;&gt;&gt; BucketSecret(
  ...     id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...     endpoint=&quot;s3.amazonaws.com&quot;,
  ...     bucket_name=&quot;my-data-bucket&quot;,
  ...     secure=True,
  ...     region=&quot;us-east-1&quot;,
  ...     cert_check=True,
  ...     organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=None
  ... )

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

Updates the bucket secret&#x27;s. Only provided parameters will be
updated, others remain unchanged.

**Arguments**:

- `secret_id` - ID of the bucket secret to update.
- `endpoint` - S3-compatible storage endpoint URL (e.g., &#x27;s3.amazonaws.com&#x27;).
- `bucket_name` - Name of the storage bucket.
- `access_key` - Access key for bucket authentication.
- `secret_key` - Secret key for bucket authentication.
- `session_token` - Temporary session token for authentication.
- `secure` - Use HTTPS for connections.
- `region` - Storage region identifier (e.g., &#x27;us-east-1&#x27;).
- `cert_check` - Verify SSL certificates.
  

**Returns**:

- `BucketSecret` - Updated bucket secret object.
  

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
  ...     bucket_secret = await dfs.bucket_secrets.update(
  ...         id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...         endpoint=&quot;s3.amazonaws.com&quot;,
  ...         bucket_name=&quot;updated-bucket&quot;,
  ...         region=&quot;us-west-2&quot;,
  ...         secure=True
  ...     )
  
  Response object:
  &gt;&gt;&gt; BucketSecret(
  ...     id=&quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;,
  ...     endpoint=&quot;s3.amazonaws.com&quot;,
  ...     bucket_name=&quot;updated-bucket&quot;,
  ...     secure=True,
  ...     region=&quot;us-west-2&quot;,
  ...     cert_check=True,
  ...     organization_id=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     created_at=&#x27;2025-01-15T10:30:00.123456Z&#x27;,
  ...     updated_at=&#x27;2025-01-15T14:22:30.987654Z&#x27;
  ... )

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

  &gt;&gt;&gt; dfs = AsyncDataForceClient(
  ...     api_key=&quot;dfs_your_key&quot;,
  ... )
  ... dfs.setup_config(
  ...     organization=&quot;0199c455-21ec-7c74-8efe-41470e29bae5&quot;,
  ...     orbit=&quot;0199c455-21ed-7aba-9fe5-5231611220de&quot;,
  ...     collection=&quot;0199c455-21ee-74c6-b747-19a82f1a1e75&quot;
  ... )
  &gt;&gt;&gt; async def main():
  ...     await dfs.bucket_secrets.delete(
  ...         &quot;0199c455-21ef-79d9-9dfc-fec3d72bf4b5&quot;
  ...     )
  

**Warnings**:

  This operation is irreversible. Orbits using this bucket secret
  will lose access to their storage. Ensure no active orbits depend
  on this bucket secret before deletion.

