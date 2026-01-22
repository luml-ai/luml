import hashlib
import hmac
import os
import re
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from luml.s3_proxy.schemas import (
    CompleteMultipartUploadResponse,
    InitiateMultipartUploadResponse,
    MultipartUpload,
    PartInfo,
    S3ErrorResponse,
    S3Request,
)


class S3ProxyHandler(BaseHTTPRequestHandler):
    STORAGE_ROOT: str = "./s3_storage"  # Storage root directory
    CREDENTIALS: dict[str, str] = {}

    CORS_ENABLED: bool = False
    CORS_ORIGINS: str = "*"
    CORS_METHODS: str = "GET, PUT, POST, DELETE, HEAD, OPTIONS"
    CORS_HEADERS: str = "Authorization, Content-Type, Content-MD5, x-amz-*, Range"
    CORS_MAX_AGE: str = "3600"

    multipart_uploads: dict[str, MultipartUpload] = {}

    DEBUG: bool = False

    def __init__(self, *args, **kwargs) -> None:
        os.makedirs(self.STORAGE_ROOT, exist_ok=True)
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args) -> None:
        message = format % args if args else format
        if message.startswith("[AUTH]") and not self.DEBUG:
            return
        print(f"[{datetime.now().isoformat()}] {message}")

    def add_cors_headers(self) -> None:
        if self.CORS_ENABLED:
            self.send_header("Access-Control-Allow-Origin", self.CORS_ORIGINS)
            self.send_header("Access-Control-Allow-Methods", self.CORS_METHODS)
            self.send_header("Access-Control-Allow-Headers", self.CORS_HEADERS)
            self.send_header("Access-Control-Max-Age", self.CORS_MAX_AGE)
            self.send_header(
                "Access-Control-Expose-Headers", "ETag, Content-Range, Accept-Ranges"
            )

    def send_s3_response(
        self, code: int, body: str = "", content_type: str = "application/xml"
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body.encode())))
        self.send_header("Server", "S3Proxy/1.0")
        self.send_header("x-amz-request-id", os.urandom(16).hex())
        self.add_cors_headers()
        self.end_headers()
        if body:
            self.wfile.write(body.encode())

    def send_error_response(self, code: int, error_code: str, message: str) -> None:
        error = S3ErrorResponse(
            code=error_code,
            message=message,
            request_id=os.urandom(16).hex(),
        )
        self.send_s3_response(code, error.to_xml())

    def parse_s3_path(self) -> S3Request:
        parsed = urlparse(self.path)
        path_parts = [p for p in parsed.path.split("/") if p]
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        bucket = path_parts[0] if len(path_parts) > 0 else None
        key = "/".join(path_parts[1:]) if len(path_parts) > 1 else None

        query_dict = {
            k: v[0] if isinstance(v, list) else v for k, v in query_params.items()
        }

        return S3Request(
            bucket=bucket,
            key=unquote(key) if key else None,
            query_params=query_dict,
        )

    def get_file_path(self, bucket: str, key: str) -> Path:
        return Path(self.STORAGE_ROOT) / bucket / key

    @staticmethod
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(
        self, secret_key: str, date_stamp: str, region: str, service: str
    ) -> bytes:
        k_date = self._sign(f"AWS4{secret_key}".encode(), date_stamp)
        k_region = self._sign(k_date, region)
        k_service = self._sign(k_region, service)
        return self._sign(k_service, "aws4_request")

    def validate_signature_v4(self) -> tuple[bool, str | None]:
        auth_header = self.headers.get("Authorization", "")

        self.log_message(
            f"[AUTH] Authorization header: {auth_header[:100]}..."
            if len(auth_header) > 100
            else f"[AUTH] Authorization header: {auth_header}"
        )

        if not self.CREDENTIALS:
            self.log_message(
                "[AUTH] No credentials configured - "
                "accepting any valid signature format"
            )
            if not auth_header.startswith("AWS4-HMAC-SHA256"):
                self.log_message(
                    "[AUTH] REJECTED: Authorization header "
                    "does not start with AWS4-HMAC-SHA256"
                )
                return False, None
            pattern = r"AWS4-HMAC-SHA256 Credential=([^/]+)/"
            match = re.search(pattern, auth_header)
            if match:
                access_key = match.group(1)
                self.log_message(
                    f"[AUTH] ACCEPTED: Valid signature format "
                    f"with access key: {access_key}"
                )
                return True, access_key
            self.log_message(
                "[AUTH] REJECTED: Could not extract access key "
                "from authorization header"
            )
            return len(auth_header) > 0, None

        self.log_message("[AUTH] Credentials configured - performing strict validation")
        if not auth_header.startswith("AWS4-HMAC-SHA256"):
            self.log_message(
                "[AUTH] REJECTED: Authorization header "
                "does not start with AWS4-HMAC-SHA256"
            )
            return False, None

        try:
            pattern = r"AWS4-HMAC-SHA256 Credential=([^,]+), SignedHeaders=([^,]+), Signature=([a-f0-9]+)"
            match = re.match(pattern, auth_header)
            if not match:
                self.log_message(
                    "[AUTH] REJECTED: Could not parse authorization header"
                )
                return False, None

            credential, signed_headers, client_signature = match.groups()
            self.log_message(
                f"[AUTH] Parsed - Credential: {credential}, SignedHeaders: {signed_headers}, "
                f"ClientSignature: {client_signature[:16]}..."
            )

            cred_parts = credential.split("/")
            if len(cred_parts) != 5:
                self.log_message(
                    f"[AUTH] REJECTED: Invalid credential format "
                    f"(expected 5 parts, got {len(cred_parts)})"
                )
                return False, None

            access_key, date_stamp, region, service, _ = cred_parts
            self.log_message(
                f"[AUTH] Credential parts - AccessKey: {access_key}, "
                f"Date: {date_stamp}, Region: {region}, Service: {service}"
            )

            if access_key not in self.CREDENTIALS:
                self.log_message(f"[AUTH] REJECTED: Unknown access key: {access_key}")
                self.log_message(
                    f"[AUTH] Configured access keys: {list(self.CREDENTIALS.keys())}"
                )
                return False, access_key

            secret_key = self.CREDENTIALS[access_key]
            self.log_message(f"[AUTH] Found matching access key: {access_key}")

            x_amz_date = self.headers.get("x-amz-date", "")
            if not x_amz_date:
                date_header = self.headers.get("Date", "")
                if not date_header:
                    self.log_message(
                        "[AUTH] REJECTED: Missing x-amz-date or Date header"
                    )
                    return False, access_key
                self.log_message(f"[AUTH] Using Date header: {date_header}")
            else:
                self.log_message(f"[AUTH] Using x-amz-date header: {x_amz_date}")

            method = self.command
            canonical_uri = urlparse(self.path).path
            canonical_querystring = urlparse(self.path).query or ""

            self.log_message(
                f"[AUTH] Building canonical request - Method: {method}, "
                f"URI: {canonical_uri}, Query: {canonical_querystring}"
            )

            canonical_headers = []
            for header in signed_headers.split(";"):
                value = self.headers.get(header, "")
                canonical_headers.append(f"{header}:{value.strip()}")
            canonical_headers_str = "\n".join(canonical_headers) + "\n"

            self.log_message(f"[AUTH] Canonical headers: {canonical_headers}")

            payload_hash = self.headers.get("x-amz-content-sha256", "UNSIGNED-PAYLOAD")
            self.log_message(f"[AUTH] Payload hash: {payload_hash}")

            canonical_request = (
                f"{method}\n{canonical_uri}\n{canonical_querystring}\n"
                f"{canonical_headers_str}\n{signed_headers}\n{payload_hash}"
            )
            self.log_message(
                f"[AUTH] Canonical request (hash): "
                f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
            )

            algorithm = "AWS4-HMAC-SHA256"
            credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
            canonical_request_hash = hashlib.sha256(
                canonical_request.encode("utf-8")
            ).hexdigest()
            string_to_sign = (
                f"{algorithm}\n{x_amz_date}\n"
                f"{credential_scope}\n{canonical_request_hash}"
            )

            self.log_message("[AUTH] String to sign:")
            for i, line in enumerate(string_to_sign.split("\n")):
                self.log_message(f"[AUTH] Line {i}: {line}")

            signing_key = self._get_signature_key(
                secret_key, date_stamp, region, service
            )
            signature = hmac.new(
                signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
            ).hexdigest()

            self.log_message(f"[AUTH] Computed signature: {signature}")
            self.log_message(f"[AUTH] Client signature:   {client_signature}")

            if signature != client_signature:
                self.log_message(
                    f"[AUTH] REJECTED: Signature mismatch for access key: {access_key}"
                )
                return False, access_key

            self.log_message(
                f"[AUTH] ACCEPTED: Signature validated "
                f"successfully for access key: {access_key}"
            )
            return True, access_key

        except Exception as e:
            self.log_message(f"[AUTH] REJECTED: Signature validation error: {e}")
            import traceback

            self.log_message(f"[AUTH] Traceback: {traceback.format_exc()}")
            return False, None

    def validate_presigned_url(self) -> tuple[bool, str | None]:
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        if "X-Amz-Signature" not in query_params:
            return False, None

        self.log_message("[AUTH] Detected presigned URL request")

        try:
            credential = query_params.get("X-Amz-Credential", [""])[0]
            date = query_params.get("X-Amz-Date", [""])[0]
            expires = query_params.get("X-Amz-Expires", ["3600"])[0]

            self.log_message(
                f"[AUTH] Presigned - Credential: {credential}, "
                f"Date: {date}, Expires: {expires}s"
            )

            cred_parts = credential.split("/")
            if len(cred_parts) < 1:
                self.log_message("[AUTH] REJECTED: Invalid credential format")
                return False, None

            access_key = cred_parts[0]
            self.log_message(f"[AUTH] Presigned access key: {access_key}")

            if self.CREDENTIALS and access_key not in self.CREDENTIALS:
                self.log_message(f"[AUTH] REJECTED: Unknown access key: {access_key}")
                return False, access_key

            try:
                request_time = datetime.strptime(date, "%Y%m%dT%H%M%SZ")
                age_seconds = (datetime.now(UTC) - request_time).total_seconds()

                if age_seconds > int(expires):
                    self.log_message(
                        f"[AUTH] REJECTED: Presigned URL expired "
                        f"(age: {age_seconds}s, max: {expires}s)"
                    )
                    return False, access_key

                if age_seconds < 0:
                    self.log_message(
                        f"[AUTH] WARNING: Presigned URL "
                        f"from future (age: {age_seconds}s)"
                    )

                self.log_message(
                    f"[AUTH] Presigned URL age: {age_seconds}s / {expires}s"
                )
            except Exception as e:
                self.log_message(f"[AUTH] Warning: Could not check expiration: {e}")
                # Accept anyway

            return True, access_key

        except Exception as e:
            self.log_message(f"[AUTH] REJECTED: Presigned URL validation error: {e}")
            import traceback

            self.log_message(f"[AUTH] Traceback: {traceback.format_exc()}")
            return False, None

    def check_auth(self) -> bool:
        self.log_message(
            f"[AUTH] Checking authentication for {self.command} {self.path}"
        )

        is_presigned, access_key = self.validate_presigned_url()
        if is_presigned:
            self.log_message("[AUTH] Authentication successful (presigned URL)")
            return True

        if "Authorization" not in self.headers:
            self.log_message(
                "[AUTH] REJECTED: No Authorization header or presigned URL parameters"
            )
            self.log_message(f"[AUTH] Available headers: {dict(self.headers)}")
            self.send_error_response(403, "AccessDenied", "Access Denied")
            return False

        is_valid, _ = self.validate_signature_v4()
        if not is_valid:
            self.log_message("[AUTH] REJECTED: Signature validation failed")
            self.send_error_response(
                403,
                "SignatureDoesNotMatch",
                "The request signature we calculated does not "
                "match the signature you provided",
            )
            return False

        self.log_message("[AUTH] Authentication successful")
        return True

    def do_OPTIONS(self) -> None:
        if self.CORS_ENABLED:
            self.send_response(200)
            self.add_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_error_response(405, "MethodNotAllowed", "Method not allowed")

    def do_GET(self) -> None:
        if not self.check_auth():
            return

        req = self.parse_s3_path()

        if not req.bucket:
            self.send_error_response(
                404, "NoSuchBucket", "The specified bucket does not exist"
            )
            return

        if not req.key:
            self.send_error_response(
                501, "NotImplemented", "List objects not implemented"
            )
            return

        file_path = self.get_file_path(req.bucket, req.key)

        if not file_path.exists():
            self.send_error_response(
                404, "NoSuchKey", "The specified key does not exist"
            )
            return

        range_header = self.headers.get("Range")
        file_size = file_path.stat().st_size

        if range_header:
            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start = int(range_match.group(1))
                end = (
                    int(range_match.group(2)) if range_match.group(2) else file_size - 1
                )

                if start >= file_size or end >= file_size or start > end:
                    self.send_error_response(
                        416, "InvalidRange", "The requested range is not satisfiable"
                    )
                    return

                self.send_response(206)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(end - start + 1))
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("ETag", f'"{self._compute_etag(file_path)}"')
                self.add_cors_headers()
                self.end_headers()

                with open(file_path, "rb") as f:
                    f.seek(start)
                    self.wfile.write(f.read(end - start + 1))
                return

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", f'"{self._compute_etag(file_path)}"')
        self.add_cors_headers()
        self.end_headers()

        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def do_PUT(self) -> None:
        if not self.check_auth():
            return

        req = self.parse_s3_path()

        if not req.has_bucket_and_key:
            self.send_error_response(
                400, "InvalidRequest", "Bucket and key are required"
            )
            return

        if "uploadId" in req.query_params and "partNumber" in req.query_params:
            self._handle_upload_part(req)
            return

        file_path = self.get_file_path(req.bucket, req.key)  # type: ignore[arg-type]
        file_path.parent.mkdir(parents=True, exist_ok=True)

        content_length = int(self.headers.get("Content-Length", 0))
        content = self.rfile.read(content_length)

        with open(file_path, "wb") as f:
            f.write(content)

        etag = hashlib.md5(content).hexdigest()

        self.send_response(200)
        self.send_header("ETag", f'"{etag}"')
        self.add_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:
        if not self.check_auth():
            return

        req = self.parse_s3_path()

        if not req.has_bucket_and_key:
            self.send_error_response(
                400, "InvalidRequest", "Bucket and key are required"
            )
            return

        if "uploads" in req.query_params:
            self._handle_initiate_multipart(req)
            return

        if "uploadId" in req.query_params:
            self._handle_complete_multipart(req)
            return

        self.send_error_response(400, "InvalidRequest", "Unknown POST operation")

    def do_DELETE(self) -> None:
        if not self.check_auth():
            return

        req = self.parse_s3_path()

        if not req.has_bucket_and_key:
            self.send_error_response(
                400, "InvalidRequest", "Bucket and key are required"
            )
            return

        if "uploadId" in req.query_params:
            self._handle_abort_multipart(req)
            return

        file_path = self.get_file_path(req.bucket, req.key)  # type: ignore[arg-type]

        if not file_path.exists():
            self.send_error_response(
                404, "NoSuchKey", "The specified key does not exist"
            )
            return

        file_path.unlink()

        self.send_response(204)
        self.add_cors_headers()
        self.end_headers()

    @staticmethod
    def _compute_etag(file_path: Path) -> str:
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def _handle_initiate_multipart(self, req: S3Request) -> None:
        upload_id = os.urandom(16).hex()

        self.multipart_uploads[upload_id] = MultipartUpload(
            bucket=req.bucket,  # type: ignore[arg-type]
            key=req.key,  # type: ignore[arg-type]
        )

        response = InitiateMultipartUploadResponse(
            bucket=req.bucket,  # type: ignore[arg-type]
            key=req.key,  # type: ignore[arg-type]
            upload_id=upload_id,
        )
        self.send_s3_response(200, response.to_xml())

    def _handle_upload_part(self, req: S3Request) -> None:
        upload_id = req.query_params["uploadId"]
        part_number = int(req.query_params["partNumber"])

        if upload_id not in self.multipart_uploads:
            self.send_error_response(
                404, "NoSuchUpload", "The specified upload does not exist"
            )
            return

        content_length = int(self.headers.get("Content-Length", 0))
        content = self.rfile.read(content_length)

        temp_dir = Path(self.STORAGE_ROOT) / ".multipart" / upload_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        part_file = temp_dir / f"part_{part_number}"

        with open(part_file, "wb") as f:
            f.write(content)

        etag = hashlib.md5(content).hexdigest()

        self.multipart_uploads[upload_id].parts[part_number] = PartInfo(
            etag=etag,
            size=len(content),
            file=part_file,
        )

        self.send_response(200)
        self.send_header("ETag", f'"{etag}"')
        self.add_cors_headers()
        self.end_headers()

    def _handle_complete_multipart(self, req: S3Request) -> None:
        upload_id = req.query_params["uploadId"]

        if upload_id not in self.multipart_uploads:
            self.send_error_response(
                404, "NoSuchUpload", "The specified upload does not exist"
            )
            return

        upload_info = self.multipart_uploads[upload_id]

        content_length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(content_length).decode("utf-8")

        file_path = self.get_file_path(req.bucket, req.key)  # type: ignore[arg-type]
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as output_file:
            for part_num in sorted(upload_info.parts.keys()):
                part_info = upload_info.parts[part_num]
                with open(part_info.file, "rb") as part_file:
                    output_file.write(part_file.read())

        etag = self._compute_etag(file_path)

        temp_dir = Path(self.STORAGE_ROOT) / ".multipart" / upload_id
        for part_file in temp_dir.glob("*"):
            part_file.unlink()
        temp_dir.rmdir()

        del self.multipart_uploads[upload_id]

        response = CompleteMultipartUploadResponse(
            location=f"/{req.bucket}/{req.key}",
            bucket=req.bucket,  # type: ignore[arg-type]
            key=req.key,  # type: ignore[arg-type]
            etag=etag,
        )
        self.send_s3_response(200, response.to_xml())

    def _handle_abort_multipart(self, req: S3Request) -> None:
        upload_id = req.query_params["uploadId"]

        if upload_id not in self.multipart_uploads:
            self.send_error_response(
                404, "NoSuchUpload", "The specified upload does not exist"
            )
            return

        temp_dir = Path(self.STORAGE_ROOT) / ".multipart" / upload_id
        if temp_dir.exists():
            for part_file in temp_dir.glob("*"):
                part_file.unlink()
            temp_dir.rmdir()

        del self.multipart_uploads[upload_id]

        self.send_response(204)
        self.add_cors_headers()
        self.end_headers()


