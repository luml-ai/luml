"""Op builders for store tests — real ULIDs, real content hashes."""

from collections.abc import Sequence
from typing import Protocol

from lumlflow.flow.hashing import hash_bytes
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.index import Index
from lumlflow.flow.store.models import (
    CellAccepted,
    CellManifest,
    ConsumedRef,
    InputRef,
    MaterializationState,
    Op,
    OutputRecord,
    OutputSpec,
    RunRecorded,
    SelectionSet,
    Transaction,
    VersionFlag,
)

TABLES = (
    "meta",
    "cells",
    "asset_versions",
    "branches",
    "selections",
    "baselines",
    "materializations",
    "transactions",
    "worktrees",
    "upload_queue",
    "workspace_tree",
    "value_pins",
)


def cell_accepted(
    *,
    uid: str | None = None,
    slug: str = "features",
    source: str = "class Features: pass",
    consumes: dict[str, str] | None = None,
    bound_to: dict[str, str | None] | None = None,
    produces: dict[str, OutputSpec] | None = None,
    env_sensitive: bool = False,
    flags: list[VersionFlag] | None = None,
    parent_version_id: str | None = None,
    copied_from: str | None = None,
    author: str = "user",
) -> CellAccepted:
    """`consumes` maps an input name to its reference, `bound_to` to its uid."""
    body = source.encode()
    return CellAccepted(
        uid=uid or new_ulid(),
        version_id=new_ulid(),
        slug=slug,
        definition_hash=hash_bytes(body),
        raw_source_ref=hash_bytes(body),
        bound_source_ref=hash_bytes(b"bound " + body),
        manifest=CellManifest(
            consumes={
                name: ConsumedRef(
                    ref=ref,
                    uid=(bound_to or {}).get(name, new_ulid()),
                    output=ref.split(".", 1)[1] if "." in ref else None,
                )
                for name, ref in (consumes or {}).items()
            },
            produces=produces or {"data": OutputSpec(type="asset")},
            params={"seed": 1337},
            env_sensitive=env_sensitive,
        ),
        parent_version_id=parent_version_id,
        copied_from=copied_from,
        author=author,
        flags=flags or [],
    )


def accept(
    store: FlowStore,
    slug: str,
    *,
    branch: str = MAIN_BRANCH,
    uid: str | None = None,
    source: str | None = None,
    consumes: dict[str, str] | None = None,
    bound_to: dict[str, str | None] | None = None,
    produces: dict[str, OutputSpec] | None = None,
    env_sensitive: bool = False,
) -> CellAccepted:
    """Accept a version and select it on the branch, as acceptance would."""
    branch_id = store.branches.get(branch).branch_id
    op = cell_accepted(
        uid=uid,
        slug=slug,
        source=source if source is not None else f"class {slug.title()}: pass",
        consumes=consumes,
        bound_to=bound_to,
        produces=produces,
        env_sensitive=env_sensitive,
    )
    store.commit(
        [op, SelectionSet(branch_id=branch_id, uid=op.uid, version_id=op.version_id)],
        intent=f"accept {slug}",
        actor="user",
        branch=branch_id,
    )
    return op


class Accepted(Protocol):
    """What `record_run` needs of a version, whether the op or the pipeline
    result named it — both address the same row, and both are frozen."""

    @property
    def uid(self) -> str: ...
    @property
    def version_id(self) -> str: ...
    @property
    def slug(self) -> str: ...


def record_run(
    store: FlowStore,
    accepted: Accepted,
    *,
    branch: str = MAIN_BRANCH,
    content: bytes = b"rows",
    inputs: dict[str, InputRef] | None = None,
    state: MaterializationState = "succeeded",
) -> RunRecorded:
    """Stage the value in the CAS, then journal the run — the store's ordering."""
    store.values.put(content)
    branch_id = store.branches.get(branch).branch_id
    run = run_recorded(
        uid=accepted.uid,
        version_id=accepted.version_id,
        branch_id=branch_id,
        state=state,
        inputs=inputs,
        outputs={"data": output_record(content)},
    )
    store.commit([run], intent=f"ran {accepted.slug}", actor="user", branch=branch_id)
    return run


def input_ref(run: RunRecorded, output: str = "data") -> InputRef:
    return InputRef(
        uid=run.uid,
        output=output,
        content_hash=run.outputs[output].content_hash,
        mat_id=run.mat_id,
    )


def run_recorded(
    *,
    uid: str,
    version_id: str,
    branch_id: str,
    state: MaterializationState = "succeeded",
    mat_id: str | None = None,
    memo_key: str | None = None,
    outputs: dict[str, OutputRecord] | None = None,
    inputs: dict[str, InputRef] | None = None,
    identity_dependent: bool = False,
    external: bool = False,
) -> RunRecorded:
    return RunRecorded(
        mat_id=mat_id or new_ulid(),
        uid=uid,
        version_id=version_id,
        branch_id=branch_id,
        memo_key=memo_key or hash_bytes(version_id.encode()),
        state=state,
        inputs=inputs or {},
        outputs=outputs or {"data": output_record()},
        identity_dependent=identity_dependent,
        external=external,
        cost_seconds=1.5,
        started_step=1,
        finished_step=2,
    )


def transaction(
    step: int,
    ops: Sequence[Op] | None = None,
    *,
    actor: str = "user",
    intent: str = "edit the cell",
    branch: str | None = None,
    offline: bool = False,
    settled: bool = False,
) -> Transaction:
    return Transaction(
        step=step,
        ts=f"2026-08-12T09:00:{step % 60:02d}+00:00",
        actor=actor,
        intent=intent,
        branch=branch,
        offline=offline,
        settled=settled,
        ops=list(ops) if ops is not None else [cell_accepted()],
    )


def output_record(content: bytes = b"rows") -> OutputRecord:
    return OutputRecord(
        content_hash=hash_bytes(content),
        kind="frame",
        kind_source="matcher",
        size=len(content),
        value_ref=hash_bytes(content),
    )


def snapshot(index: Index) -> dict[str, list[tuple[object, ...]]]:
    """Every indexed row, order-normalized — the shape a rebuild must reproduce."""
    return {
        table: [
            tuple(row)
            for row in index.conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2")
        ]
        for table in TABLES
    }
