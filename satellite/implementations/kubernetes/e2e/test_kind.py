import argparse
import http.client
import json
import socket
import subprocess
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, cast

from e2e.create_state import (
    GPU_DEPLOYMENT_ID,
    MAIN_DEPLOYMENT_ID,
    REPLICA_DEPLOYMENT_ID,
    SATELLITE_TOKEN,
    VALID_API_KEY,
    task_record,
)

_BUILT_IMAGES = {
    "luml-e2e/kubernetes:local",
    "luml-e2e/monitoring:local",
    "luml-e2e/serving:local",
    "luml-e2e/stub-model:local",
}


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> dict[str, Any]:
        value = json.loads(self.body)
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        return value


class PlatformControl:
    def __init__(self, port: int) -> None:
        self.port = port

    def state(self) -> dict[str, Any]:
        result = _http(self.port, "GET", "/__fake__/state", bearer=SATELLITE_TOKEN)
        if result.status != 200:
            raise AssertionError(f"fake platform state returned {result.status}: {result.body!r}")
        return result.json()

    def seed(self, body: Mapping[str, object]) -> None:
        result = _http(
            self.port,
            "POST",
            "/__fake__/state",
            bearer=SATELLITE_TOKEN,
            json_body=body,
        )
        if result.status != 204:
            raise AssertionError(f"fake platform seed returned {result.status}: {result.body!r}")


def _run(
    *command: str,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        check=check,
    )


def _kubectl(namespace: str, *arguments: str, input_text: str | None = None) -> str:
    return _run("kubectl", "-n", namespace, *arguments, input_text=input_text).stdout.strip()


def _kubectl_json(namespace: str, *arguments: str) -> dict[str, Any]:
    output = _kubectl(namespace, *arguments, "-o", "json")
    return cast(dict[str, Any], json.loads(output))


