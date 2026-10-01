"""Deployments of registry artifacts onto the demo satellites."""

from __future__ import annotations

from typing import Any

from luml_demo.config import DemoConfig
from luml_demo.platform import PlatformClient
from luml_demo.shell import say, wait_for
from luml_demo.state import DemoState

DEPLOY_TIMEOUT = 2400


def existing_deployment(client: PlatformClient, state: DemoState, name: str) -> dict[str, Any] | None:
    for deployment in client.deployments(state.organization_id, state.orbit_id):
        if deployment["name"] == name and deployment["status"] not in ("deletion_pending", "failed"):
            return deployment
    return None


def ensure_deployment(
    client: PlatformClient,
    state: DemoState,
    *,
    name: str,
    artifact_id: str,
    satellite_slug: str,
    description: str,
    tags: list[str],
) -> dict[str, Any]:
    deployment = existing_deployment(client, state, name)
    if deployment is None:
        satellite_id = state.satellites[satellite_slug]["id"]
        deployment = client.create_deployment(state.organization_id, state.orbit_id, {
            "satellite_id": satellite_id,
            "artifact_id": artifact_id,
            "name": name,
            "monitoring_mode": "full",
            "satellite_parameters": {},
            "description": description,
            "env_variables": {},
            "tags": tags,
        })
        say(f"created deployment {name} ({deployment['id']}) on {satellite_slug}")
    state.deployments[name] = {
        "id": str(deployment["id"]),
        "satellite": satellite_slug,
        "artifact_id": artifact_id,
    }
    return deployment


def wait_active(client: PlatformClient, state: DemoState, name: str) -> dict[str, Any]:
    deployment_id = state.deployments[name]["id"]
    notes: set[str] = set()

    def active() -> bool:
        current = client.deployment(state.organization_id, state.orbit_id, deployment_id)
        note = str(current.get("progress_note") or "")
        if note and note not in notes:
            notes.add(note)
            say(f"  {name}: {note}")
        if current["status"] == "failed":
            raise RuntimeError(f"deployment {name} failed: {current.get('error_message')}")
        return str(current["status"]) == "active"

    wait_for(f"deployment {name} to become active (model env build)", active,
             timeout=DEPLOY_TIMEOUT, interval=10)
    record = client.deployment(state.organization_id, state.orbit_id, deployment_id)
    state.deployments[name].update({
        "inference_url": record.get("inference_url"),
        "monitoring_url": record.get("monitoring_url"),
    })
    return record


def inference_url(config: DemoConfig, state: DemoState, name: str) -> str:
    record = state.deployments[name]
    spec = config.satellite(record["satellite"])
    return f"http://localhost:{spec.port}/deployments/{record['id']}/compute"


def undeploy_all(client: PlatformClient, state: DemoState) -> None:
    for name, record in list(state.deployments.items()):
        try:
            client.delete_deployment(state.organization_id, state.orbit_id, record["id"])
            say(f"undeploy requested for {name}")
        except RuntimeError as error:
            say(f"undeploy {name}: {error}")

    def gone() -> bool:
        remaining = {
            d["name"] for d in client.deployments(state.organization_id, state.orbit_id)
            if d["name"] in state.deployments
        }
        return not remaining

    try:
        wait_for("deployments to be removed", gone, timeout=300, interval=5)
    except TimeoutError as error:
        say(str(error))
    state.deployments.clear()
