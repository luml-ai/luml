import logging
from typing import Any, cast

import httpx
import pytest
from luml_satellite import PlatformClient
from luml_satellite.container import (
    KUBERNETES_DERIVATION_FINGERPRINT_LABEL,
    KUBERNETES_LAUNCHER_PROTOCOL_LABEL,
)
from luml_satellite.testing import FakePlatform, ScriptedDeployCase

from luml_satellite_kubernetes import InMemoryKubernetesApi, KubernetesDriver
from luml_satellite_kubernetes.main import build_runtime
from luml_satellite_kubernetes.manifests import deployment_object_name
from tests.support import (
    ARTIFACT_ID,
    DEPLOYMENT_ID,
    OTHER_DEPLOYMENT_ID,
    close_runtime,
    configuration,
    deployment,
    deployment_record,
    start_context,
    upstream_transport,
)


@pytest.mark.asyncio
async def test_scripted_deploy_reaches_the_shared_status_sequence() -> None:
    fake_platform = FakePlatform()
    case = ScriptedDeployCase()
    case.seed(fake_platform)
    api = InMemoryKubernetesApi(auto_ready=True)
    config = configuration()

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = KubernetesDriver(config, api)
        runtime = build_runtime(
            config,
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await case.run_and_assert(runtime.polling, fake_platform)
        finally:
            await close_runtime(runtime)

    workload = api.object("Deployment", deployment_object_name(case.deployment_id))
    assert workload is not None
    assert workload["metadata"]["labels"][KUBERNETES_LAUNCHER_PROTOCOL_LABEL] == "1"
    assert workload["metadata"]["labels"][KUBERNETES_DERIVATION_FINGERPRINT_LABEL]
    assert fake_platform.deployments[case.deployment_id]["inference_url"] == (
        f"/deployments/{case.deployment_id}"
    )
    assert fake_platform.deployments[case.deployment_id]["provider_ref"] == (
        f"deployment/{deployment_object_name(case.deployment_id)}"
    )


@pytest.mark.asyncio
async def test_main_composition_pairs_reconciles_and_keeps_compute_out_of_process() -> None:
    fake_platform = FakePlatform()
    fake_platform.allowed_api_keys.add("access-key")
    config = configuration(SATELLITE_SLUG="custom-kubernetes-v1")
    api = InMemoryKubernetesApi()

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = KubernetesDriver(config, api)
        runtime = build_runtime(
            config,
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        application = cast(Any, runtime.public_application)
        try:
            await runtime.pair()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://satellite",
            ) as client:
                gated = await client.get(
                    "/deployments",
                    headers={"Authorization": "Bearer access-key"},
                )
                liveness = await client.get("/livez")
                compute = await client.post(
                    f"/deployments/{DEPLOYMENT_ID}/compute",
                    json={"value": 1},
                    headers={"Authorization": "Bearer access-key"},
                )
                internal = await client.get(f"/satellites/deployments/{DEPLOYMENT_ID}/companion")
            await runtime.reconcile()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://satellite",
            ) as client:
                deployments = await client.get(
                    "/deployments",
                    headers={"Authorization": "Bearer access-key"},
                )
                compute_after_reconciliation = await client.post(
                    f"/deployments/{DEPLOYMENT_ID}/compute",
                    json={"value": 1},
                    headers={"Authorization": "Bearer access-key"},
                )
        finally:
            await close_runtime(runtime)

    pair_request = next(
        request for request in fake_platform.requests if request.path == "/satellites/v1/pair"
    )
    body = cast(dict[str, Any], pair_request.body)
    assert gated.status_code == 503
    assert liveness.status_code == 200
    assert compute.status_code == 503
    assert compute_after_reconciliation.status_code == 404
    assert internal.status_code == 404
    assert deployments.status_code == 200
    assert deployments.json() == []
    assert body["slug"] == "custom-kubernetes-v1"
    assert body["kit"]["kind"] == "kubernetes"
    assert body["base_url"] == "http://satellite.example"
    assert isinstance(body["openapi"], dict)
    assert driver.platform_satellite_id == fake_platform.satellite_id


