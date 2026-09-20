from dataclasses import replace
from typing import Any

import pytest
from luml_satellite import StartStatus, TokenDeriver, WorkloadState
from luml_satellite.container import (
    KUBERNETES_DEPLOYMENT_LABEL,
    KUBERNETES_DERIVATION_FINGERPRINT_LABEL,
    KUBERNETES_LAUNCHER_PROTOCOL_LABEL,
    KUBERNETES_MANAGED_BY_LABEL,
    KUBERNETES_SATELLITE_LABEL,
    KUBERNETES_SHARED_LABEL,
)
from luml_satellite.testing import DriverConformanceSuite

from luml_satellite_kubernetes import (
    InMemoryKubernetesApi,
    KubernetesDeploymentSettings,
    KubernetesDriver,
)
from luml_satellite_kubernetes.manifests import deployment_object_name
from tests.support import (
    ARTIFACT_ID,
    DEPLOYMENT_ID,
    OTHER_DEPLOYMENT_ID,
    configuration,
    deployment,
    start_context,
)


@pytest.mark.asyncio
async def test_start_applies_four_objects_idempotently_and_updates_changed_settings() -> None:
    config = configuration(GPU_OFFERED=True)
    api = InMemoryKubernetesApi(auto_ready=False)
    driver = KubernetesDriver(config, api)

    first = await driver.start(
        deployment(),
        start_context(config, parameters={"replicas": 1}),
    )
    second = await driver.start(
        deployment(),
        start_context(config, parameters={"replicas": 3}),
    )

    assert first.status is StartStatus.IN_PROGRESS
    assert first.provider_ref == f"deployment/{deployment_object_name(DEPLOYMENT_ID)}"
    assert first.progress_note == "0/1 pods ready"
    assert second.progress_note == "0/3 pods ready"
    assert len(api.objects) == 4
    assert len(api.apply_calls) == 8
    workload = api.object("Deployment", deployment_object_name(DEPLOYMENT_ID))
    assert workload is not None
    assert workload["spec"]["replicas"] == 3


@pytest.mark.asyncio
async def test_shared_cache_without_a_claim_fails_before_applying_an_object() -> None:
    config = configuration(SHARED_CACHE_CLAIM_NAME=None)
    api = InMemoryKubernetesApi()
    driver = KubernetesDriver(config, api)
    context = replace(
        start_context(config),
        settings=KubernetesDeploymentSettings(artifact_cache="shared"),
    )

    result = await driver.start(deployment(), context)

    assert result.status is StartStatus.FAILED
    assert result.reason == "Shared cache unavailable"
    assert "shared cache claim" in (result.error or "")
    assert api.apply_calls == []


@pytest.mark.asyncio
async def test_observe_maps_ready_and_ready_wins_over_a_failing_pod() -> None:
    driver, api = await _started_driver()
    workload = _workload(api)
    workload["status"] = {"availableReplicas": 1, "readyReplicas": 1, "replicas": 2}
    api.put(workload)
    api.put(_pod(workload, waiting=("model", "CrashLoopBackOff", "crashed")))

    observation = await driver.observe(DEPLOYMENT_ID)

    assert observation.state is WorkloadState.READY
    assert observation.launcher_protocol == "1"
    assert observation.provider_ref == f"deployment/{deployment_object_name(DEPLOYMENT_ID)}"


@pytest.mark.asyncio
async def test_observe_waits_until_a_ready_replica_is_available() -> None:
    driver, api = await _started_driver()
    workload = _workload(api)
    workload["spec"]["replicas"] = 2
    workload["status"] = {"availableReplicas": 0, "readyReplicas": 1, "replicas": 2}
    api.put(workload)

    observation = await driver.observe(DEPLOYMENT_ID)

    assert observation.state is WorkloadState.STARTING
    assert observation.progress_note == "1/2 pods ready"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "message"),
    [
        ("ErrImagePull", "registry denied the image"),
        ("ImagePullBackOff", "back-off pulling image"),
        ("CrashLoopBackOff", "sidecar keeps exiting"),
    ],
)
async def test_observe_maps_failing_regular_containers_with_logs(
    reason: str,
    message: str,
) -> None:
    driver, api = await _started_driver()
    workload = _workload(api)
    pod = _pod(workload, waiting=("model", reason, message))
    api.put(pod)
    pod_name = pod["metadata"]["name"]
    api.logs[(pod_name, "model")] = "".join(f"line-{index}\n" for index in range(120))

    observation = await driver.observe(DEPLOYMENT_ID)

    assert observation.state is WorkloadState.FAILED
    assert observation.error == f"{reason}: {message}"
    assert observation.recent_logs.startswith("line-20")
    assert "line-0\n" not in observation.recent_logs


