## Artifact

*model* `Artifact(id, collection_id, file_name, name, description=None, extra_values, manifest, file_hash, file_index, bucket_location, size, unique_identifier, tags=None, status, type, created_at, updated_at=None)`

**Fields**

- **id** (*str*)
- **collection_id** (*str*)
- **file_name** (*str*)
- **name** (*str*)
- **description** (*str | None, optional*) – Defaults to `None`.
- **extra_values** (*dict*)
- **manifest** (*dict*)
- **file_hash** (*str*)
- **file_index** (*dict[str, tuple[int, int]]*)
- **bucket_location** (*str*)
- **size** (*int*)
- **unique_identifier** (*str*)
- **tags** (*list[str] | None, optional*) – Defaults to `None`.
- **status** (*str*)
- **type** (*ArtifactType*)
- **created_at** (*str*)
- **updated_at** (*str | None, optional*) – Defaults to `None`.

## ArtifactFileDetails

*model* `ArtifactFileDetails(file_name, extra_values, manifest, file_hash, file_index, size)`

**Fields**

- **file_name** (*str*)
- **extra_values** (*dict*)
- **manifest** (*dict*)
- **file_hash** (*str*)
- **file_index** (*dict[str, tuple[int, int]]*)
- **size** (*int*)

## ArtifactSortBy

*enum* `ArtifactSortBy`

**Members**

- **CREATED_AT** – `'created_at'`
- **NAME** – `'name'`
- **SIZE** – `'size'`
- **DESCRIPTION** – `'description'`
- **STATUS** – `'status'`
- **TYPE** – `'type'`

## ArtifactStatus

*enum* `ArtifactStatus`

**Members**

- **PENDING_UPLOAD** – `'pending_upload'`
- **UPLOADED** – `'uploaded'`
- **UPLOAD_FAILED** – `'upload_failed'`
- **DELETION_FAILED** – `'deletion_failed'`

## ArtifactType

*enum* `ArtifactType`

**Members**

- **MODEL** – `'model'`
- **EXPERIMENT** – `'experiment'`
- **DATASET** – `'dataset'`

## ArtifactsList

*model* `ArtifactsList(items, cursor=None)`

**Fields**

- **items** (*list[~T]*)
- **cursor** (*str | None, optional*) – Defaults to `None`.

## AzureBucketSecret

*model* `AzureBucketSecret(id, type=<BucketType.AZURE: 'azure'>, endpoint, bucket_name, organization_id, created_at, updated_at=None)`

**Fields**

- **id** (*str*)
- **type** (*Literal[<AZURE: 'azure'>], optional*) – Defaults to `<BucketType.AZURE: 'azure'>`.
- **endpoint** (*str*)
- **bucket_name** (*str*)
- **organization_id** (*str*)
- **created_at** (*str*)
- **updated_at** (*str | None, optional*) – Defaults to `None`.

## BucketMultipartUpload

*model* `BucketMultipartUpload(bucket_id, bucket_location, size, upload_id)`

**Fields**

- **bucket_id** (*str*)
- **bucket_location** (*str*)
- **size** (*int*)
- **upload_id** (*str*)

## BucketType

*enum* `BucketType`

**Members**

- **S3** – `'s3'`
- **AZURE** – `'azure'`

## Collection

*model* `Collection(id, orbit_id, description, name, type, tags=None, total_artifacts=0, created_at, updated_at=None)`

**Fields**

- **id** (*str*)
- **orbit_id** (*str*)
- **description** (*str*)
- **name** (*str*)
- **type** (*str*)
- **tags** (*list[str] | None, optional*) – Defaults to `None`.
- **total_artifacts** (*int, optional*) – Defaults to `0`.
- **created_at** (*str*)
- **updated_at** (*str | None, optional*) – Defaults to `None`.

## CollectionDetails

*model* `CollectionDetails(id, orbit_id, description, name, type, tags=None, total_artifacts=0, created_at, updated_at=None, artifacts_tags=None, artifacts_extra_values=None)`

**Fields**

- **id** (*str*)
- **orbit_id** (*str*)
- **description** (*str*)
- **name** (*str*)
- **type** (*str*)
- **tags** (*list[str] | None, optional*) – Defaults to `None`.
- **total_artifacts** (*int, optional*) – Defaults to `0`.
- **created_at** (*str*)
- **updated_at** (*str | None, optional*) – Defaults to `None`.
- **artifacts_tags** (*list[str] | None, optional*) – Defaults to `None`.
- **artifacts_extra_values** (*list[str] | None, optional*) – Defaults to `None`.

