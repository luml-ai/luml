import hashlib
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from luml.s3_proxy.s3_signature_validator import AwsSignatureValidator
from luml.s3_proxy.schemas import (
    CompleteMultipartUploadResponse,
    InitiateMultipartUploadResponse,
    MultipartUpload,
    PartInfo,
    S3AuthError,
    S3ErrorResponse,
    S3Request,
)


class S3ProxyHandler(BaseHTTPRequestHandler):
    STORAGE_ROOT: str = "./s3_storage"  # Storage root directory
    CREDENTIALS: dict[str, str] = {}
    MAX_FILE_SIZE: int = 5_497_558_138_880  # 5 TB

    CORS_ENABLED: bool = False
    CORS_ORIGINS: str = "*"
    CORS_METHODS: str = "GET, PUT, POST, DELETE, HEAD, OPTIONS"
    CORS_HEADERS: str = "Authorization, Content-Type, Content-MD5, x-amz-*, Range"
    CORS_MAX_AGE: str = "3600"

    multipart_uploads: dict[str, MultipartUpload] = {}

    DEBUG: bool = False
    _auth: AwsSignatureValidator | None = None

    @classmethod
    def get_auth(cls) -> AwsSignatureValidator:
        if cls._auth is None:
            cls._auth = AwsSignatureValidator(
                credentials=cls.CREDENTIALS, debug=cls.DEBUG
            )
        return cls._auth

    @classmethod
    def reset_auth(cls) -> None:
        cls._auth = None

    def __init__(self, *args, **kwargs) -> None:
        os.makedirs(self.STORAGE_ROOT, exist_ok=True)
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args) -> None:
        message = format % args if args else format
        if message.startswith("[AUTH]") and not self.DEBUG:
            return
        super().log_message("%s", message)

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

    def _get_content_length(self) -> int:
        header_value = self.headers.get("Content-Length")
        if header_value is None:
            return 0
        try:
            length = int(header_value)
            return max(0, length)
        except ValueError:
            return 0

    def _require_content_length(self) -> int | None:
        header_value = self.headers.get("Content-Length")
        if header_value is None:
            self.send_error_response(
                400, "MissingContentLength", "Content-Length header is required"
            )
            return None
        try:
            length = int(header_value)
            if length < 0:
                self.send_error_response(
                    400, "InvalidArgument", "Content-Length must be non-negative"
                )
                return None
            if length > self.MAX_FILE_SIZE:
                self.send_error_response(
                    400,
                    "EntityTooLarge",
                    f"File size exceeds maximum allowed ({self.MAX_FILE_SIZE} bytes)",
                )
                return None
            return length
        except ValueError:
            self.send_error_response(
                400, "InvalidArgument", "Content-Length must be a valid integer"
            )
            return None

    def _safe_write_file(self, file_path: Path, content: bytes) -> bool:
        """Safely write content to file. Returns False and sends error on failure."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(content)
            return True
        except PermissionError:
            self.send_error_response(
                500, "AccessDenied", "Permission denied writing file"
            )
            return False
        except OSError as e:
            self.send_error_response(500, "InternalError", f"Failed to write file: {e}")
            return False

    def _safe_delete_file(self, file_path: Path) -> bool:
        try:
            file_path.unlink()
            return True
        except FileNotFoundError:
            self.send_error_response(
                404, "NoSuchKey", "The specified key does not exist"
            )
            return False
        except PermissionError:
            self.send_error_response(
                500, "AccessDenied", "Permission denied deleting file"
            )
            return False
        except OSError as e:
            self.send_error_response(
                500, "InternalError", f"Failed to delete file: {e}"
            )
            return False

    def _safe_cleanup_temp_dir(self, temp_dir: Path) -> None:
        """Safely cleanup multipart temp directory. Errors are logged but not raised."""
        try:
            if temp_dir.exists():
                for part_file in temp_dir.glob("*"):
                    part_file.unlink(missing_ok=True)
                temp_dir.rmdir()
        except OSError as e:
            self.log_message(f"Warning: Failed to cleanup temp dir {temp_dir}: {e}")

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
        storage_root = Path(self.STORAGE_ROOT).resolve()
        file_path = (storage_root / bucket / key).resolve()
        if os.path.commonpath([str(storage_root), str(file_path)]) != str(storage_root):
            raise ValueError("Invalid bucket or key path.")
        return file_path

    def check_auth(self) -> bool:
        try:
            self.get_auth().validate_request(
                dict(self.headers), self.command, self.path
            )
            self.log_message("[AUTH] Authentication successful")
            return True
        except S3AuthError as e:
            self.log_message(f"[AUTH] {e.error_code}: {e.message}")
            self.send_error_response(e.status_code, e.error_code, e.message)
            return False

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
            while chunk := f.read(8192):
                self.wfile.write(chunk)

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

        content_length = self._require_content_length()
        if content_length is None:
            return
        content = self.rfile.read(content_length)

        file_path = self.get_file_path(req.bucket, req.key)  # type: ignore[arg-type]
        if not self._safe_write_file(file_path, content):
            return

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

        if not self._safe_delete_file(file_path):
            return

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

        content_length = self._require_content_length()
        if content_length is None:
            return
        content = self.rfile.read(content_length)

        temp_dir = Path(self.STORAGE_ROOT) / ".multipart" / upload_id
        part_file = temp_dir / f"part_{part_number}"

        if not self._safe_write_file(part_file, content):
            return

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

        content_length = self._get_content_length()
        self.rfile.read(content_length).decode("utf-8")

        file_path = self.get_file_path(req.bucket, req.key)  # type: ignore[arg-type]

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as output_file:
                for part_num in sorted(upload_info.parts.keys()):
                    part_info = upload_info.parts[part_num]
                    with open(part_info.file, "rb") as part_file:
                        output_file.write(part_file.read())
        except OSError as e:
            self.send_error_response(
                500, "InternalError", f"Failed to assemble file: {e}"
            )
            return

        etag = self._compute_etag(file_path)

        temp_dir = Path(self.STORAGE_ROOT) / ".multipart" / upload_id
        self._safe_cleanup_temp_dir(temp_dir)

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
        self._safe_cleanup_temp_dir(temp_dir)

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
    debug: bool = False,
) -> None:
    S3ProxyHandler.STORAGE_ROOT = storage_root
    S3ProxyHandler.DEBUG = debug

    if access_key and secret_key:
        S3ProxyHandler.CREDENTIALS = {access_key: secret_key}
    else:
        S3ProxyHandler.CREDENTIALS = {}

    S3ProxyHandler.CORS_ENABLED = cors_enabled

    server_address = (host, port)
    httpd = HTTPServer(server_address, S3ProxyHandler)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