def _http(
    port: int,
    method: str,
    path: str,
    *,
    host: str | None = None,
    bearer: str | None = None,
    json_body: Mapping[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
) -> HttpResult:
    request_headers = dict(headers or {})
    if host is not None:
        request_headers["Host"] = host
    if bearer is not None:
        request_headers["Authorization"] = f"Bearer {bearer}"
    body: bytes | None = None
    if json_body is not None:
        body = json.dumps(json_body, separators=(",", ":")).encode()
        request_headers["Content-Type"] = "application/json"
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        return HttpResult(
            response.status,
            {name.lower(): value for name, value in response.getheaders()},
            response.read(),
        )
    finally:
        connection.close()


def _wait_for[T](
    description: str,
    check: Callable[[], T | None],
    *,
    timeout: float = 600,
    interval: float = 2,
) -> T:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result is not None:
                return result
        except Exception as error:
            last_error = error
        time.sleep(interval)
    suffix = f"; last error: {last_error}" if last_error is not None else ""
    raise AssertionError(f"timed out waiting for {description}{suffix}")


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@contextmanager
def _port_forward(namespace: str, resource: str, remote_port: int) -> Iterator[int]:
    local_port = _free_port()
    process = subprocess.Popen(
        [
            "kubectl",
            "-n",
            namespace,
            "port-forward",
            resource,
            f"{local_port}:{remote_port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:

        def forwarded() -> bool | None:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr is not None else ""
                raise RuntimeError(f"port-forward exited: {stderr}")
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=0.2):
                    return True
            except OSError:
                return None

        _wait_for(f"port-forward to {resource}", forwarded, timeout=30, interval=0.1)
        yield local_port
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _deployment(control: PlatformControl, deployment_id: str) -> dict[str, Any] | None:
    for deployment in control.state()["deployments"]:
        if deployment.get("id") == deployment_id:
            return cast(dict[str, Any], deployment)
    return None


def _assert_pairing(control: PlatformControl) -> None:
    def paired() -> bool | None:
        for request in control.state()["requests"]:
            if request.get("method") != "POST" or request.get("path") != "/satellites/v1/pair":
                continue
            body = request.get("body") or {}
            if body.get("kit", {}).get("kind") == "kubernetes":
                return True
        return None

    _wait_for("Kubernetes pairing", paired)


def _wait_for_deployments(control: PlatformControl) -> None:
    def active() -> bool | None:
        main = _deployment(control, MAIN_DEPLOYMENT_ID)
        replica = _deployment(control, REPLICA_DEPLOYMENT_ID)
        if main is None or replica is None:
            return None
        if main.get("status") != "active" or replica.get("status") != "active":
            return None
        assert main["inference_url"] == f"/deployments/{MAIN_DEPLOYMENT_ID}"
        assert replica["inference_url"] == f"/deployments/{REPLICA_DEPLOYMENT_ID}"
        return True

    def insufficient_gpu() -> bool | None:
        gpu = _deployment(control, GPU_DEPLOYMENT_ID)
        note = str((gpu or {}).get("progress_note") or "")
        if "insufficient" in note.lower() and "nvidia.com/gpu" in note:
            return True
        return None

    _wait_for("active monitored and replicated deployments", active)
    _wait_for("the insufficient-GPU progress note", insufficient_gpu)


def _assert_public_serving(host: str) -> str:
    compute_path = f"/deployments/{MAIN_DEPLOYMENT_ID}/compute"
    valid = _http(
        18080,
        "POST",
        compute_path,
        host=host,
        bearer=VALID_API_KEY,
        json_body={"value": 7},
    )
    assert valid.status == 200, valid.body
    assert valid.headers.get("x-event-id")
    assert valid.json()["fixture"] == {"prediction": 42}

    denied = _http(
        18080,
        "POST",
        compute_path,
        host=host,
        bearer="invalid-api-key",
        json_body={"value": 7},
    )
    assert denied.status == 401, denied.body

    schema = _http(
        18080,
        "GET",
        f"/deployments/{MAIN_DEPLOYMENT_ID}/openapi.json",
        host=host,
        bearer=VALID_API_KEY,
    )
    assert schema.status == 200, schema.body
    assert schema.json()["info"]["title"] == "LUML stub model"

    internal = _http(
        18080,
        "GET",
        f"/satellites/deployments/{MAIN_DEPLOYMENT_ID}/artifact",
        host=host,
    )
    assert internal.status == 404, internal.body
    return compute_path


def _satellite_deployment(namespace: str) -> str:
    data = _kubectl_json(
        namespace,
        "get",
        "deployment",
        "-l",
        "app.kubernetes.io/component=satellite",
    )
    items = data.get("items", [])
    if len(items) != 1:
        raise AssertionError(f"expected one satellite Deployment, found {len(items)}")
    return str(items[0]["metadata"]["name"])


def _assert_serving_survives_satellite_outage(namespace: str, host: str, path: str) -> None:
    deployment = _satellite_deployment(namespace)
    pods = _kubectl_json(
        namespace,
        "get",
        "pod",
        "-l",
        "app.kubernetes.io/component=satellite",
    )["items"]
    assert len(pods) == 1
    _kubectl(namespace, "delete", "pod", pods[0]["metadata"]["name"], "--wait=false")
    _kubectl(namespace, "scale", f"deployment/{deployment}", "--replicas=0")

    def no_satellite_pod() -> bool | None:
        current = _kubectl_json(
            namespace,
            "get",
            "pod",
            "-l",
            "app.kubernetes.io/component=satellite",
        )["items"]
        return True if not current else None

    _wait_for("the satellite outage", no_satellite_pod, timeout=120)
    response = _http(
        18080,
        "POST",
        path,
        host=host,
        bearer=VALID_API_KEY,
        json_body={"during": "satellite-outage"},
    )
    assert response.status == 200, response.body
    _kubectl(namespace, "scale", f"deployment/{deployment}", "--replicas=1")
    _kubectl(namespace, "rollout", "status", f"deployment/{deployment}", "--timeout=5m")


def _ready_replica_pods(namespace: str) -> list[dict[str, Any]] | None:
    items = _kubectl_json(
        namespace,
        "get",
        "pod",
        "-l",
        f"luml.ai/deployment-id={REPLICA_DEPLOYMENT_ID}",
    )["items"]
    if len(items) != 3:
        return None
    for item in items:
        conditions = item.get("status", {}).get("conditions", [])
        if not any(
            condition.get("type") == "Ready" and condition.get("status") == "True"
            for condition in conditions
        ):
            return None
    return cast(list[dict[str, Any]], items)


def _assert_three_replicas_answer(namespace: str) -> list[dict[str, Any]]:
    pods = _wait_for("three ready model replicas", lambda: _ready_replica_pods(namespace))
    script = (
        "import json,sys,urllib.request;"
        "r=urllib.request.Request("
        "'http://127.0.0.1:8000/deployments/'+sys.argv[1]+'/compute',"
        "data=b'{\"value\":1}',headers={'Authorization':'Bearer '+sys.argv[2],"
        "'Content-Type':'application/json'},method='POST');"
        "print(urllib.request.urlopen(r,timeout=10).read().decode())"
    )
    for pod in pods:
        name = str(pod["metadata"]["name"])

        def answers(pod_name: str = name) -> bool | None:
            try:
                output = _kubectl(
                    namespace,
                    "exec",
                    pod_name,
                    "-c",
                    "sidecar",
                    "--",
                    "python",
                    "-c",
                    script,
                    REPLICA_DEPLOYMENT_ID,
                    VALID_API_KEY,
                )
                return True if json.loads(output)["replica"] == pod_name else None
            except json.JSONDecodeError, subprocess.CalledProcessError:
                return None

        _wait_for(f"replica {name} to answer", answers, timeout=120)
    return pods


def _assert_model_port_is_blocked(namespace: str, target_pod: Mapping[str, Any]) -> None:
    pod_ip = str(target_pod["status"]["podIP"])
    script = (
        "import socket,sys;"
        "s=socket.socket();s.settimeout(3);"
        "result=1;"
        "\ntry:\n s.connect((sys.argv[1],8080))\n"
        "except OSError:\n result=0\n"
        "finally:\n s.close()\n"
        "sys.exit(result)"
    )
    _kubectl(
        namespace,
        "exec",
        "network-probe",
        "--",
        "python",
        "-c",
        script,
        pod_ip,
    )


def _launch_monitoring(host: str) -> str:
    launch = _http(
        18080,
        "GET",
        "/monitoring/launch?token=ci-monitoring-launch-token",
        host=host,
    )
    assert launch.status == 303, launch.body
    assert launch.headers["location"] == "/monitoring/app/"
    cookies: SimpleCookie = SimpleCookie()
    cookies.load(launch.headers["set-cookie"])
    session = cookies["monitoring_session"].value
    _assert_monitoring_session(host, session)
    return session


def _assert_monitoring_session(host: str, session: str) -> None:
    response = _http(
        18080,
        "GET",
        "/monitoring/api/session",
        host=host,
        headers={"Cookie": f"monitoring_session={session}"},
    )
    assert response.status == 200, response.body
    assert response.json()["deployment_id"] == MAIN_DEPLOYMENT_ID


def _derivation_key(namespace: str, release: str) -> str:
    secret = _kubectl_json(
        namespace,
        "get",
        "secret",
        f"{release}-luml-satellite-kubernetes-derivation-key",
    )
    return str(secret["data"]["derivation-key"])


def _assert_upgrade_keeps_sessions(
    namespace: str,
    release: str,
    chart: Path,
    host: str,
    session: str,
) -> None:
    before = _derivation_key(namespace, release)
    _run(
        "helm",
        "upgrade",
        release,
        str(chart),
        "--namespace",
        namespace,
        "--reuse-values",
        "--wait",
        "--timeout",
        "10m",
    )
    after = _derivation_key(namespace, release)
    assert after == before
    _assert_monitoring_session(host, session)


def _orphan_manifest(name: str, deployment_id: str, satellite_id: str, run_as_user: int) -> str:
    manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "labels": {
                "app.kubernetes.io/managed-by": "luml-satellite",
                "luml.ai/deployment-id": deployment_id,
                "luml.ai/satellite-id": satellite_id,
                "luml.ai/shared": "false",
            },
        },
        "spec": {
            "replicas": 0,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": run_as_user,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "placeholder",
                            "image": "luml-e2e/stub-model:local",
                            "securityContext": {
                                "runAsNonRoot": True,
                                "runAsUser": run_as_user,
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                            },
                        }
                    ],
                },
            },
        },
    }
    return json.dumps(manifest)


