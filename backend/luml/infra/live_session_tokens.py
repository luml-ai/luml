import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

# The claims and the key identifier follow what `luml_tunnel` checks in the relay.
ALGORITHM = "ES256"
TOKEN_ISSUER = "luml"


class TunnelTokenKind(StrEnum):
    EXPOSE = "expose"
    VIEW = "view"


def load_signing_key(pem: str) -> ec.EllipticCurvePrivateKey:
    # Environment files often hold a PEM on one line with "\n" escapes.
    private_key = serialization.load_pem_private_key(
        pem.replace("\\n", "\n").encode(), password=None
    )
    if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(
        private_key.curve, ec.SECP256R1
    ):
        raise ValueError("The live session signing key must be an EC P-256 key")
    return private_key


def _thumbprint(jwk: dict[str, str]) -> str:
    # RFC 7638: SHA-256 over the required members in lexicographic order.
    required = {name: jwk[name] for name in ("crv", "kty", "x", "y")}
    canonical = json.dumps(required, separators=(",", ":"), sort_keys=True).encode()
    digest = hashlib.sha256(canonical).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class TunnelTokenSigner:
    def __init__(self, private_key: ec.EllipticCurvePrivateKey) -> None:
        self._private_key = private_key
        jwk: dict[str, str] = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
        self.key_id = _thumbprint(jwk)
        self.public_jwk = {**jwk, "kid": self.key_id, "alg": ALGORITHM, "use": "sig"}

    def sign(
        self,
        kind: TunnelTokenKind,
        relay_id: str,
        session_id: str,
        user_id: str,
        lifetime: timedelta,
    ) -> tuple[str, datetime]:
        # JWT times are whole seconds, so the reported expiry matches the claim.
        issued_at = datetime.now(UTC).replace(microsecond=0)
        expires_at = issued_at + lifetime
        payload: dict[str, Any] = {
            "iss": TOKEN_ISSUER,
            "aud": relay_id,
            "sub": user_id,
            "sid": session_id,
            "kind": str(kind),
            "iat": issued_at,
            "exp": expires_at,
            "jti": secrets.token_urlsafe(16),
        }
        token = jwt.encode(
            payload,
            self._private_key,
            algorithm=ALGORITHM,
            headers={"kid": self.key_id},
        )
        return token, expires_at
