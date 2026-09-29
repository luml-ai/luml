import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx
import pytest

from luml_satellite import AuthorizationVerdict, Deployment, ModelDescription, TokenDeriver
from luml_satellite.serving import (
    COMPANION_PATH,
    CompanionAuthorization,
    CompanionAuthorizer,
    CompanionClient,
    CompanionMetadata,
    CompanionRecordingPolicy,
    CompanionRefusedError,
    CompanionSecrets,
    CompanionSecretSource,
    CompanionServingPlacement,
    CompanionUnavailableError,
    SecretUnavailable,
    create_sidecar_internal_application,
)
from luml_satellite.workload import DeploymentMetadata, RecordingPolicy
from tests.helpers import ARTIFACT_ID, DEPLOYMENT_ID, deployment_record

OTHER_DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000002"
SATELLITE_ID = "00000000-0000-0000-0000-000000000001"


@dataclass
class FakeClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now


@dataclass
class FakeCompanion:
    allowed: dict[str, bool] = field(default_factory=lambda: {"key": True, "new": True})
    secret_values: dict[str, str] = field(default_factory=lambda: {"password": "first"})
    failure: CompanionUnavailableError | None = None
    authorization_calls: list[str] = field(default_factory=list)
    secret_calls: int = 0

    async def metadata(self) -> CompanionMetadata:
        if self.failure is not None:
            raise self.failure
        return CompanionMetadata(
            deployment_id=DEPLOYMENT_ID,
            artifact_id=ARTIFACT_ID,
        )

    async def authorize(self, api_key: str) -> CompanionAuthorization:
        self.authorization_calls.append(api_key)
        if self.failure is not None:
            raise self.failure
        return CompanionAuthorization(authorized=self.allowed.get(api_key, False))

    async def secrets(self) -> CompanionSecrets:
        self.secret_calls += 1
        if self.failure is not None:
            raise self.failure
        return CompanionSecrets(values=self.secret_values)


class AllowKnownKeys:
    async def authorize(self, api_key: str) -> AuthorizationVerdict:
        return (
            AuthorizationVerdict.ALLOWED
            if api_key in {"platform-key", "target-key"}
            else AuthorizationVerdict.DENIED
        )


class StaticSecrets:
    async def resolve(
        self,
        deployment_id: str,
        secrets: Mapping[str, str],
    ) -> Mapping[str, str]:
        assert deployment_id == DEPLOYMENT_ID
        return {attribute: f"value-for-{secret_id}" for attribute, secret_id in secrets.items()}


async def _finish_background_refresh() -> None:
    await asyncio.sleep(0)
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_companion_authorizer_refreshes_and_uses_only_bounded_stale_entries() -> None:
    clock = FakeClock()
    companion = FakeCompanion()
    authorizer = CompanionAuthorizer(companion, clock=clock)

    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    clock.now = 50
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    assert companion.authorization_calls == ["key"]
    await _finish_background_refresh()
    assert companion.authorization_calls == ["key", "key"]

    clock.now = 70
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    companion.failure = CompanionUnavailableError("satellite down")
    clock.now = 500
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    assert await authorizer.authorize("new") is AuthorizationVerdict.UNAVAILABLE
    clock.now = 1000
    assert await authorizer.authorize("key") is AuthorizationVerdict.UNAVAILABLE
    await authorizer.aclose()


@pytest.mark.asyncio
async def test_companion_authorizer_negative_cache_expires_after_ten_seconds() -> None:
    clock = FakeClock()
    companion = FakeCompanion(allowed={"denied": False})
    authorizer = CompanionAuthorizer(companion, clock=clock)

    assert await authorizer.authorize("denied") is AuthorizationVerdict.DENIED
    clock.now = 9
    assert await authorizer.authorize("denied") is AuthorizationVerdict.DENIED
    assert companion.authorization_calls == ["denied"]

    companion.allowed["denied"] = True
    clock.now = 10
    assert await authorizer.authorize("denied") is AuthorizationVerdict.ALLOWED
    assert companion.authorization_calls == ["denied", "denied"]
    await authorizer.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [403, 404])