def _resource_exists(namespace: str, kind: str, name: str) -> bool:
    completed = _run("kubectl", "-n", namespace, "get", kind, name, check=False)
    return completed.returncode == 0


def _assert_orphan_rules(namespace: str, release: str, run_as_user: int) -> None:
    owned_id = "90000000-0000-0000-0000-000000000001"
    foreign_id = "90000000-0000-0000-0000-000000000002"
    owned_name = f"luml-dep-{owned_id}"
    foreign_name = f"luml-dep-{foreign_id}"
    _kubectl(
        namespace,
        "apply",
        "-f",
        "-",
        input_text=_orphan_manifest(owned_name, owned_id, release, run_as_user),
    )
    _kubectl(
        namespace,
        "apply",
        "-f",
        "-",
        input_text=_orphan_manifest(foreign_name, foreign_id, "foreign-satellite", run_as_user),
    )
    deployment = _satellite_deployment(namespace)
    _kubectl(namespace, "rollout", "restart", f"deployment/{deployment}")
    _kubectl(namespace, "rollout", "status", f"deployment/{deployment}", "--timeout=5m")
    _wait_for(
        "owned orphan cleanup",
        lambda: True if not _resource_exists(namespace, "deployment", owned_name) else None,
        timeout=180,
    )
    assert _resource_exists(namespace, "deployment", foreign_name)


