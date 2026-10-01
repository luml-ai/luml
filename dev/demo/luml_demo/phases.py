"""The ordered phases behind `luml-demo up`, each idempotent against the saved state."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from luml_prisma.demo.scenario import load_scenario, resolve_scenario_dir

from luml_demo import deployments, monitoring, platform, prisma_engine, registry, satellites
from luml_demo.config import SCENARIOS, DemoConfig, ScenarioSpec
from luml_demo.shell import say
from luml_demo.state import DemoState

PRISMA_RUN_TIMEOUT = 3600


def _save(config: DemoConfig, state: DemoState) -> None:
    state.save(config.state_path)


def _platform_client(config: DemoConfig, state: DemoState) -> platform.PlatformClient:
    """A session-authenticated client: some routes (organizations, API keys) refuse API keys."""
    client = platform.PlatformClient(config.api_url)
    client.signin(config.admin_email, config.admin_password)
    state.user_id = client.user_id
    return client


def ensure_platform(config: DemoConfig, state: DemoState, *, skip: bool) -> None:
    if skip:
        if not platform.api_ready_quiet(config):
            raise RuntimeError(f"--skip-platform given but nothing answers at {config.api_url}")
        say(f"platform already running at {config.api_url}")
        return
    platform.up(config)
    say(f"platform ready: {config.web_url} (API {config.api_url})")


def ensure_account(config: DemoConfig, state: DemoState) -> None:
    client = platform.PlatformClient(config.api_url)
    client.signin(config.admin_email, config.admin_password)
    state.user_id = client.user_id
    if not state.api_key or not client.api_key_valid(state.api_key):
        state.api_key = client.create_api_key()
        say("created a platform API key for the demo")
    _save(config, state)


def ensure_orbit(config: DemoConfig, state: DemoState) -> None:
    client = _platform_client(config, state)
    organizations = client.organizations()
    org = next((o for o in organizations if o["name"] == config.org_name), None)
    if org is None:
        org = client.create_organization(config.org_name)
        say(f"created organization {config.org_name}")
    if state.organization_id and state.organization_id != str(org["id"]):
        say("the platform database was recreated; forgetting ids from the previous environment")
        _forget_platform_state(state)
    state.organization_id = str(org["id"])
    registry_client = registry.make_client(config, DemoState(api_key=state.api_key,
                                                             organization_id=state.organization_id))
    endpoint = config.bucket_endpoint_for_docker
    secrets = registry_client.bucket_secrets.list()
    secret = next(
        (s for s in secrets if s.endpoint == endpoint and s.bucket_name == config.bucket_name), None,
    )
    if secret is None:
        secret = registry_client.bucket_secrets.create(
            endpoint=endpoint, bucket_name=config.bucket_name, region="us-east-1",
            access_key="minioadmin", secret_key="minioadmin", secure=False, cert_check=False,
        )
        say(f"created bucket secret for {endpoint}/{config.bucket_name} (reachable from Docker)")
    state.bucket_secret_id = str(secret.id)
    orbit = next((o for o in client.orbits(state.organization_id) if o["name"] == config.orbit_name), None)
    if orbit is None:
        orbit = client.create_orbit(state.organization_id, config.orbit_name, state.bucket_secret_id)
        say(f"created orbit {config.orbit_name}")
    state.orbit_id = str(orbit["id"])
    luml = registry.make_client(config, state)
    registry.ensure_collections(luml, state)
    registry.ensure_tracks(luml, state, SCENARIOS)
    _save(config, state)


def _forget_platform_state(state: DemoState) -> None:
    state.orbit_id = ""
    state.bucket_secret_id = ""
    for field in (state.collections, state.tracks, state.satellites, state.artifacts,
                  state.datasets, state.deployments, state.history):
        field.clear()


def ensure_satellites(config: DemoConfig, state: DemoState, *, rebuild_images: bool) -> None:
    satellites.ensure_images(config, force=rebuild_images)
    client = _platform_client(config, state)
    known = {str(s["id"]): s for s in client.satellites(state.organization_id, state.orbit_id)}
    for spec in config.satellites:
        record = state.satellites.get(spec.slug)
        if record is None or record["id"] not in known:
            created = client.create_satellite(state.organization_id, state.orbit_id, spec.name,
                                              spec.description)
            record = {"id": str(created["satellite"]["id"]), "token": created["api_key"],
                      "port": spec.port}
            state.satellites[spec.slug] = record
            _save(config, state)
            say(f"registered satellite {spec.name} ({record['id']})")
        satellites.write_stack(config, spec, record["token"])
        satellites.up(config, spec)
    for spec in config.satellites:
        satellites.wait_paired(client, state.organization_id, state.orbit_id,
                               state.satellites[spec.slug]["id"], spec.name)
    _save(config, state)


def _prisma_demo(config: DemoConfig, *args: str) -> None:
    executable = Path(sys.executable).parent / "prisma-demo"
    subprocess.run([str(executable), *args], check=True, env=prisma_engine.engine_environment(config))


def _registry_target(state: DemoState) -> dict[str, str]:
    return {
        "collection_id": state.collections[registry.MODELS_COLLECTION],
        "organization_id": state.organization_id,
        "orbit_id": state.orbit_id,
    }


def _repo_path(config: DemoConfig, spec: ScenarioSpec) -> Path:
    return config.repos_dir / spec.name


def _ensure_engine(config: DemoConfig, *, speed: float) -> prisma_engine.Engine:
    engine = prisma_engine.Engine(config)
    if engine.healthy() and engine.pid_file.exists():
        engine.stop()
    engine.start(speed=speed)
    return engine


def run_prisma_scenarios(config: DemoConfig, state: DemoState) -> None:
    engine = _ensure_engine(config, speed=0.0)
    client = prisma_engine.PrismaClient(config.prisma_url)
    config.repos_dir.mkdir(parents=True, exist_ok=True)
    for spec in SCENARIOS:
        scenario = load_scenario(resolve_scenario_dir(spec.name))
        _prisma_demo(config, "install-agent", spec.name)
        repo = _repo_path(config, spec)
        if not repo.exists():
            _prisma_demo(config, "init-repo", spec.name, str(repo))
        if scenario.agent_id not in client.available_agents():
            raise RuntimeError(f"agent {scenario.agent_id} is not visible to the engine")
        repository_id = client.ensure_repository(scenario.title, repo)
        state.repositories[spec.name] = repository_id
        existing = state.runs.get(spec.name)
        if existing and client.run(existing)["status"] == "succeeded":
            say(f"prisma run for {spec.name} already recorded ({existing})")
            continue
        payload = prisma_engine.run_payload(
            scenario, spec, repository_id, name=f"{spec.model_name} research — {_stamp()}",
            registry=_registry_target(state),
        )
        run = prisma_engine.run_to_completion(client, payload, timeout=PRISMA_RUN_TIMEOUT)
        state.runs[spec.name] = str(run["id"])
        _save(config, state)
    say(f"prisma runs recorded; engine log at {engine.log_file}")


def _stamp() -> str:
    return datetime.now(UTC).strftime("%b %d, %H:%M")


def publish_registry(config: DemoConfig, state: DemoState) -> None:
    engine = prisma_engine.Engine(config)
    if not engine.healthy():
        engine.start(speed=config.demo_speed)
    prisma = prisma_engine.PrismaClient(config.prisma_url)
    luml = registry.make_client(config, state)
    registry.ensure_collections(luml, state)
    registry.ensure_tracks(luml, state, SCENARIOS)
    for spec in SCENARIOS:
        if spec.name in state.artifacts:
            say(f"registry already holds the {spec.name} versions")
            continue
        run_id = state.runs.get(spec.name)
        if not run_id:
            say(f"no prisma run recorded for {spec.name}; skipping registry publish")
            continue
        artifacts = prisma_engine.collect_artifacts(prisma, run_id)
        if not artifacts:
            raise RuntimeError(f"prisma run {run_id} produced no artifacts")
        dataset_id = None
        if spec.dataset_file:
            csv_path = _repo_path(config, spec) / spec.dataset_file
            dataset_id = registry.publish_dataset(luml, state, spec, csv_path)
        uploads = registry.EngineUploads.collect(prisma, run_id)
        registry.publish_artifacts(luml, state, spec, artifacts, dataset_id, engine_uploads=uploads)
        _save(config, state)


def _deployment_name(spec: ScenarioSpec, *, candidate: bool) -> str:
    return f"{spec.model_name}-candidate" if candidate else spec.model_name


def ensure_deployments(config: DemoConfig, state: DemoState) -> None:
    client = _platform_client(config, state)
    for spec in SCENARIOS:
        winner = state.winner(spec.name)
        if winner is None:
            say(f"no winner recorded for {spec.name}; skipping deployment")
            continue
        deployments.ensure_deployment(
            client, state, name=_deployment_name(spec, candidate=False),
            artifact_id=winner["artifact_id"], satellite_slug=spec.deploy_winner_to,
            description=f"{winner['name']} — {spec.primary_metric}={winner['metric']:.4f} (Prisma winner)",
            tags=[spec.name, "production"],
        )
        runner_up = state.runner_up(spec.name)
        if spec.deploy_runner_up_to and runner_up is not None:
            deployments.ensure_deployment(
                client, state, name=_deployment_name(spec, candidate=True),
                artifact_id=runner_up["artifact_id"], satellite_slug=spec.deploy_runner_up_to,
                description=(
                    f"{runner_up['name']} — {spec.primary_metric}={runner_up['metric']:.4f} (candidate)"
                ),
                tags=[spec.name, "staging"],
            )
    _save(config, state)
    for name in list(state.deployments):
        deployments.wait_active(client, state, name)
    _save(config, state)


def _traffic_for(config: DemoConfig, state: DemoState, spec: ScenarioSpec, *, candidate: bool
                 ) -> monitoring.Traffic:
    artifact = state.runner_up(spec.name) if candidate else state.winner(spec.name)
    if artifact is None:
        raise RuntimeError(f"no artifact recorded for {spec.name}")
    scenario_dir = resolve_scenario_dir(spec.name)
    if spec.name == "churn":
        return monitoring.ChurnTraffic(scenario_dir / "repo" / "data" / "customers.csv",
                                       Path(artifact["local_path"]))
    return monitoring.AssistantTraffic(scenario_dir / "repo" / "data" / "eval.json",
                                       Path(artifact["local_path"]))


def _plan_for(spec: ScenarioSpec, *, candidate: bool, hours: int | None) -> monitoring.HistoryPlan:
    if candidate:
        plan = monitoring.CANDIDATE_PLAN
    elif spec.name == "churn":
        plan = monitoring.CHURN_PLAN
    else:
        plan = monitoring.ASSISTANT_PLAN
    if hours:
        plan = monitoring.HistoryPlan(**{**plan.__dict__, "hours": hours})
    return plan


def backfill_history(config: DemoConfig, state: DemoState, *, only: str | None = None,
                     hours: int | None = None) -> None:
    for spec in SCENARIOS:
        if only and spec.name != only:
            continue
        for candidate in (False, True):
            name = _deployment_name(spec, candidate=candidate)
            if name not in state.deployments:
                continue
            if state.history.get(name) and not only:
                say(f"history already backfilled for {name}")
                continue
            record = state.deployments[name]
            sat = config.satellite(record["satellite"])
            traffic = _traffic_for(config, state, spec, candidate=candidate)
            inference_url = deployments.inference_url(config, state, name)
            probe_inputs, _ = traffic.sample(drift=0.0, quality_issues=False)
            envelope = monitoring.probe_envelope(inference_url, state.api_key, probe_inputs)
            plan = _plan_for(spec, candidate=candidate, hours=hours or config.history_hours
                             if not candidate else hours)
            monitoring.backfill(
                deployment_id=record["id"], traffic=traffic, plan=plan, otlp_port=sat.otlp_port,
                greptime_port=sat.greptime_port, envelope=envelope,
            )
            # Enough live requests to fill the current window; sparse windows read as drift.
            counts = monitoring.send_live(inference_url, state.api_key, traffic, minutes=1.0,
                                          per_minute=150, drift=not candidate)
            say(f"live warm-up for {name}: {counts}")
            state.history[name] = datetime.now(UTC).isoformat()
            _save(config, state)


def live_traffic(config: DemoConfig, state: DemoState, *, scenario: str, minutes: float,
                 per_minute: float, drift: bool) -> None:
    spec = config.scenario(scenario)
    name = _deployment_name(spec, candidate=False)
    if name not in state.deployments:
        raise RuntimeError(f"deployment {name} is not prepared; run `luml-demo up` first")
    traffic = _traffic_for(config, state, spec, candidate=False)
    counts = monitoring.send_live(deployments.inference_url(config, state, name), state.api_key,
                                  traffic, minutes=minutes, per_minute=per_minute, drift=drift)
    say(f"traffic finished: {counts}")


def start_live_engine(config: DemoConfig, state: DemoState, *, speed: float | None = None) -> None:
    engine = prisma_engine.Engine(config)
    if engine.pid_file.exists():
        engine.stop()
    engine.start(speed=speed if speed is not None else config.demo_speed)


def stop_engine(config: DemoConfig) -> None:
    prisma_engine.Engine(config).stop()


def forget_prisma_runs(config: DemoConfig, state: DemoState) -> None:
    """Remove the demo's runs and repositories from the engine; other runs stay."""
    engine = prisma_engine.Engine(config)
    started = False
    if not engine.healthy():
        engine.start(speed=config.demo_speed)
        started = True
    client = prisma_engine.PrismaClient(config.prisma_url)
    for scenario, run_id in list(state.runs.items()):
        client.delete_run(run_id)
        say(f"deleted prisma run for {scenario} ({run_id})")
    for scenario, repository_id in list(state.repositories.items()):
        client.delete_repository(repository_id)
        say(f"deleted prisma repository for {scenario} ({repository_id})")
    state.runs.clear()
    state.repositories.clear()
    if started:
        engine.stop()