async def test_companion_refusals_are_unavailable_and_never_cached_as_denials(
    status_code: int,
) -> None:
    clock = FakeClock()
    companion = FakeCompanion()
    authorizer = CompanionAuthorizer(companion, clock=clock)
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED

    clock.now = 61
    companion.failure = CompanionRefusedError(status_code)
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    assert await authorizer.authorize("new") is AuthorizationVerdict.UNAVAILABLE

    calls_during_refusal = companion.authorization_calls.copy()
    companion.failure = None
    assert await authorizer.authorize("key") is AuthorizationVerdict.ALLOWED
    assert await authorizer.authorize("new") is AuthorizationVerdict.ALLOWED
    assert companion.authorization_calls == [*calls_during_refusal, "key", "new"]
    await authorizer.aclose()


@pytest.mark.asyncio
async def test_companion_secret_source_refreshes_and_honours_the_stale_allowance() -> None:
    clock = FakeClock()
    companion = FakeCompanion()
    source = CompanionSecretSource(companion, DEPLOYMENT_ID, clock=clock)
    references = {"password": "secret-id"}

    assert await source.resolve(DEPLOYMENT_ID, references) == {"password": "first"}
    companion.secret_values = {"password": "second"}
    clock.now = 50
    assert await source.resolve(DEPLOYMENT_ID, references) == {"password": "first"}
    await _finish_background_refresh()
    clock.now = 70
    assert await source.resolve(DEPLOYMENT_ID, references) == {"password": "second"}

    companion.failure = CompanionUnavailableError("satellite down")
    clock.now = 500
    assert await source.resolve(DEPLOYMENT_ID, references) == {"password": "second"}
    clock.now = 1000
    with pytest.raises(SecretUnavailable, match="password"):
        await source.resolve(DEPLOYMENT_ID, references)
    await source.aclose()


@pytest.mark.asyncio
async def test_companion_api_is_token_bound_and_not_held_by_the_starting_gate() -> None:
    tokens = TokenDeriver("satellite-token", "derivation-key")
    placement = CompanionServingPlacement(
        AllowKnownKeys(),
        StaticSecrets(),
        tokens,
        satellite_id=SATELLITE_ID,
        recording_policy=RecordingPolicy(sample_rate=0.25, body_max_bytes=2048),
        upstream_transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    )
    path = COMPANION_PATH.format(deployment_id=DEPLOYMENT_ID)
    foreign_path = COMPANION_PATH.format(deployment_id=OTHER_DEPLOYMENT_ID)
    valid_headers = {"Authorization": f"Bearer {tokens.companion_token(DEPLOYMENT_ID)}"}
    foreign_headers = {"Authorization": f"Bearer {tokens.companion_token(OTHER_DEPLOYMENT_ID)}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=placement.internal_application),
        base_url="http://satellite",
    ) as internal:
        wrong_token = await internal.get(path, headers={"Authorization": "Bearer wrong"})
        not_registered = await internal.get(path, headers=valid_headers)
        foreign = await internal.get(foreign_path, headers=foreign_headers)

        deployment = Deployment.model_validate(
            deployment_record(
                monitoring_mode="full",
                dynamic_attributes_secrets={"password": "secret-id"},
            )
        )
        await placement.register(
            deployment,
            upstream_url="http://sidecar:8001",
            description=ModelDescription(schema={"openapi": "3.1.0"}),
        )
        metadata = await internal.get(path, headers=valid_headers)
        authorization = await internal.post(
            f"{path}/inference-access",
            headers=valid_headers,
            json={"api_key": "target-key"},
        )
        secrets = await internal.get(f"{path}/secrets", headers=valid_headers)
        await placement.register(
            deployment.model_copy(update={"monitoring_mode": "off"}),
            upstream_url=None,
            description=ModelDescription(),
        )
        updated_metadata = await internal.get(path, headers=valid_headers)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=placement.application),
        base_url="http://satellite",
    ) as public:
        gated = await public.get(
            "/deployments",
            headers={"Authorization": "Bearer platform-key"},
        )
    await placement.aclose()

    assert wrong_token.status_code == 403
    assert not_registered.status_code == 404
    assert not_registered.json() == {
        "detail": "Deployment not hosted",
        "code": "deployment_not_hosted",
    }
    assert foreign.json() == not_registered.json()
    assert metadata.status_code == 200
    assert metadata.json()["secret_attributes"] == ["password"]
    assert metadata.json()["monitoring_enabled"] is True
    assert updated_metadata.json()["monitoring_enabled"] is False
    registered = placement.get_companion_record(DEPLOYMENT_ID)
    assert registered is not None
    assert registered.deployment.upstream_url == "http://sidecar:8001"
    assert metadata.json()["recording_policy"] == {
        "sample_rate": 0.25,
        "body_max_bytes": 2048,
        "keep_inputs": True,
        "keep_outputs": True,
    }
    assert authorization.json() == {"authorized": True, "ttl_seconds": 60.0}
    assert secrets.json() == {
        "values": {"password": "value-for-secret-id"},
        "ttl_seconds": 60.0,
    }
    assert gated.status_code == 503


