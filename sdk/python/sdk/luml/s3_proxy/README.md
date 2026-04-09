# S3 Proxy

A local S3-compatible HTTP server that stores files on the local filesystem. Implements the AWS S3 API (AWS Signature V4) and can be used as a drop-in replacement for cloud S3 during development and local deployments.

## Why

The LUML platform works with artifacts (models, datasets) through an S3-compatible storage backend. When cloud S3 is unavailable or local storage is preferred, S3 Proxy emulates S3 behavior: it accepts presigned URLs from the platform and saves files to disk.

## How it works

```
S3ProxyServer (HTTPServer)
├── stores files at: {storage_root}/{bucket}/{key}
├── multipart temp parts: {storage_root}/.multipart/{upload_id}/
├── validates AWS Signature V4 (Authorization header + presigned URLs)
└── S3ProxyHandler handles: GET, PUT, POST, DELETE, OPTIONS
```

All files are stored on disk in a plain directory. Bucket structure is reproduced via nested folders.

## Authentication

The proxy supports two modes:

**No credentials configured (default):**
Accepts any correctly formed AWS Signature V4 request. Suitable for local development — any access key / secret key pair works in the client.

**With credentials configured:**
Pass a `{access_key: secret_key}` dict. The proxy validates the signature and rejects requests with unknown keys.

Supported auth methods:
- `Authorization: AWS4-HMAC-SHA256 ...` header
- Presigned URL (`X-Amz-Signature` in query string)

## Running

### CLI

```bash
# Start with defaults (port 9000, ./s3_storage)
s3-proxy

# Or via python -m
python -m luml.s3_proxy

# With custom options
s3-proxy --port 9000 --storage /data/s3_storage --cors --debug
```

| Flag | Default | Description |
|---|---|---|
| `--port` | `9000` | Server port |
| `--storage` | `./s3_storage` | Root directory for file storage |
| `--cors` | disabled | Enable CORS (needed if a frontend talks directly to the proxy) |
| `--debug` | disabled | Verbose authentication logs |

### Programmatic (Python)

```python
from luml.s3_proxy import run_server

run_server(
    host="127.0.0.1",
    port=9000,
    storage_root="./s3_storage",
    cors_enabled=False,
    debug=False,
)
```

## Supported S3 operations

| Method | URL | Description |
|---|---|---|
| `GET` | `/{bucket}/{key}` | Download object (supports `Range` header for partial reads) |
| `PUT` | `/{bucket}/{key}` | Upload object (single-part) |
| `POST` | `/{bucket}/{key}?uploads` | Initiate multipart upload |
| `PUT` | `/{bucket}/{key}?uploadId=...&partNumber=N` | Upload a part |
| `POST` | `/{bucket}/{key}?uploadId=...` | Complete multipart upload |
| `DELETE` | `/{bucket}/{key}` | Delete object |
| `DELETE` | `/{bucket}/{key}?uploadId=...` | Abort multipart upload |
| `OPTIONS` | any | CORS preflight (only when `--cors` is set) |

Maximum file size: **5 TB**. Multipart parts are written to a temp directory in parallel and assembled into a single file on completion.

## Using with the LUML platform

### 1. Start the proxy

```bash
s3-proxy --port 9000 --storage ./s3_storage
```

### 2. Register a bucket secret in LUML

Add a bucket secret pointing to the proxy:

```python
from luml_api import LumlClient

luml = LumlClient(api_key="luml_your_key", organization="...", ...)

bucket_secret = luml.bucket_secrets.create(
    endpoint="http://localhost:9000",  # address of the running proxy
    bucket_name="my-local-bucket",     # any name
    region="us-east-1",                # any region (not validated by proxy)
    access_key="any-key",              # any value when no credentials are configured
    secret_key="any-secret",           # any value when no credentials are configured
    secure=False,
)
```

After this, all artifact uploads (models, datasets) through the platform will be saved to `./s3_storage/my-local-bucket/...`.

### 3. Assign the bucket secret to an orbit

Set the created `bucket_secret.id` in the orbit settings on the platform. The platform will generate presigned URLs pointing to `http://localhost:9000`, and the SDK/API will upload files through the proxy.

## Disk storage structure

```
s3_storage/
├── my-local-bucket/
│   ├── orbit-abc123/collection-def456/model-name.tar
│   └── orbit-abc123/collection-def456/dataset-name.tar
└── .multipart/
    └── <upload_id>/
        ├── part_1
        ├── part_2
        └── part_3
```

The `.multipart/` directory is created automatically during multipart uploads and deleted after completion or abort.

## Using with boto3 / AWS SDK

The proxy is fully compatible with boto3:

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="any-key",
    aws_secret_access_key="any-secret",
    region_name="us-east-1",
)

# Upload a file
s3.upload_file("model.tar", "my-local-bucket", "models/model.tar")

# Download a file
s3.download_file("my-local-bucket", "models/model.tar", "model_downloaded.tar")

# Generate a presigned URL
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": "my-local-bucket", "Key": "models/model.tar"},
    ExpiresIn=3600,
)
```

## Limitations

- Object listing (`GET /{bucket}`) is not implemented — returns `501 NotImplemented`.
- No object versioning support.
- No bucket management (`PUT /{bucket}`, `DELETE /{bucket}`).
- HTTP only — HTTPS is not supported.
- Single-threaded server (Python `HTTPServer`) — suitable for development, not for production under load.