def teardown(config: DemoConfig, state: DemoState, *, volumes: bool, keep_platform: bool) -> None:
    if platform.api_ready_quiet(config) and state.api_key and state.deployments:
        deployments.undeploy_all(_platform_client(config, state), state)
        _save(config, state)
    if volumes and (state.runs or state.repositories):
        forget_prisma_runs(config, state)
        _save(config, state)
    for spec in config.satellites:
        satellites.down(config, spec, volumes=volumes)
        satellites.remove_model_containers(spec.slug)
    stop_engine(config)
    if not keep_platform:
        platform.down(config, volumes=volumes)
    if volumes:
        DemoState().save(config.state_path)
        say("state reset; the next `luml-demo up` starts from an empty platform")


def status_text(config: DemoConfig, state: DemoState) -> str:
    lines = [
        f"platform   {config.web_url}  (API {config.api_url}, "
        f"{'up' if platform.api_ready_quiet(config) else 'down'})",
        f"prisma     {config.prisma_url}  "
        f"({'up' if prisma_engine.Engine(config).healthy() else 'down'})",
        f"state      {config.state_path}",
        f"org/orbit  {state.organization_id or '-'} / {state.orbit_id or '-'} ({config.orbit_name})",
    ]
    for slug, record in state.satellites.items():
        spec = config.satellite(slug)
        lines.append(f"satellite  {spec.name:<20} http://localhost:{spec.port}  id={record['id']}")
    for name, record in state.deployments.items():
        lines.append(f"deployment {name:<28} on {record['satellite']:<8} id={record['id']}")
    for items in state.artifacts.values():
        for item in items:
            flag = " (winner)" if item.get("winner") else ""
            lines.append(
                f"artifact   {item['name']:<36} v{item.get('version')} stage={item.get('stage')}{flag}"
            )
    return "\n".join(lines)


