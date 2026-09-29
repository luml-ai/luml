import hashlib
import hmac
from enum import StrEnum

_FINGERPRINT_LENGTH = 12
_DOMAIN = b"luml-satellite-token-v1"


class TokenPurpose(StrEnum):
    COMPANION = "companion"
    MONITORING_SESSION = "monitoring-session"


class TokenDeriver:
    def __init__(self, satellite_token: str, derivation_key: str | None = None) -> None:
        if not satellite_token:
            raise ValueError("satellite_token must not be empty")
        if derivation_key == "":
            raise ValueError("derivation_key must not be empty")
        self._key = (derivation_key or satellite_token).encode()

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self._key).hexdigest()[:_FINGERPRINT_LENGTH]

    def artifact_token(self, deployment_id: str) -> str:
        return hmac.new(self._key, str(deployment_id).encode(), hashlib.sha256).hexdigest()

    def verify_artifact_token(self, deployment_id: str, token: str | None) -> bool:
        if not token:
            return False
        return hmac.compare_digest(self.artifact_token(deployment_id), token)

    def derive(self, purpose: str | TokenPurpose, subject: str) -> str:
        purpose_value = str(purpose)
        if not purpose_value:
            raise ValueError("purpose must not be empty")
        message = b"\0".join((_DOMAIN, purpose_value.encode(), str(subject).encode()))
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def companion_token(self, deployment_id: str) -> str:
        return self.derive(TokenPurpose.COMPANION, deployment_id)

    def verify(
        self,
        purpose: str | TokenPurpose,
        subject: str,
        token: str | None,
    ) -> bool:
        if not token:
            return False
        return hmac.compare_digest(self.derive(purpose, subject), token)


def mint_artifact_token(
    deployment_id: str,
    satellite_token: str,
    derivation_key: str | None = None,
) -> str:
    return TokenDeriver(satellite_token, derivation_key).artifact_token(deployment_id)