@pytest.mark.asyncio
async def test_observe_keeps_pending_gpu_and_restarting_init_containers_starting() -> None:
    driver, api = await _started_driver()
    workload = _workload(api)
    pending = _pod(
        workload,
        conditions=[
            {
                "type": "PodScheduled",
                "status": "False",
                "message": "0/2 nodes have insufficient amd.com/gpu",
            }
        ],
    )
    api.put(pending)

    gpu = await driver.observe(DEPLOYMENT_ID)

    assert gpu.state is WorkloadState.STARTING
    assert gpu.progress_note == "0/1 pods ready: 0/2 nodes have insufficient amd.com/gpu"

    pending["status"] = {
        "phase": "Pending",
        "initContainerStatuses": [
            {
                "name": "artifact-fetch",
                "restartCount": 1,
                "state": {"terminated": {"exitCode": 1, "reason": "Error"}},
            }
        ],
    }
    api.put(pending)

    restarting = await driver.observe(DEPLOYMENT_ID)

    assert restarting.state is WorkloadState.STARTING
    assert restarting.error is None


@pytest.mark.asyncio
async def test_observe_fails_an_init_container_only_in_crash_loop_backoff() -> None:
    driver, api = await _started_driver()
    workload = _workload(api)
    pod = _pod(
        workload,
        init_waiting=("artifact-fetch", "CrashLoopBackOff", "archive is invalid"),
    )
    api.put(pod)
    api.logs[(pod["metadata"]["name"], "artifact-fetch")] = "unpack failed\n"

    observation = await driver.observe(DEPLOYMENT_ID)

    assert observation.state is WorkloadState.FAILED
    assert observation.error == "CrashLoopBackOff: archive is invalid"
    assert observation.recent_logs == "unpack failed\n"


@pytest.mark.asyncio
async def test_observe_maps_a_missing_deployment() -> None:
    driver = KubernetesDriver(configuration(), InMemoryKubernetesApi())

    observation = await driver.observe(DEPLOYMENT_ID)

    assert observation.state is WorkloadState.MISSING


@pytest.mark.asyncio
async def test_bulk_observe_uses_exactly_one_deployment_and_one_pod_list() -> None:
    config = configuration()
    api = InMemoryKubernetesApi(auto_ready=True)
    driver = KubernetesDriver(config, api)
    for deployment_id in [DEPLOYMENT_ID, OTHER_DEPLOYMENT_ID, "third", "fourth", "fifth"]:
        await driver.start(
            deployment(id=deployment_id, artifact_id=f"artifact-{deployment_id}"),
            start_context(config),
        )
    api.list_calls.clear()

    observations = await driver.observe_all(
        {DEPLOYMENT_ID, OTHER_DEPLOYMENT_ID, "third", "fourth", "fifth"}
    )

    assert all(item.state is WorkloadState.READY for item in observations.values())
    assert [kind for kind, _ in api.list_calls] == ["Deployment", "Pod"]


@pytest.mark.asyncio
async def test_stale_derivation_fingerprint_requests_reapplication() -> None:
    driver, api = await _started_driver(auto_ready=True)
    workload = _workload(api)
    workload["metadata"]["labels"][KUBERNETES_DERIVATION_FINGERPRINT_LABEL] = "stale"
    api.put(workload)

    observation = await driver.observe(DEPLOYMENT_ID)

    assert observation.state is WorkloadState.READY
    assert observation.needs_reapply is True


