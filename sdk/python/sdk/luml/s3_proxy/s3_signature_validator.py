import hashlib
import hmac
import logging
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, quote, urlparse

from luml.s3_proxy.schemas import AwsAuthInfo, AwsCredentials, S3AuthError

logging.basicConfig(
    format="[AUTH] %(message)s",
    level=logging.DEBUG,
)


class AwsSignatureValidator:
    def __init__(
        self,
        credentials: dict[str, str] | None = None,
        debug: bool = False,
        algorithm: str = "AWS4-HMAC-SHA256",
    ) -> None:
        self.credentials = credentials or {}
        self._logger = logging.getLogger(__name__)
        self.algorithm = algorithm
        if debug:
            self._logger.setLevel(logging.DEBUG)

    @staticmethod
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(
        self, secret_key: str, creds: AwsCredentials | AwsAuthInfo
    ) -> bytes:
        k_date = self._sign(f"AWS4{secret_key}".encode(), creds.date_stamp)
        k_region = self._sign(k_date, creds.region)
        k_service = self._sign(k_region, creds.service)
        return self._sign(k_service, "aws4_request")

    def _check_presigned_expiration(self, x_amz_date: str, expires: str) -> bool:
        try:
            request_time = datetime.strptime(x_amz_date, "%Y%m%dT%H%M%SZ")
            request_time = request_time.replace(tzinfo=UTC)
            age_seconds = (datetime.now(UTC) - request_time).total_seconds()

            if age_seconds > int(expires):
                self._logger.debug("Presigned URL expired")
                return False
            return True
        except ValueError as e:
            self._logger.debug(f"Invalid date format: {e}")
            return False

    @staticmethod
    def _build_presigned_canonical_querystring(
        query_params: dict[str, list[str]],
    ) -> str:
        canonical_params = []
        for key in sorted(query_params.keys()):
            if key != "X-Amz-Signature":
                for value in query_params[key]:
                    # URL-encode key and value per AWS Signature V4 spec
                    encoded_key = quote(key, safe="~")
                    encoded_value = quote(value, safe="~")
                    canonical_params.append(f"{encoded_key}={encoded_value}")
        return "&".join(canonical_params)

    def _parse_credential(self, credential: str) -> AwsCredentials | None:
        cred_parts = credential.split("/")
        if len(cred_parts) != 5:
            self._logger.debug(f"Invalid credential format: {cred_parts}")
            return None
        access_key, date_stamp, region, service, _ = cred_parts
        return AwsCredentials(
            access_key=access_key, date_stamp=date_stamp, region=region, service=service
        )

    def _get_secret_key(self, access_key: str) -> str | None:
        if not self.credentials:
            return None
        if access_key not in self.credentials:
            self._logger.debug(
                f"Unknown access key. Configured keys: {list(self.credentials.keys())}"
            )
            return None
        return self.credentials[access_key]

    @staticmethod
    def _build_canonical_headers(signed_headers: str, headers: dict[str, str]) -> str:
        canonical_headers = []
        for header in signed_headers.split(";"):
            value = headers.get(header, "") or headers.get(header.title(), "")
            canonical_headers.append(f"{header}:{value.strip()}")
        return "\n".join(canonical_headers) + "\n"

    def _compute_signature_raw(
        self,
        secret_key: str,
        creds: AwsCredentials,
        string_to_sign: str,
    ) -> str:
        signing_key = self._get_signature_key(secret_key, creds)
        return hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def _parse_auth_header(self, headers: dict[str, str]) -> AwsAuthInfo | None:
        auth_header = headers.get("Authorization", "")

        self._logger.debug(f"Authorization header: {auth_header[:100]}...")

        if not auth_header.startswith(self.algorithm):
            self._logger.debug(
                f"Authorization header does not start with {self.algorithm}"
            )
            return None

        pattern = (
            rf"{self.algorithm} Credential=([^,]+), "
            r"SignedHeaders=([^,]+), Signature=([a-f0-9]+)"
        )
        match = re.match(pattern, auth_header)
        if not match:
            self._logger.debug("Could not parse authorization header")
            return None

        credential, signed_headers, client_signature = match.groups()

        creds = self._parse_credential(credential)
        if creds is None:
            return None

        secret_key = self._get_secret_key(creds.access_key)
        if secret_key is None:
            return None

        return AwsAuthInfo(
            access_key=creds.access_key,
            secret_key=secret_key,
            date_stamp=creds.date_stamp,
            region=creds.region,
            service=creds.service,
            signed_headers=signed_headers,
            client_signature=client_signature,
        )

    def _build_string_to_sign(
        self,
        auth: AwsAuthInfo,
        headers: dict[str, str],
        method: str,
        path: str,
    ) -> str | None:
        x_amz_date = headers.get("x-amz-date", "")

        if not x_amz_date and not headers.get("Date", ""):
            self._logger.debug("Missing x-amz-date or Date header")
            return None

        parsed_path = urlparse(path)
        canonical_uri = parsed_path.path
        canonical_querystring = parsed_path.query or ""

        canonical_headers = []
        for header in auth.signed_headers.split(";"):
            value = headers.get(header, "")
            canonical_headers.append(f"{header}:{value.strip()}")
        canonical_headers_str = "\n".join(canonical_headers) + "\n"

        payload_hash = headers.get("x-amz-content-sha256", "UNSIGNED-PAYLOAD")

        canonical_request = (
            f"{method}\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers_str}\n{auth.signed_headers}\n{payload_hash}"
        )

        credential_scope = (
            f"{auth.date_stamp}/{auth.region}/{auth.service}/aws4_request"
        )
        canonical_request_hash = hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest()

        return f"{self.algorithm}\n{x_amz_date}\n{credential_scope}\n{canonical_request_hash}"

    def _compute_signature(self, auth: AwsAuthInfo, string_to_sign: str) -> str:
        signing_key = self._get_signature_key(auth.secret_key, auth)
        return hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def validate_signature(
        self,
        headers: dict[str, str],
        method: str,
        path: str,
    ) -> tuple[bool, str | None]:
        if not self.credentials:
            return self._validate_no_credentials(headers)

        try:
            auth = self._parse_auth_header(headers)
            if auth is None:
                return False, None

            string_to_sign = self._build_string_to_sign(auth, headers, method, path)

            if string_to_sign is None:
                return False, auth.access_key

            signature = self._compute_signature(auth, string_to_sign)

            if signature != auth.client_signature:
                self._logger.debug(
                    f"Signature mismatch for access key: {auth.access_key}"
                )
                return False, auth.access_key

            self._logger.debug("Signature validated successfully")
            return True, auth.access_key

        except Exception as e:
            self._logger.debug(f"Signature validation error: {e}", exc_info=True)
            return False, None

    def _validate_no_credentials(
        self, headers: dict[str, str]
    ) -> tuple[bool, str | None]:
        auth_header = headers.get("Authorization", "")
        self._logger.debug("No credentials configured - accepting any valid signature")

        if not auth_header.startswith(self.algorithm):
            self._logger.debug(
                f"Authorization header does not start with {self.algorithm}"
            )
            return False, None

        pattern = rf"{self.algorithm} Credential=([^/]+)/"
        match = re.search(pattern, auth_header)
        if match:
            return True, match.group(1)

        self._logger.debug("Could not extract access key from authorization header")
        return len(auth_header) > 0, None

    def validate_presigned_url(
        self,
        headers: dict[str, str],
        method: str,
        path: str,
    ) -> tuple[bool, str | None]:
        parsed = urlparse(path)
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        if "X-Amz-Signature" not in query_params:
            return False, None

        try:
            credential = query_params.get("X-Amz-Credential", [""])[0]
            x_amz_date = query_params.get("X-Amz-Date", [""])[0]
            expires = query_params.get("X-Amz-Expires", ["3600"])[0]
            signed_headers = query_params.get("X-Amz-SignedHeaders", ["host"])[0]
            client_signature = query_params.get("X-Amz-Signature", [""])[0]

            creds = self._parse_credential(credential)
            if creds is None:
                return False, None

            if not self.credentials:
                self._logger.debug(
                    "No credentials configured - accepting presigned URL"
                )
                return True, creds.access_key

            secret_key = self._get_secret_key(creds.access_key)
            if secret_key is None:
                return False, creds.access_key

            if not self._check_presigned_expiration(x_amz_date, expires):
                return False, creds.access_key

            canonical_querystring = self._build_presigned_canonical_querystring(
                query_params
            )
            canonical_headers_str = self._build_canonical_headers(
                signed_headers, headers
            )

            canonical_request = (
                f"{method}\n{parsed.path}\n{canonical_querystring}\n"
                f"{canonical_headers_str}\n{signed_headers}\nUNSIGNED-PAYLOAD"
            )

            credential_scope = (
                f"{creds.date_stamp}/{creds.region}/{creds.service}/aws4_request"
            )
            canonical_request_hash = hashlib.sha256(
                canonical_request.encode()
            ).hexdigest()
            string_to_sign = (
                f"{self.algorithm}\n{x_amz_date}\n"
                f"{credential_scope}\n{canonical_request_hash}"
            )

            computed_signature = self._compute_signature_raw(
                secret_key, creds, string_to_sign
            )

            if computed_signature != client_signature:
                self._logger.debug("Signature mismatch")
                return False, creds.access_key

            return True, creds.access_key

        except Exception as e:
            self._logger.debug(f"Presigned URL validation error: {e}", exc_info=True)
            return False, None

    def validate_request(
        self,
        headers: dict[str, str],
        method: str,
        path: str,
    ) -> str | None:
        is_presigned, access_key = self.validate_presigned_url(headers, method, path)
        if is_presigned:
            self._logger.debug("Authentication successful (presigned URL)")
            return access_key

        if "Authorization" not in headers:
            self._logger.debug(
                f"No Authorization header or presigned URL parameters\n"
                f"Available headers: {list(headers.keys())}"
            )
            raise S3AuthError(403, "AccessDenied", "Access Denied")

        is_valid, access_key = self.validate_signature(headers, method, path)
        if not is_valid:
            self._logger.debug("Signature validation failed")
            raise S3AuthError(
                403,
                "SignatureDoesNotMatch",
                "The request signature does not match the signature you provided",
            )

        self._logger.debug("Authentication successful")
        return access_key
