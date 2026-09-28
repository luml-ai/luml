"""Memo keys — what makes two runs the same run — and the hits they find.

A key is the behavior hash (the cell's own identity plus the shared code it can
import) over a **named** map of input content hashes. Named, never a bag: two
outputs of the same schema swapped between two inputs are a different
computation, and a key hashing a multiset would happily serve one branch's
answer for the other's question.

Hits are cross-branch by construction — the same lookup, not a special case.
Two recorded facts block one. A run that read its own branch identity may not
be reused under another name, or that branch would be served content computed
elsewhere and its side effect would silently never fire. A run that touched
something outside the flow is never reusable at all, because nothing here knows
what it read.
"""

from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING

from lumlflow.flow.hashing import hash_json
from lumlflow.flow.store.index import Index, MaterializationRow, VersionRow

if TYPE_CHECKING:
    from lumlflow.flow.store.flowstore import FlowStore


def behavior_hash(definition_hash: str, workspace_tree_hash: str | None) -> str:
    """Does it need to rerun: the cell's identity plus the shared code around it."""
    return hash_json({"definition": definition_hash, "workspace": workspace_tree_hash})


def memo_key(
    behavior: str,
    inputs: Mapping[str, str],
    *,
    env_lock_hash: str | None = None,
) -> str:
    """No seed component: a seed is a param, and params ride `definition_hash`."""
    body: dict[str, object] = {"behavior": behavior, "inputs": dict(inputs)}
    if env_lock_hash is not None:
        body["env"] = env_lock_hash
    return hash_json(body)


def key_for(index: Index, version: VersionRow, inputs: Mapping[str, str]) -> str:
    """The key as this store would compute it now — env only where declared.

    The env is recorded provenance, not an ingredient: a mid-run install must
    not invalidate what already ran. `env_sensitive` is the opt-in for cells
    that genuinely compute something different under a different lockfile.
    """
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
    """Would serving this materialization here be the truth?

    `require_values` names outputs a caller needs the bytes of. A declared
    unpersisted output has none, ever, so a hit never satisfies a request that
    needs them — the producer re-executes instead.
    """
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