@pytest.mark.asyncio
async def test_companion_placement_reads_the_guarded_sidecar_internal_port() -> None:
    tokens = TokenDeriver("satellite-token", "derivation-key")
    companion_token = tokens.companion_token(DEPLOYMENT_ID)
    sidecar_internal = create_sidecar_internal_application(
        companion_token,
        description=lambda: ModelDescription(
            manifest={"producer_tags": ["luml.ai::tabular_monitoring:v1"]},
            schema={"openapi": "3.1.0"},
            reference_profile={
                "profile_status": "ready",
                "feature_summaries": {"numerical_features": {"x": {"mean": 1}}},
            },
        ),
        health=lambda: asyncio.sleep(0, result=True),
    )
    placement = CompanionServingPlacement(
        AllowKnownKeys(),
        StaticSecrets(),
        tokens,
        upstream_transport=httpx.ASGITransport(app=sidecar_internal),
    )
    deployment = Deployment.model_validate(deployment_record())
    try:
        description = await placement.describe(deployment, upstream_url="http://sidecar")
        healthy = await placement.check_health(deployment, upstream_url="http://sidecar")
    finally:
        await placement.aclose()

    assert description.manifest == {"producer_tags": ["luml.ai::tabular_monitoring:v1"]}
    assert description.schema == {"openapi": "3.1.0"}
    assert description.reference_profile is not None
    assert healthy is True


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [403, 404])
async def test_companion_client_maps_token_and_registration_refusals(
    status_code: int,
) -> None:
    client = CompanionClient(
        "http://satellite",
        DEPLOYMENT_ID,
        "token",
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code)),
    )
    try:
        with pytest.raises(CompanionRefusedError) as caught:
            await client.metadata()
    finally:
        await client.aclose()

    assert caught.value.status_code == status_code


def test_companion_metadata_policy_round_trip() -> None:
    metadata = CompanionMetadata(
        deployment_id=DEPLOYMENT_ID,
        artifact_id=ARTIFACT_ID,
        metadata=DeploymentMetadata(name="classifier"),
        recording_policy=CompanionRecordingPolicy(
            sample_rate=0.5,
            body_max_bytes=1024,
            keep_inputs=False,
        ),
    )

    assert metadata.recording_policy is not None
    assert metadata.recording_policy.to_policy() == RecordingPolicy(
        sample_rate=0.5,
        body_max_bytes=1024,
        keep_inputs=False,
    )