def run_server(
    host: str = "127.0.0.1",
    port: int = 9000,
    storage_root: str = "./s3_storage",
    access_key: str | None = None,
    secret_key: str | None = None,
    cors_enabled: bool = False,
    cors_origins: str = "*",
    cors_methods: str = "GET, PUT, POST, DELETE, HEAD, OPTIONS",
    cors_headers: str = "Authorization, Content-Type, Content-MD5, x-amz-*, Range",
    debug: bool = False,
) -> None:
    S3ProxyHandler.STORAGE_ROOT = storage_root
    S3ProxyHandler.DEBUG = debug

    if access_key and secret_key:
        S3ProxyHandler.CREDENTIALS = {access_key: secret_key}
    else:
        S3ProxyHandler.CREDENTIALS = {}

    S3ProxyHandler.CORS_ENABLED = cors_enabled
    S3ProxyHandler.CORS_ORIGINS = cors_origins
    S3ProxyHandler.CORS_METHODS = cors_methods
    S3ProxyHandler.CORS_HEADERS = cors_headers

    server_address = (host, port)
    httpd = HTTPServer(server_address, S3ProxyHandler)

    if cors_enabled:
        pass
    if debug:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="S3 Proxy Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9000, help="Port to bind to")
    parser.add_argument(
        "--storage", default="./s3_storage", help="Storage root directory"
    )
    parser.add_argument("--access-key", help="AWS access key for authentication")
    parser.add_argument("--secret-key", help="AWS secret key for authentication")
    parser.add_argument("--cors", action="store_true", help="Enable CORS support")
    parser.add_argument(
        "--cors-origins", default="*", help="CORS allowed origins (default: *)"
    )
    parser.add_argument(
        "--cors-methods",
        default="GET, PUT, POST, DELETE, HEAD, OPTIONS",
        help="CORS allowed methods",
    )
    parser.add_argument(
        "--cors-headers",
        default="Authorization, Content-Type, Content-MD5, x-amz-*, Range",
        help="CORS allowed headers",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (shows detailed auth logs)",
    )

    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        storage_root=args.storage,
        access_key=args.access_key,
        secret_key=args.secret_key,
        cors_enabled=args.cors,
        cors_origins=args.cors_origins,
        cors_methods=args.cors_methods,
        cors_headers=args.cors_headers,
        debug=args.debug,
    )
