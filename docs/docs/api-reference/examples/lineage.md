---
title: lineage.py
sidebar_position: 7
description: "Recording what an artifact was produced from and reading the graph back: a training pipeline, impact analysis from a dataset, provenance of the model in production, fixing wrong links"
---

Lineage: recording what an artifact was produced from and reading it back.

Lineage is a graph per orbit. Every artifact that takes part in it is a node,
and an edge points from an input to what was produced from it:
`dataset -> experiment`, `experiment -> model`, `dataset -> model`.
A node outlives its artifact: when an artifact is deleted its node stays in
the graph with `is_deleted=True` and a copy of its name, so the history of
the artifacts around it keeps making sense.

The basic calls come first. The scenarios after them show how the pieces fit
together: a training pipeline that records lineage as it uploads, an impact
analysis that starts from a dataset, a provenance check that starts from the
model in production, and a clean-up of a wrong link. The graph helpers at the
end only work on responses, so they serve the async client unchanged;
`async_demo.py` shows the calls on that client.

```python
from collections import deque

from luml_api import ConflictError, LumlClient
from luml_api._types import LineageEdge, LineageGraph, LineageNode

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
DATASET_COLLECTION_ID = "0199c455-21ee-74c6-b747-19a82f1a1e70"
EXPERIMENT_COLLECTION_ID = "0199c455-21ee-74c6-b747-19a82f1a1e71"
MODEL_COLLECTION_ID = "0199c455-21ee-74c6-b747-19a82f1a1e75"
TRACK_ID = "0199c455-21ee-74c6-b747-19a82f1a1e67"

DATASET_ID = "0199c455-21ee-74c6-b747-19a82f1a1e80"
EXPERIMENT_ID = "0199c455-21ee-74c6-b747-19a82f1a1e81"
MODEL_ID = "0199c455-21ee-74c6-b747-19a82f1a1e82"
LAST_MONTH_DATASET_ID = "0199c455-21ee-74c6-b747-19a82f1a1e83"

# Artifacts uploaded before lineage was recorded, and what they were made from
BACKFILL = {
    "0199c455-21ee-74c6-b747-19a82f1a1e90": [DATASET_ID],
    "0199c455-21ee-74c6-b747-19a82f1a1e91": [DATASET_ID, EXPERIMENT_ID],
    "0199c455-21ee-74c6-b747-19a82f1a1e92": [LAST_MONTH_DATASET_ID],
}

# Lineage is scoped to the orbit; the collection only matters for uploads
luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization=ORGANIZATION_ID,
    orbit=ORBIT_ID,
    collection=MODEL_COLLECTION_ID,
)


# --- Basics --------------------------------------------------------------------


def demo_lineage_basics() -> None:
    # The whole connected graph around an artifact. The platform stops at 200
    # artifacts and sets ``truncated`` when it had to
    graph = luml.artifacts.get_lineage(MODEL_ID)
    print(
        f"{len(graph.nodes)} nodes, {len(graph.edges)} edges, "
        f"truncated={graph.truncated}"
    )

    # Only the direct inputs and outputs
    neighbours = luml.artifacts.get_lineage(MODEL_ID, depth=1)

    # Edges reference nodes, not artifacts: map node ids back to the artifacts
    nodes_by_id = {node.id: node for node in neighbours.nodes}
    for edge in neighbours.edges:
        source, target = nodes_by_id[edge.source], nodes_by_id[edge.target]
        print(
            f"{source.name} -> {target.name} "
            f"(linked via {edge.created_via} by {edge.created_by_user})"
        )

    # A deleted artifact keeps its node, so what was made from it stays explained
    for node in graph.nodes:
        if node.is_deleted:
            print(f"{node.name} was deleted; its node is kept for the graph")

    # Record that a dataset was used for an experiment and for a model
    edges = luml.artifacts.log_lineage(DATASET_ID, [EXPERIMENT_ID, MODEL_ID])
    print(f"Created: {edges}")

    # The same from the other side: the model came out of the experiment.
    # Every input is linked in one transaction, or none of them is
    luml.artifacts.log_lineage_inputs(MODEL_ID, [EXPERIMENT_ID])

    # What the platform refuses: a link that already exists or runs the other
    # way round (409), an artifact linked to itself (400), an artifact of
    # another orbit (404)
    try:
        luml.artifacts.log_lineage(MODEL_ID, [DATASET_ID])
    except ConflictError as error:
        print(f"Refused, dataset -> model already exists: {error}")

    # Remove one connection; either artifact of the connection can be named
    removed = luml.artifacts.remove_lineage(MODEL_ID, edges[1].id)
    print(f"Removed: {removed}")


# --- Scenario: a training pipeline that records lineage as it goes ------------


def demo_training_pipeline() -> None:
    """Upload a dataset, an experiment and a model, linked as they are created."""
    # Each upload names the artifacts it was produced from. The platform
    # creates the artifact and its lineage in one step, so a model never
    # shows up without its inputs, and a failed upload leaves no half-linked
    # artifact behind
    dataset = luml.artifacts.upload(
        "/path/to/customers_2026_09.dfs",
        name="customers-2026-09",
        tags=["churn", "training-data"],
        collection_id=DATASET_COLLECTION_ID,
    )
    experiment = luml.artifacts.upload(
        "/path/to/churn_tuning.dfs",
        name="churn-tuning-run-42",
        lineage_inputs=[dataset.id],
        collection_id=EXPERIMENT_COLLECTION_ID,
    )
    model = luml.artifacts.upload(
        "/path/to/churn_model.fnnx",
        name="churn-predictor",
        description="XGBoost, tuned in run 42",
        lineage_inputs=[dataset.id, experiment.id],
        collection_id=MODEL_COLLECTION_ID,
    )

    # The model joins its track as the next version, straight into staging
    entry = luml.tracks.add_artifact(TRACK_ID, model.id, stage="staging")
    print(f"{model.name} is v{entry.version} of the track, in {entry.stage_name}")

    # Artifacts uploaded before lineage existed are backfilled afterwards. This
    # is safe to run again: only the missing links are written
    for artifact_id, input_ids in BACKFILL.items():
        ensure_inputs(artifact_id, input_ids)


def ensure_inputs(artifact_id: str, input_artifact_ids: list[str]) -> None:
    """Link the inputs that are not linked yet; safe to run again and again.

    ``log_lineage_inputs`` refuses the whole batch when any of the links
    already exists, so a pipeline that is re-run would fail on its second step.
    Reading the direct neighbours first and linking only what is missing keeps
    the call idempotent, and the remaining batch still lands in one transaction.
    """
    neighbours = luml.artifacts.get_lineage(artifact_id, depth=1)
    linked = existing_inputs(neighbours, artifact_id)
    missing = [input_id for input_id in input_artifact_ids if input_id not in linked]
    if not missing:
        print(f"{artifact_id}: every input is already linked")
        return
    try:
        created = luml.artifacts.log_lineage_inputs(artifact_id, missing)
    except ConflictError:
        # Someone linked one of them between the read and the write; the next
        # run sees it and links the rest
        print(f"{artifact_id}: a link appeared meanwhile, run again")
        return
    print(f"{artifact_id}: linked {len(created)} inputs")


# --- Scenario: what depends on a dataset ---------------------------------------


def demo_dataset_impact() -> None:
    """Everything made from a dataset, and which of it is serving in production."""
    graph = luml.artifacts.get_lineage(DATASET_ID)

    for node in reachable(graph, DATASET_ID, downstream=True):
        if node.type != "model" or node.data is None:
            # Experiments, and models that were deleted (``data`` is None)
            continue
        # ``data`` is the live artifact, its deployments included
        active = [d.name for d in node.data.deployments if d.status == "active"]
        where = ", ".join(active) if active else "not deployed"
        print(f"{node.name} ({node.collection_name}): {where}")

    if graph.truncated:
        # More than 200 artifacts hang off this dataset and the response holds
        # the closest ones. Start again from an artifact further down, or walk
        # level by level as ``ancestors`` does below
        print("The graph was cut at 200 artifacts")


# --- Scenario: where the model in production came from -------------------------


def demo_production_provenance() -> None:
    """From the version serving in production back to the data it was trained on."""
    entry = luml.tracks.get_artifact_by_stage(TRACK_ID, "production")
    lineage = ancestors(str(entry.artifact_id))

    datasets = [node.name for node in lineage if node.type == "dataset"]
    print(f"v{entry.version} of the track was trained on: {datasets}")

    deleted = [node.name for node in lineage if node.is_deleted]
    if deleted:
        print(f"Part of its history was deleted: {deleted}")


def ancestors(artifact_id: str) -> list[LineageNode]:
    """Every artifact ``artifact_id`` descends from, however big the graph is.

    One response holds at most 200 artifacts. When that is not enough, the
    graph is walked one level at a time, re-focusing on every live ancestor.
    A deleted ancestor is reported but not walked through: there is no artifact
    left to focus on.
    """
    graph = luml.artifacts.get_lineage(artifact_id)
    if not graph.truncated:
        return reachable(graph, artifact_id, downstream=False)

    found: dict[str, LineageNode] = {}
    frontier = [artifact_id]
    while frontier:
        next_frontier: list[str] = []
        for current_id in frontier:
            level = luml.artifacts.get_lineage(current_id, depth=1)
            for node in reachable(level, current_id, downstream=False):
                if node.id in found:
                    continue
                found[node.id] = node
                if node.artifact_id is not None:
                    next_frontier.append(node.artifact_id)
        frontier = next_frontier
    return list(found.values())


# --- Scenario: fixing a wrong link ---------------------------------------------


def demo_fix_wrong_link() -> None:
    """The model was linked to last month's dataset; point it at the right one."""
    neighbours = luml.artifacts.get_lineage(MODEL_ID, depth=1)
    wrong_edge = edge_between(neighbours, LAST_MONTH_DATASET_ID, MODEL_ID)
    if wrong_edge is not None:
        luml.artifacts.remove_lineage(MODEL_ID, wrong_edge.id)
        print(f"Removed the link from {LAST_MONTH_DATASET_ID}")

    # Link the right dataset; nothing happens if it is already linked
    ensure_inputs(MODEL_ID, [DATASET_ID])

    # Removing the last connection of an artifact also drops its node, so the
    # graph never keeps lone dots around


# --- Graph helpers: pure functions over a response -----------------------------


def existing_inputs(graph: LineageGraph, artifact_id: str) -> set[str]:
    """Ids of the artifacts that are direct inputs of ``artifact_id``."""
    focal = focal_node(graph, artifact_id)
    if focal is None:
        return set()
    nodes_by_id = {node.id: node for node in graph.nodes}
    inputs: set[str] = set()
    for edge in graph.edges:
        source = nodes_by_id[edge.source]
        if edge.target == focal.id and source.artifact_id is not None:
            inputs.add(source.artifact_id)
    return inputs


def edge_between(
    graph: LineageGraph, source_artifact_id: str, target_artifact_id: str
) -> LineageEdge | None:
    """The edge from one artifact to another, if the graph holds it."""
    source = focal_node(graph, source_artifact_id)
    target = focal_node(graph, target_artifact_id)
    if source is None or target is None:
        return None
    return next(
        (e for e in graph.edges if e.source == source.id and e.target == target.id),
        None,
    )


def reachable(
    graph: LineageGraph, artifact_id: str, *, downstream: bool
) -> list[LineageNode]:
    """Nodes reachable from ``artifact_id`` following the edges one way.

    ``downstream=True`` follows input -> output (what was made from it),
    ``downstream=False`` follows output -> input (what it was made from).
    """
    focal = focal_node(graph, artifact_id)
    if focal is None:
        return []
    nodes_by_id = {node.id: node for node in graph.nodes}
    next_ids: dict[str, list[str]] = {}
    for edge in graph.edges:
        if downstream:
            next_ids.setdefault(edge.source, []).append(edge.target)
        else:
            next_ids.setdefault(edge.target, []).append(edge.source)

    seen = {focal.id}
    queue = deque([focal.id])
    found: list[LineageNode] = []
    while queue:
        for node_id in next_ids.get(queue.popleft(), []):
            if node_id in seen:
                continue
            seen.add(node_id)
            found.append(nodes_by_id[node_id])
            queue.append(node_id)
    return found


def focal_node(graph: LineageGraph, artifact_id: str) -> LineageNode | None:
    """The node of a live artifact, or None when the artifact has no lineage."""
    return next((n for n in graph.nodes if n.artifact_id == artifact_id), None)


if __name__ == "__main__":
    demo_lineage_basics()
    demo_training_pipeline()
    demo_dataset_impact()
    demo_production_provenance()
    demo_fix_wrong_link()
```