@pytest.mark.asyncio
async def test_remove_verifies_all_four_objects_and_reports_the_artifact() -> None:
    driver, api = await _started_driver(auto_ready=True)

    result = await driver.remove(DEPLOYMENT_ID)

    assert result.removed is True
    assert result.verified is True
    assert result.artifact_id == ARTIFACT_ID
    assert driver.removal_rechecks == 1
    assert api.objects == {}


@pytest.mark.asyncio
async def test_remove_is_unverified_when_an_object_outlives_the_poll() -> None:
    driver, api = await _started_driver(auto_ready=True)
    name = deployment_object_name(DEPLOYMENT_ID)
    api.blocked_deletions.add(("Deployment", name))

    result = await driver.remove(DEPLOYMENT_ID)

    assert result.removed is True
    assert result.verified is False
    assert api.object("Deployment", name) is not None


@pytest.mark.asyncio
async def test_two_releases_in_one_namespace_keep_workloads_apart() -> None:
    api = InMemoryKubernetesApi(namespace="models", auto_ready=True)
    first_config = configuration(SATELLITE_NAME="release-one")
    second_config = configuration(SATELLITE_NAME="release-two")
    first = KubernetesDriver(first_config, api)
    second = KubernetesDriver(second_config, api)
    await first.start(deployment(), start_context(first_config))
    await second.start(
        deployment(id=OTHER_DEPLOYMENT_ID, artifact_id="artifact-two"),
        start_context(second_config),
    )

    first_list = await first.list_workloads()
    second_list = await second.list_workloads()
    first_observations = await first.observe_all({DEPLOYMENT_ID, OTHER_DEPLOYMENT_ID})
    second_observations = await second.observe_all({DEPLOYMENT_ID, OTHER_DEPLOYMENT_ID})

    assert [(item.deployment_id, item.owned) for item in first_list] == [
        (DEPLOYMENT_ID, True),
        (OTHER_DEPLOYMENT_ID, False),
    ]
    assert [(item.deployment_id, item.owned) for item in second_list] == [
        (DEPLOYMENT_ID, False),
        (OTHER_DEPLOYMENT_ID, True),
    ]
    assert first_observations[DEPLOYMENT_ID].state is WorkloadState.READY
    assert first_observations[OTHER_DEPLOYMENT_ID].state is WorkloadState.MISSING
    assert second_observations[DEPLOYMENT_ID].state is WorkloadState.MISSING
    assert second_observations[OTHER_DEPLOYMENT_ID].state is WorkloadState.READY


@pytest.mark.asyncio
async def test_listing_distinguishes_owned_shared_foreign_and_unidentified_workloads() -> None:
    config = configuration()
    api = InMemoryKubernetesApi()
    driver = KubernetesDriver(config, api)
    api.put(_listed_deployment("owned", config.SATELLITE_NAME, shared=False))
    api.put(_listed_deployment("shared", config.SATELLITE_NAME, shared=True))
    api.put(_listed_deployment("foreign", "another-release", shared=False))
    unidentified = _listed_deployment(None, config.SATELLITE_NAME, shared=False)
    api.put(unidentified)

    workloads = await driver.list_workloads()

    assert [(item.deployment_id, item.owned, item.shared) for item in workloads] == [
        ("owned", True, False),
        ("shared", True, True),
        ("foreign", False, False),
        (None, True, False),
    ]


@pytest.mark.asyncio
async def test_driver_passes_the_shared_conformance_suite() -> None:
    config = configuration()
    api = InMemoryKubernetesApi(auto_ready=True)
    driver = KubernetesDriver(config, api)
    suite = DriverConformanceSuite(
        driver,
        removal_recheck_count=lambda: driver.removal_rechecks,
    )

    await suite.run(deployment(), start_context(config))

    assert driver.removal_rechecks == 1


