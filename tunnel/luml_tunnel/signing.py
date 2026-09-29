import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from luml_tunnel.tokens import TokenKind

ALGORITHM = "ES256"
SESSION_CLAIM = "sid"
KIND_CLAIM = "kind"


def public_jwk(public_key: ec.EllipticCurvePublicKey) -> dict[str, str]:
    jwk: dict[str, str] = ECAlgorithm.to_jwk(public_key, as_dict=True)
    key_id = _thumbprint(jwk)
    return {**jwk, "kid": key_id, "alg": ALGORITHM, "use": "sig"}


def _thumbprint(jwk: dict[str, str]) -> str:
    # RFC 7638: SHA-256 over the required members in lexicographic order, without whitespace.
    required = {name: jwk[name] for name in ("crv", "kty", "x", "y")}
    canonical = json.dumps(required, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode()


def generate_private_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def private_key_to_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def load_private_key(pem: str) -> ec.EllipticCurvePrivateKey:
    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(
        private_key.curve, ec.SECP256R1
    ):
        raise ValueError("the signing key must be an EC key on the P-256 curve")
    return private_key


def key_set(*public_keys: ec.EllipticCurvePublicKey) -> dict[str, list[dict[str, str]]]:
    return {"keys": [public_jwk(public_key) for public_key in public_keys]}


@dataclass(frozen=True)
class TokenSigner:
    private_key: ec.EllipticCurvePrivateKey
    issuer: str

    @property
    def key_id(self) -> str:
        return public_jwk(self.private_key.public_key())["kid"]

    def sign(
        self,
        kind: TokenKind,
        relay: str,
        session: str,
        user: str,
        lifetime: timedelta,
        now: datetime | None = None,
    ) -> str:
        issued_at = now or datetime.now(UTC)
        payload: dict[str, Any] = {
            "iss": self.issuer,
            "aud": relay,
            "sub": user,
            SESSION_CLAIM: session,
            KIND_CLAIM: str(kind),
            "iat": issued_at,
            "exp": issued_at + lifetime,
            "jti": secrets.token_urlsafe(16),
        }
        return jwt.encode(
            payload, self.private_key, algorithm=ALGORITHM, headers={"kid": self.key_id}
        )
