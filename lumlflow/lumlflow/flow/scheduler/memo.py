from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING

from lumlflow.flow.hashing import hash_json
from lumlflow.flow.store.index import Index, MaterializationRow, VersionRow

if TYPE_CHECKING:
    from lumlflow.flow.store.flowstore import FlowStore


def behavior_hash(definition_hash: str, workspace_tree_hash: str | None) -> str:
    return hash_json({"definition": definition_hash, "workspace": workspace_tree_hash})


def memo_key(
    behavior: str,
    inputs: Mapping[str, str],
    *,
    env_lock_hash: str | None = None,
) -> str:
    body: dict[str, object] = {"behavior": behavior, "inputs": dict(inputs)}
    if env_lock_hash is not None:
        body["env"] = env_lock_hash
    return hash_json(body)


def key_for(index: Index, version: VersionRow, inputs: Mapping[str, str]) -> str:
    tree = index.workspace_tree()
    behavior = behavior_hash(
        version.definition_hash, tree.tree_hash if tree is not None else None
    )
    env = index.env_lock_hash() if version.manifest.env_sensitive else None
    return memo_key(behavior, inputs, env_lock_hash=env)


def lookup(
    store: "FlowStore",
    key: str,
    *,
    branch_id: str,
    require_values: Collection[str] = (),
) -> MaterializationRow | None:
    for mat in store.index.memo_candidates(key):
        if reusable(store, mat, branch_id=branch_id, require_values=require_values):
            return mat
    return None


def reusable(
    store: "FlowStore",
    mat: MaterializationRow,
    *,
    branch_id: str,
    require_values: Collection[str] = (),
) -> bool:
    if mat.external:
        return False
    if mat.identity_dependent and mat.branch_id != branch_id:
        return False
    return all(_has_bytes(store, mat, name) for name in require_values)


def _has_bytes(store: "FlowStore", mat: MaterializationRow, output: str) -> bool:
    record = mat.outputs.get(output)
    return (
        record is not None
        and record.value_ref is not None
        and store.values.exists(record.value_ref)
    )