def _assert_arbitrary_user(namespace: str, random_user: int) -> None:
    pods = _kubectl_json(namespace, "get", "pods")["items"]
    checked = 0
    for pod in pods:
        pod_name = str(pod["metadata"]["name"])
        pod_spec = pod["spec"]
        statuses = {
            status["name"]: status for status in pod.get("status", {}).get("containerStatuses", [])
        }
        for container in pod_spec.get("containers", []):
            if container.get("image") not in _BUILT_IMAGES:
                continue
            status = statuses.get(container["name"], {})
            if "running" not in status.get("state", {}):
                continue
            output = _kubectl(
                namespace,
                "exec",
                pod_name,
                "-c",
                container["name"],
                "--",
                "python",
                "-c",
                "import os; print(f'{os.getuid()}:{os.getgid()}')",
            )
            assert output == f"{random_user}:0", (pod_name, container["name"], output)
            assert pod_spec["securityContext"]["fsGroup"] == random_user
            assert "runAsGroup" not in pod_spec["securityContext"]
            checked += 1
    assert checked >= 6


def _assert_undeploy(control: PlatformControl, namespace: str) -> None:
    deployment = _deployment(control, MAIN_DEPLOYMENT_ID)
    if deployment is None:
        raise AssertionError("main deployment disappeared before undeploy")
    deployment["status"] = "deletion_pending"
    undeploy_task = task_record(
        "20000000-0000-0000-0000-000000000004",
        MAIN_DEPLOYMENT_ID,
        "undeploy",
    )
    control.seed({"deployments": [deployment], "tasks": [undeploy_task]})

    def removed() -> bool | None:
        state = control.state()
        deployments = {item["id"] for item in state["deployments"]}
        task = next(item for item in state["tasks"] if item["id"] == undeploy_task["id"])
        if MAIN_DEPLOYMENT_ID not in deployments and task["status"] == "done":
            return True
        return None

    _wait_for("verified undeploy", removed, timeout=180)
    name = f"luml-dep-{MAIN_DEPLOYMENT_ID}"
    for kind in ("deployment", "service", "ingress", "secret"):
        assert not _resource_exists(namespace, kind, name), (kind, name)


def run_suite(
    preset: str,
    namespace: str,
    release: str,
    host: str,
    chart: Path,
    random_user: int,
) -> None:
    with _port_forward(namespace, "service/fake-platform", 8090) as platform_port:
        control = PlatformControl(platform_port)
        _assert_pairing(control)
        _wait_for_deployments(control)
        compute_path = _assert_public_serving(host)
        _assert_serving_survives_satellite_outage(namespace, host, compute_path)
        replica_pods = _assert_three_replicas_answer(namespace)
        _assert_model_port_is_blocked(namespace, replica_pods[0])
        session = _launch_monitoring(host)
        _assert_upgrade_keeps_sessions(namespace, release, chart, host, session)
        if preset == "openshift":
            _assert_arbitrary_user(namespace, random_user)
        _assert_orphan_rules(namespace, release, random_user)
        _assert_undeploy(control, namespace)


def main() -> None:
    parser = argparse.ArgumentParser(description="Assert the Kubernetes satellite kind scenario")
    parser.add_argument("--preset", choices=("vanilla", "openshift"), required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--chart", type=Path, required=True)
    parser.add_argument("--random-user", type=int, required=True)
    arguments = parser.parse_args()
    run_suite(
        arguments.preset,
        arguments.namespace,
        arguments.release,
        arguments.host,
        arguments.chart,
        arguments.random_user,
    )


if __name__ == "__main__":
    main()
