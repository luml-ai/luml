import json
from typing import get_args

import pytest
from lumlflow.flow.store import models
from lumlflow.flow.store.models import (
    JOURNAL_SCHEMA_VERSION,
    CellManifest,
    CellNoted,
    FlowInit,
    Op,
    OutputSpec,
    Transaction,
)
from pydantic import BaseModel, ValidationError

from tests.flow.helpers import cell_accepted, transaction

SPEC_OP_VOCABULARY = {
    "flow_init",
    "cell_accepted",
    "cell_removed",
    "cell_noted",
    "selection_set",
    "branch_created",
    "branch_archived",
    "worktree_bound",
    "rewound",
    "adopted",
    "renamed",
    "run_recorded",
    "memo_hit",
    "workspace_code_changed",
    "env_changed",
    "flag_set",
    "agent_begin",
    "agent_end",
    "checkpointed",
}


def _op_models() -> set[type[BaseModel]]:
    return {
        member
        for member in vars(models).values()
        if isinstance(member, type)
        and issubclass(member, BaseModel)
        and "op" in member.model_fields
    }


class TestOpVocabulary:
    def test_the_wire_names_are_exactly_the_documented_vocabulary(self) -> None:
        assert {
            model.model_fields["op"].default for model in _op_models()
        } == SPEC_OP_VOCABULARY

    def test_every_op_model_is_reachable_from_the_union(self) -> None:
        assert _op_models() == set(get_args(get_args(Op)[0]))

    def test_an_unknown_op_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            Transaction.model_validate(
                {
                    "step": 1,
                    "ts": "2026-08-12T09:00:00+00:00",
                    "actor": "user",
                    "intent": "edit",
                    "ops": [{"op": "teleport", "uid": "U"}],
                }
            )

    def test_unknown_transaction_and_op_fields_are_ignored_on_read(self) -> None:
        original = transaction(1, [cell_accepted()])
        payload = json.loads(original.to_line())
        payload["mood"] = "hopeful"
        payload["ops"][0]["future_field"] = {"kept_by": "a future release"}

        assert Transaction.from_line(json.dumps(payload).encode()) == original

    def test_intent_is_mandatory(self) -> None:
        with pytest.raises(ValidationError):
            Transaction.model_validate(
                {
                    "step": 1,
                    "ts": "2026-08-12T09:00:00+00:00",
                    "actor": "user",
                    "ops": [],
                }
            )


class TestManifest:
    def test_produces_takes_only_the_four_words(self) -> None:
        assert OutputSpec(type="model").persist is True
        with pytest.raises(ValidationError):
            CellManifest(produces={"data": OutputSpec(type="frame")})  # type: ignore[arg-type]

    def test_an_output_can_opt_out_of_the_values_store(self) -> None:
        spec = OutputSpec(type="asset", kind="frame", persist=False)
        assert (spec.kind, spec.persist) == ("frame", False)


class TestWireFormat:
    def test_flow_init_stamps_journal_schema_version_two(self) -> None:
        assert JOURNAL_SCHEMA_VERSION == 2
        assert FlowInit(flow_id="F", name="churn").schema_version == 2

    def test_a_cell_note_requires_a_lane_scoped_transaction(self) -> None:
        with pytest.raises(ValidationError, match="lane-scoped"):
            transaction(
                1,
                [
                    CellNoted(
                        uid="cell-score",
                        kind="refresh_failed",
                        sentence="could not refresh score",
                    )
                ],
            )

    def test_a_cell_note_requires_the_system_actor(self) -> None:
        with pytest.raises(ValidationError, match="system actor"):
            transaction(
                1,
                [
                    CellNoted(
                        uid="cell-score",
                        kind="refresh_failed",
                        sentence="could not refresh score",
                    )
                ],
                branch="lane-main",
            )

    def test_a_line_round_trips_through_canonical_json(self) -> None:
        original = transaction(9, [cell_accepted(slug="train_model")], branch="b1")
        line = original.to_line()

        assert line.endswith(b"\n")
        assert line.count(b"\n") == 1
        assert Transaction.from_line(line) == original

    def test_the_same_transaction_always_serializes_identically(self) -> None:
        entry = transaction(1, [cell_accepted()])
        assert entry.to_line() == entry.to_line()
