from pathlib import Path

import pytest
from lumlflow.flow.hashing import hash_bytes
from lumlflow.flow.scheduler import memo
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.index import VersionRow
from lumlflow.flow.store.models import EnvChanged, OutputRecord

from tests.flow.helpers import accept, cell_accepted, output_record, run_recorded

TRAIN = hash_bytes(b"train rows")
TEST = hash_bytes(b"test rows")


@pytest.fixture
def store(tmp_path: Path) -> FlowStore:
    return FlowStore.init(tmp_path / "churn.flow")


def branch_id(store: FlowStore, name: str = MAIN_BRANCH) -> str:
    return store.branches.get(name).branch_id


def _version(store: FlowStore, version_id: str) -> VersionRow:
    row = store.index.version(version_id)
    assert row is not None
    return row


def record(
    store: FlowStore,
    *,
    memo_key: str,
    branch: str = MAIN_BRANCH,
    identity_dependent: bool = False,
    external: bool = False,
    outputs: dict[str, OutputRecord] | None = None,
) -> str:
    accepted = cell_accepted(slug="train")
    here = branch_id(store, branch)
    run = run_recorded(
        uid=accepted.uid,
        version_id=accepted.version_id,
        branch_id=here,
        memo_key=memo_key,
        outputs=outputs,
        identity_dependent=identity_dependent,
        external=external,
    )
    store.commit([accepted, run], intent="ran train", actor="user", branch=here)
    return run.mat_id


class TestKeys:
    def test_a_swap_of_two_same_shaped_inputs_changes_the_key(self) -> None:
        """Named map, never a bag: `{train: a, test: b}` is not `{train: b, ...}`."""
        behavior = hash_bytes(b"behavior")

        assert memo.memo_key(behavior, {"train": TRAIN, "test": TEST}) != memo.memo_key(
            behavior, {"train": TEST, "test": TRAIN}
        )

    def test_the_order_inputs_are_written_in_does_not_matter(self) -> None:
        behavior = hash_bytes(b"behavior")

        assert memo.memo_key(behavior, {"train": TRAIN, "test": TEST}) == memo.memo_key(
            behavior, {"test": TEST, "train": TRAIN}
        )

    def test_shared_code_rides_the_behavior_hash(self) -> None:
        assert memo.behavior_hash("d", "tree-a") != memo.behavior_hash("d", "tree-b")

    def test_only_an_env_sensitive_cell_keys_on_the_lockfile(
        self, store: FlowStore
    ) -> None:
        versions = {
            "ordinary": accept(store, "features").version_id,
            "sensitive": accept(store, "sensitive", env_sensitive=True).version_id,
        }

        def keys() -> dict[str, str]:
            return {
                name: memo.key_for(store.index, _version(store, version_id), {})
                for name, version_id in versions.items()
            }

        before = keys()
        store.commit(
            [EnvChanged(lock_hash="lock-2")], intent="added lightgbm", actor="user"
        )

        after = keys()
        assert after["ordinary"] == before["ordinary"]
        assert after["sensitive"] != before["sensitive"]


class TestLookup:
    def test_a_matching_key_is_a_hit_whichever_branch_ran_it(
        self, store: FlowStore
    ) -> None:
        mat_id = record(store, memo_key="k")
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        hit = memo.lookup(store, "k", branch_id=branch_id(store, "sweep"))
        assert hit is not None and hit.mat_id == mat_id

    def test_an_identity_dependent_run_never_matches_another_branch(
        self, store: FlowStore
    ) -> None:
        record(store, memo_key="k", identity_dependent=True)
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)

        assert memo.lookup(store, "k", branch_id=branch_id(store, "sweep")) is None
        assert memo.lookup(store, "k", branch_id=branch_id(store)) is not None

    def test_an_external_run_never_matches_at_all(self, store: FlowStore) -> None:
        record(store, memo_key="k", external=True)

        assert memo.lookup(store, "k", branch_id=branch_id(store)) is None

    def test_a_hit_never_serves_bytes_that_were_never_persisted(
        self, store: FlowStore
    ) -> None:
        unpersisted = OutputRecord(
            content_hash=hash_bytes(b"token"),
            kind="frame",
            kind_source="matcher",
            size=0,
            value_ref=None,
            persisted=False,
        )
        record(store, memo_key="k", outputs={"data": unpersisted})

        here = branch_id(store)
        assert memo.lookup(store, "k", branch_id=here) is not None
        assert memo.lookup(store, "k", branch_id=here, require_values=["data"]) is None

    def test_a_required_output_whose_blob_is_gone_is_not_a_hit(
        self, store: FlowStore
    ) -> None:
        record(store, memo_key="k", outputs={"data": output_record(b"rows")})

        here = branch_id(store)
        assert memo.lookup(store, "k", branch_id=here, require_values=["data"]) is None