## CollectionSortBy

*enum* `CollectionSortBy`

**Members**

- **CREATED_AT** – `'created_at'`
- **NAME** – `'name'`
- **TYPE** – `'type'`
- **DESCRIPTION** – `'description'`
- **TOTAL_ARTIFACTS** – `'total_artifacts'`

## CollectionType

*enum* `CollectionType`

**Members**

- **MODEL** – `'model'`
- **DATASET** – `'dataset'`
- **EXPERIMENT** – `'experiment'`
- **MODEL_DATASET** – `'model_dataset'`
- **DATASET_EXPERIMENT** – `'dataset_experiment'`
- **MODEL_EXPERIMENT** – `'model_experiment'`
- **MIXED** – `'mixed'`

## CollectionTypeFilter

*enum* `CollectionTypeFilter`

**Members**

- **MODEL** – `'model'`
- **DATASET** – `'dataset'`
- **EXPERIMENT** – `'experiment'`
- **MIXED** – `'mixed'`

## CollectionsList

*model* `CollectionsList(items, cursor=None)`

**Fields**

- **items** (*list[~T]*)
- **cursor** (*str | None, optional*) – Defaults to `None`.

## CreatedArtifact

*model* `CreatedArtifact(upload_details, artifact)`

**Fields**

- **upload_details** (*UploadDetails*)
- **artifact** (*Artifact*)

## MultiPartUploadDetails

*model* `MultiPartUploadDetails(type, upload_id=None, parts, complete_url)`

**Fields**

- **type** (*BucketType*)
- **upload_id** (*str | None, optional*) – Defaults to `None`.
- **parts** (*list[PartDetails]*)
- **complete_url** (*str*)

## MultipartUploadInfo

*model* `MultipartUploadInfo(upload_id, parts_count, part_size)`

**Fields**

- **upload_id** (*str*)
- **parts_count** (*int*)
- **part_size** (*int*)

## Orbit

*model* `Orbit(id, name, organization_id, bucket_secret_id, total_members=None, total_collections=None, created_at, updated_at=None)`

**Fields**

- **id** (*str*)
- **name** (*str*)
- **organization_id** (*str*)
- **bucket_secret_id** (*str*)
- **total_members** (*int | None, optional*) – Defaults to `None`.
- **total_collections** (*int | None, optional*) – Defaults to `None`.
- **created_at** (*str*)
- **updated_at** (*str | None, optional*) – Defaults to `None`.

## Organization

*model* `Organization(id, name, logo=None, created_at, updated_at=None)`

**Fields**

- **id** (*str*)
- **name** (*str*)
- **logo** (*str | None, optional*) – Defaults to `None`.
- **created_at** (*str*)
- **updated_at** (*str | None, optional*) – Defaults to `None`.

## PartDetails

*model* `PartDetails(part_number, url, start_byte, end_byte, part_size)`

**Fields**

- **part_number** (*int*)
- **url** (*str*)
- **start_byte** (*int*)
- **end_byte** (*int*)
- **part_size** (*int*)

## S3BucketSecret

*model* `S3BucketSecret(id, type=<BucketType.S3: 's3'>, endpoint, bucket_name, secure=None, region, cert_check=None, organization_id, created_at, updated_at=None)`

**Fields**

- **id** (*str*)
- **type** (*Literal[<S3: 's3'>], optional*) – Defaults to `<BucketType.S3: 's3'>`.
- **endpoint** (*str*)
- **bucket_name** (*str*)
- **secure** (*bool | None, optional*) – Defaults to `None`.
- **region** (*str*)
- **cert_check** (*bool | None, optional*) – Defaults to `None`.
- **organization_id** (*str*)
- **created_at** (*str*)
- **updated_at** (*str | None, optional*) – Defaults to `None`.

## SortOrder

*enum* `SortOrder`

**Members**

- **ASC** – `'asc'`
- **DESC** – `'desc'`

## UploadDetails

*model* `UploadDetails(type, url=None, multipart=False, bucket_location, bucket_secret_id)`

**Fields**

- **type** (*BucketType*)
- **url** (*str | None, optional*) – Defaults to `None`.
- **multipart** (*bool, optional*) – Defaults to `False`.
- **bucket_location** (*str*)
- **bucket_secret_id** (*str*)
