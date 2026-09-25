import hashlib
import hmac

import pytest

from luml_satellite.tokens import TokenDeriver, TokenPurpose, mint_artifact_token


def test_default_artifact_token_matches_the_existing_agent() -> None:
    satellite_token = "satellite-secret"
    deployment_id = "deployment-id"
    expected = hmac.new(
        satellite_token.encode(), deployment_id.encode(), hashlib.sha256
    ).hexdigest()

    deriver = TokenDeriver(satellite_token)

    assert deriver.artifact_token(deployment_id) == expected
    assert mint_artifact_token(deployment_id, satellite_token) == expected
    assert deriver.verify_artifact_token(deployment_id, expected) is True
    assert deriver.verify_artifact_token(deployment_id, None) is False


def test_configured_derivation_key_survives_satellite_token_reissue() -> None:
    first = TokenDeriver("old-satellite-token", "stable-derivation-key")
    second = TokenDeriver("new-satellite-token", "stable-derivation-key")
    rotated = TokenDeriver("new-satellite-token", "rotated-derivation-key")

    assert first.artifact_token("deployment") == second.artifact_token("deployment")
    assert first.companion_token("deployment") == second.companion_token("deployment")
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != rotated.fingerprint


def test_token_purposes_and_subjects_are_separated() -> None:
    deriver = TokenDeriver("satellite-token")

    tokens = {
        deriver.artifact_token("deployment"),
        deriver.companion_token("deployment"),
        deriver.derive(TokenPurpose.MONITORING_SESSION, "deployment"),
        deriver.companion_token("other-deployment"),
    }

    assert len(tokens) == 4
    companion = deriver.companion_token("deployment")
    assert deriver.verify(TokenPurpose.COMPANION, "deployment", companion) is True
    assert deriver.verify(TokenPurpose.MONITORING_SESSION, "deployment", companion) is False


@pytest.mark.parametrize(
    ("satellite_token", "derivation_key", "message"),
    [("", None, "satellite_token"), ("token", "", "derivation_key")],
)
def test_empty_key_material_is_rejected(
    satellite_token: str,
    derivation_key: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        TokenDeriver(satellite_token, derivation_key)