@pytest.mark.asyncio
async def test_satellite_monitoring_routes_are_in_the_pairing_document() -> None:
    fake_platform = FakePlatform()
    config = configuration(MONITORING_ENABLED=True)

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = KubernetesDriver(config, InMemoryKubernetesApi())
        runtime = build_runtime(
            config,
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
        finally:
            await close_runtime(runtime)

    pair_request = next(
        request for request in fake_platform.requests if request.path == "/satellites/v1/pair"
    )
    body = cast(dict[str, Any], pair_request.body)
    document = cast(dict[str, Any], body["openapi"])
    paths = cast(dict[str, Any], document["paths"])
    assert "/monitoring/launch" in paths
    assert "/deployments/{deployment_id}/monitoring/overview" in paths


@pytest.mark.asyncio
async def test_reissued_token_keeps_model_objects_and_companion_token() -> None:
    fake_platform = FakePlatform(token="new-token")
    fake_platform.add_deployment(
        deployment_record(
            status="active",
            inference_url=f"/deployments/{DEPLOYMENT_ID}",
        )
    )
    old_config = configuration(SATELLITE_TOKEN="old-token")
    api = InMemoryKubernetesApi(auto_ready=True)
    old_driver = KubernetesDriver(old_config, api)
    await old_driver.start(deployment(status="active"), start_context(old_config))
    name = deployment_object_name(DEPLOYMENT_ID)
    old_secret = api.object("Secret", name)
    old_workload = api.object("Deployment", name)
    assert old_secret is not None
    assert old_workload is not None
    old_hash = old_workload["spec"]["template"]["metadata"]["annotations"]["luml.ai/secret-hash"]
    companion_token = old_driver.tokens.companion_token(DEPLOYMENT_ID)
    api.apply_calls.clear()

    new_config = configuration(SATELLITE_TOKEN="new-token")
    async with PlatformClient(
        "http://platform",
        "new-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = KubernetesDriver(new_config, api)
        runtime = build_runtime(
            new_config,
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        internal_application = cast(Any, runtime.internal_application)
        try:
            await runtime.pair()
            await runtime.reconcile()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=internal_application),
                base_url="http://satellite",
            ) as client:
                companion = await client.get(
                    f"/satellites/deployments/{DEPLOYMENT_ID}/companion",
                    headers={"Authorization": f"Bearer {companion_token}"},
                )
        finally:
            await close_runtime(runtime)

    current_secret = api.object("Secret", name)
    current_workload = api.object("Deployment", name)
    assert current_secret == old_secret
    assert current_workload is not None
    assert (
        current_workload["spec"]["template"]["metadata"]["annotations"]["luml.ai/secret-hash"]
        == old_hash
    )
    assert api.apply_calls == []
    assert companion.status_code == 200
    assert fake_platform.deployments[DEPLOYMENT_ID]["status"] == "active"
    assert fake_platform.deployment_transitions == []


@pytest.mark.asyncio
async def test_derivation_key_rotation_reapplies_and_adopts_all_model_objects() -> None:
    second_artifact_id = "20000000-0000-0000-0000-000000000002"
    fake_platform = FakePlatform()
    for record in (
        deployment_record(
            status="active",
            inference_url=f"/deployments/{DEPLOYMENT_ID}",
        ),
        deployment_record(
            id=OTHER_DEPLOYMENT_ID,
            artifact_id=second_artifact_id,
            status="active",
            inference_url=f"/deployments/{OTHER_DEPLOYMENT_ID}",
        ),
    ):
        fake_platform.add_deployment(record)
    fake_platform.add_artifact(ARTIFACT_ID, b"first")
    fake_platform.add_artifact(second_artifact_id, b"second")

    old_config = configuration(DERIVATION_KEY="old-derivation-key")
    api = InMemoryKubernetesApi(auto_ready=True)
    old_driver = KubernetesDriver(old_config, api)
    await old_driver.start(
        deployment(status="active"),
        start_context(old_config),
    )
    await old_driver.start(
        deployment(
            id=OTHER_DEPLOYMENT_ID,
            artifact_id=second_artifact_id,
            status="active",
        ),
        start_context(
            old_config,
            deployment_id=OTHER_DEPLOYMENT_ID,
            artifact_id=second_artifact_id,
        ),
    )
    old_hashes: dict[str, str] = {}
    for deployment_id in (DEPLOYMENT_ID, OTHER_DEPLOYMENT_ID):
        workload = api.object("Deployment", deployment_object_name(deployment_id))
        assert workload is not None
        old_hashes[deployment_id] = workload["spec"]["template"]["metadata"]["annotations"][
            "luml.ai/secret-hash"
        ]
    api.apply_calls.clear()

    new_config = configuration(DERIVATION_KEY="new-derivation-key")
    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = KubernetesDriver(new_config, api)
        runtime = build_runtime(
            new_config,
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await runtime.reconcile()
            assert set(runtime.convergence.in_progress) == {
                DEPLOYMENT_ID,
                OTHER_DEPLOYMENT_ID,
            }
            await runtime.health_pass()
            assert set(runtime.convergence.in_progress) == {
                DEPLOYMENT_ID,
                OTHER_DEPLOYMENT_ID,
            }
            await runtime.poll()
            assert runtime.convergence.in_progress == {}
        finally:
            await close_runtime(runtime)

    assert len(api.apply_calls) == 8
    for deployment_id in (DEPLOYMENT_ID, OTHER_DEPLOYMENT_ID):
        workload = api.object("Deployment", deployment_object_name(deployment_id))
        secret = api.object("Secret", deployment_object_name(deployment_id))
        assert workload is not None
        assert secret is not None
        labels = workload["metadata"]["labels"]
        assert labels[KUBERNETES_DERIVATION_FINGERPRINT_LABEL] == driver.tokens.fingerprint
        assert (
            workload["spec"]["template"]["metadata"]["annotations"]["luml.ai/secret-hash"]
            != old_hashes[deployment_id]
        )
        assert secret["stringData"]["companion-token"] == driver.tokens.companion_token(
            deployment_id
        )
        assert fake_platform.deployments[deployment_id]["status"] == "active"
    assert fake_platform.deployment_transitions == []


@pytest.mark.asyncio
async def test_reconciliation_warns_without_touching_workloads_outside_tightened_limits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_platform = FakePlatform()
    fake_platform.add_deployment(
        deployment_record(
            status="active",
            satellite_parameters={"cpu_millicores": 8_000},
            inference_url=f"/deployments/{DEPLOYMENT_ID}",
        )
    )
    fake_platform.add_deployment(
        deployment_record(
            id=OTHER_DEPLOYMENT_ID,
            artifact_id="artifact-two",
            status="active",
            satellite_parameters={"use_gpu": True},
            inference_url=f"/deployments/{OTHER_DEPLOYMENT_ID}",
        )
    )
    old_config = configuration(
        DEPLOYMENT_CPU_MAX_MILLICORES=10_000,
        GPU_OFFERED=True,
    )
    api = InMemoryKubernetesApi(auto_ready=True)
    old_driver = KubernetesDriver(old_config, api)
    await old_driver.start(
        deployment(
            status="active",
            satellite_parameters={"cpu_millicores": 8_000},
        ),
        start_context(old_config, parameters={"cpu_millicores": 8_000}),
    )
    await old_driver.start(
        deployment(
            id=OTHER_DEPLOYMENT_ID,
            artifact_id="artifact-two",
            status="active",
            satellite_parameters={"use_gpu": True},
        ),
        start_context(old_config, parameters={"use_gpu": True}),
    )
    api.apply_calls.clear()
    tightened = configuration(
        DEPLOYMENT_CPU_MAX_MILLICORES=4_000,
        GPU_OFFERED=False,
    )
    caplog.set_level(logging.WARNING, logger="luml_satellite.runtime")

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = KubernetesDriver(tightened, api)
        runtime = build_runtime(
            tightened,
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await runtime.reconcile()
            for deployment_id in (DEPLOYMENT_ID, OTHER_DEPLOYMENT_ID):
                name = deployment_object_name(deployment_id)
                workload = api.object("Deployment", name)
                assert workload is not None
                workload["status"] = {"availableReplicas": 0, "readyReplicas": 0}
                api.put(workload)
            await runtime.health_pass()
        finally:
            await close_runtime(runtime)

    assert "cpu_millicores" in caplog.text
    assert "use_gpu" in caplog.text
    assert DEPLOYMENT_ID in caplog.text
    assert OTHER_DEPLOYMENT_ID in caplog.text
    assert api.apply_calls == []
    for deployment_id in (DEPLOYMENT_ID, OTHER_DEPLOYMENT_ID):
        record = fake_platform.deployments[deployment_id]
        assert record["status"] == "not_responding"
        assert "Invalid deployment settings" in record["error_message"]["error"]