@pytest.mark.asyncio
async def test_sweep_runs_only_for_a_shared_cache() -> None:
    without_cache = InMemoryKubernetesApi()
    without_driver = KubernetesDriver(configuration(), without_cache)
    with_config = configuration(
        SHARED_CACHE_CLAIM_NAME="release-one-cache",
        SERVING_IMAGE_PULL_POLICY="Always",
        IMAGE_PULL_SECRETS=["private-registry"],
    )
    with_cache = InMemoryKubernetesApi()
    with_driver = KubernetesDriver(with_config, with_cache)

    await without_driver.sweep({ARTIFACT_ID})
    await with_driver.sweep({ARTIFACT_ID})

    assert without_cache.apply_calls == []
    assert with_cache.apply_calls == [("Job", "release-one-cache-sweep")]
    job = with_cache.object("Job", "release-one-cache-sweep")
    assert job is not None
    assert job["spec"]["template"]["spec"]["containers"][0]["env"] == [
        {"name": "MODEL_ARTIFACT_KEEP", "value": ARTIFACT_ID}
    ]
    assert job["spec"]["template"]["spec"]["containers"][0]["imagePullPolicy"] == "Always"
    assert job["spec"]["template"]["spec"]["imagePullSecrets"] == [{"name": "private-registry"}]


@pytest.mark.asyncio
async def test_sweep_name_is_valid_for_the_longest_helm_release_name() -> None:
    config = configuration(
        SATELLITE_NAME="a" * 53,
        SHARED_CACHE_CLAIM_NAME="shared-cache",
    )
    api = InMemoryKubernetesApi()
    driver = KubernetesDriver(config, api)

    await driver.sweep({ARTIFACT_ID})

    kind, name = api.apply_calls[0]
    assert kind == "Job"
    assert len(name) == 63
    assert name.endswith("-cache-sweep")


async def _started_driver(
    *,
    auto_ready: bool = False,
) -> tuple[KubernetesDriver, InMemoryKubernetesApi]:
    config = configuration()
    api = InMemoryKubernetesApi(auto_ready=auto_ready)
    driver = KubernetesDriver(config, api)
    await driver.start(deployment(), start_context(config))
    return driver, api


def _workload(api: InMemoryKubernetesApi) -> dict[str, Any]:
    workload = api.object("Deployment", deployment_object_name(DEPLOYMENT_ID))
    assert workload is not None
    return workload


def _pod(
    workload: dict[str, Any],
    *,
    waiting: tuple[str, str, str] | None = None,
    init_waiting: tuple[str, str, str] | None = None,
    conditions: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    status: dict[str, Any] = {"phase": "Pending"}
    if waiting is not None:
        name, reason, message = waiting
        status["containerStatuses"] = [
            {"name": name, "state": {"waiting": {"reason": reason, "message": message}}}
        ]
    if init_waiting is not None:
        name, reason, message = init_waiting
        status["initContainerStatuses"] = [
            {"name": name, "state": {"waiting": {"reason": reason, "message": message}}}
        ]
    if conditions is not None:
        status["conditions"] = conditions
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "model-pod",
            "namespace": "models",
            "labels": dict(workload["metadata"]["labels"]),
        },
        "status": status,
    }


def _listed_deployment(
    deployment_id: str | None,
    satellite_name: str,
    *,
    shared: bool,
) -> dict[str, Any]:
    labels = {
        KUBERNETES_MANAGED_BY_LABEL: "luml-satellite",
        KUBERNETES_SATELLITE_LABEL: satellite_name,
        KUBERNETES_SHARED_LABEL: str(shared).lower(),
        KUBERNETES_LAUNCHER_PROTOCOL_LABEL: "1",
        KUBERNETES_DERIVATION_FINGERPRINT_LABEL: TokenDeriver(
            "test-token",
            "stable-derivation-key",
        ).fingerprint,
    }
    if deployment_id is not None:
        labels[KUBERNETES_DEPLOYMENT_LABEL] = deployment_id
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": f"workload-{deployment_id or 'unknown'}",
            "namespace": "models",
            "labels": labels,
        },
        "spec": {"replicas": 1},
        "status": {"availableReplicas": 1},
    }