def runbook_text(config: DemoConfig, state: DemoState) -> str:
    org, orbit = state.organization_id, state.orbit_id
    orbit_url = f"{config.web_url}/organization/{org}/orbit/{orbit}"
    deployments_lines = []
    for name, record in state.deployments.items():
        sat = config.satellite(record["satellite"])
        deployments_lines.append(
            f"     {name:<28} {orbit_url}/deployments/{record['id']}/monitoring"
            f"   (inference http://localhost:{sat.port}/deployments/{record['id']}/compute)"
        )
    return "\n".join([
        "",
        "=== LUML demo runbook ===",
        f"Login            {config.web_url}  ({config.admin_email} / {config.admin_password})",
        f"Prisma board     {config.web_url}/prisma   (engine {config.prisma_url}, state under "
        f"{config.home / 'prisma'}; restart it with `luml-demo prisma start`, not a bare luml-prisma)",
        f"Flow (local)     uvx lumlflow ui --path {config.experiments_dir} --port {config.lumlflow_port}",
        f"Registry         {orbit_url}   (collections: models, datasets; tracks: "
        f"{', '.join(state.tracks) or '-'})",
        f"Satellites       {orbit_url}/satellites",
        f"Deployments      {orbit_url}/deployments",
        *deployments_lines,
        "",
        "Live demo order",
        "  1. Prisma: open the board, show the recorded research runs (graph, terminal, metrics),",
        "     or create a new Workflow with a 'Demo Agent — …' agent on the same repo and run it live:",
        f"     repos: {', '.join(str(_repo_path(config, s)) for s in SCENARIOS)}",
        "     settings: run command `uv run main.py`, max depth 2, max fork children 3, auto mode on,",
        "     upload to collection `models`.",
        "  2. Flow: experiments, metric curves, traces, evals with annotations, attachments, models.",
        "  3. Registry: artifact versions on the tracks, experiment snapshot / card / attachments /",
        "     lineage tabs, compare two versions.",
        "  4. Deployments: the production and candidate deployments, inference schema, then the",
        "     monitoring dashboard (24h history with a drift onset, data-quality issues, an incident).",
        "  5. Keep traffic flowing while talking: luml-demo traffic --scenario churn --minutes 15",
        "",
        "Keep Prisma run pages closed while `luml-demo up` runs: an open page claims the engine's",
        "uploads itself and registers plain `agent-model-<node>` artifacts instead of the curated ones.",
        "",
        "Teardown: luml-demo down  (add --volumes for a clean slate)",
        "",
    ])
