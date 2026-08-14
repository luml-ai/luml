import ast
from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from lumlflow.flow.dsl.accept import Acceptance, AcceptedCell
from lumlflow.flow.ids import is_ulid
from lumlflow.flow.scheduler import staleness
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.index import VersionRow
from lumlflow.flow.store.models import Renamed, Transaction

from tests.flow.helpers import record_run

FEATURES = """
class Features:
    '''Engineer the model features.'''

    produces = {"train_split": "dataset", "test_split": "dataset"}

    def materialize(self, ctx):
        return {"train_split": [], "test_split": []}
"""

TRAIN_MODEL = """
raise RuntimeError("a cell file is read, never imported")


class TrainXGB:
    '''Train the churn model on engineered features.'''

    consumes = {"train": "features.train_split"}
    produces = {"model": "model", "run": "experiment"}
    params = {"lr": 0.0003, "epochs": 10, "seed": 1337}

    def materialize(self, ctx, train):
        return {"model": train, "run": {}}
"""

REPORT = """
class Report:
    '''Report on the trained model.'''

    consumes = {"model": "train_model.model"}
    produces = {"page": "asset"}

    def materialize(self, ctx, model):
        return {"page": model}
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def flow_dir(workspace: Path) -> Path:
    return workspace / "churn.flow"


@pytest.fixture
def store(flow_dir: Path) -> FlowStore:
    return FlowStore.init(flow_dir)


@pytest.fixture
def acceptance(store: FlowStore) -> Acceptance:
    return Acceptance(store)


def write(acceptance: Acceptance, slug: str, source: str) -> Path:
    path = acceptance.cell_path(slug)
    path.write_text(dedent(source), encoding="utf-8")
    return path


def accept(
    acceptance: Acceptance,
    slug: str,
    source: str,
    *,
    base_version_id: str | None = None,
) -> AcceptedCell:
    return acceptance.accept_path(
        write(acceptance, slug, source), base_version_id=base_version_id
    )


def version(store: FlowStore, accepted: AcceptedCell) -> VersionRow:
    found = store.index.version(accepted.version_id)
    assert found is not None
    return found


def codes(accepted: AcceptedCell) -> list[str]:
    return [flag.code for flag in accepted.flags]


def detail(accepted: AcceptedCell, code: str) -> str:
    return next(flag.detail or "" for flag in accepted.flags if flag.code == code)


def class_body(path: Path) -> list[ast.stmt]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    return next(node for node in module.body if isinstance(node, ast.ClassDef)).body


def transactions(store: FlowStore) -> list[Transaction]:
    return list(store.journal.replay())


class TestMinting:
    def test_a_new_cell_is_minted_and_versioned_without_being_imported(
        self, store: FlowStore, acceptance: Acceptance, flow_dir: Path
    ) -> None:
        accept(acceptance, "features", FEATURES)
        accepted = accept(acceptance, "train_model", TRAIN_MODEL)

        path = acceptance.cell_path("train_model")
        body = class_body(path)
        assert is_ulid(accepted.uid)
        assert isinstance(body[0], ast.Expr)  # the docstring stays first
        assert ast.unparse(body[1]) == f"uid = {accepted.uid!r}"
        assert f'    uid = "{accepted.uid}"' in path.read_text(encoding="utf-8")

        manifest = version(store, accepted).manifest
        assert set(manifest.produces) == {"model", "run"}
        assert manifest.params == {"lr": 0.0003, "epochs": 10, "seed": 1337}
        assert manifest.consumes["train"].output == "train_split"
        assert accepted.flags == []

        index = yaml.safe_load((flow_dir / "flow.yaml").read_text())["cells"]
        assert index["train_model"] == accepted.uid

    def test_the_uid_line_is_written_once_and_acceptance_settles(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        path = write(acceptance, "features", FEATURES)
        first = acceptance.accept_path(path)
        after_mint = path.read_bytes()
        steps = store.next_step

        again = acceptance.accept_path(path)

        assert path.read_bytes() == after_mint
        assert (again.uid, again.version_id) == (first.uid, first.version_id)
        assert again.unchanged and store.next_step == steps

    def test_the_write_back_touches_nothing_but_its_own_line(
        self, acceptance: Acceptance
    ) -> None:
        path = write(acceptance, "features", FEATURES)
        before = path.read_text(encoding="utf-8").splitlines(keepends=True)

        accepted = acceptance.accept_path(path)

        after = path.read_text(encoding="utf-8").splitlines(keepends=True)
        minted = f'    uid = "{accepted.uid}"\n'
        assert [line for line in after if line != minted] == before
        assert len(after) == len(before) + 1

    def test_a_version_records_the_one_it_grew_from(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        first = accept(acceptance, "features", FEATURES)
        second = accept(acceptance, "features", FEATURES.replace("Engineer", "Build"))

        assert version(store, first).parent_version_id is None
        assert version(store, second).parent_version_id == first.version_id

    def test_an_annotated_uid_is_rewritten_in_place_not_duplicated(
        self, acceptance: Acceptance
    ) -> None:
        accept(acceptance, "eval", FEATURES)
        source = acceptance.cell_path("eval").read_text(encoding="utf-8")

        copy = accept(acceptance, "eval_v2", source.replace("uid =", "uid: str ="))

        body = class_body(acceptance.cell_path("eval_v2"))
        assert [ast.unparse(node) for node in body if "uid" in ast.unparse(node)] == [
            f"uid: str = {copy.uid!r}"
        ]

    def test_a_cell_declared_without_a_docstring_still_takes_a_uid(
        self, acceptance: Acceptance
    ) -> None:
        accepted = accept(
            acceptance,
            "plot",
            """
            class Plot:
                produces = {"figure": "asset"}

                def materialize(self, ctx):
                    return {"figure": None}
            """,
        )

        body = class_body(acceptance.cell_path("plot"))
        assert ast.unparse(body[0]) == f"uid = {accepted.uid!r}"


class TestFlaggedShapes:
    """Flagged, never rejected — an agent's edit loop runs through broken states."""

    def test_ambiguous_invalid_note_and_incomplete_all_land_as_versions(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        ambiguous = accept(
            acceptance,
            "two_cells",
            """
            class First:
                def materialize(self, ctx):
                    return {}

            class Second:
                produces = {"data": "asset"}
            """,
        )
        invalid = accept(acceptance, "not_a_cell", "\nHELPERS = {'a': 1}\n")
        note = accept(
            acceptance,
            "findings",
            """
            class Findings:
                '''## Findings

                The seed matters.
                '''
            """,
        )
        incomplete = accept(
            acceptance,
            "half_done",
            """
            class HalfDone:
                '''Work in progress.'''

                produces = {"data": "asset"}
            """,
        )

        assert codes(ambiguous) == ["ambiguous"]
        assert codes(invalid) == ["invalid"]
        assert codes(incomplete) == ["incomplete"]
        assert note.flags == []
        assert note.classification == "note"
        assert version(store, note).manifest.classification == "note"
        assert incomplete.classification == "cell"
        assert all(
            version(store, accepted) is not None
            for accepted in (ambiguous, invalid, note, incomplete)
        )

    def test_an_invalid_file_keeps_its_identity_across_edits(
        self, acceptance: Acceptance
    ) -> None:
        first = accept(acceptance, "features", "\nWORK_IN_PROGRESS = 1\n")
        repaired = accept(acceptance, "features", FEATURES)

        assert repaired.uid == first.uid
        assert repaired.copied_from is None


class TestSlugs:
    def test_an_uppercase_filename_is_lowercased_and_flagged(
        self, acceptance: Acceptance
    ) -> None:
        path = acceptance.cell_path("Features")
        path.write_text(dedent(FEATURES), encoding="utf-8")

        accepted = acceptance.accept_path(path)

        assert accepted.slug == "features"
        assert codes(accepted) == ["hygiene"]
        assert "lowercase" in detail(accepted, "hygiene")

    def test_a_taken_name_is_suffixed_rather_than_collided(
        self, acceptance: Acceptance
    ) -> None:
        first = accept(acceptance, "features", FEATURES)
        path = acceptance.cell_path("Features")
        path.write_text(dedent(FEATURES).replace("Features", "Features2"), "utf-8")

        second = acceptance.accept_path(path)

        assert second.slug == "features_2"
        assert second.uid != first.uid
        assert any(
            "named `features`. this one is `features_2`" in (flag.detail or "")
            for flag in second.flags
        )

    def test_a_suffixed_name_settles_instead_of_renaming_itself_each_rescan(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        accept(acceptance, "features", FEATURES)
        path = acceptance.cell_path("Features")
        path.write_text(dedent(FEATURES).replace("Features", "Features2"), "utf-8")
        first = acceptance.accept_path(path)
        steps = store.next_step

        again = acceptance.accept_path(path)

        assert again.unchanged and again.version_id == first.version_id
        assert again.renamed_from is None
        assert store.next_step == steps


class TestIdentity:
    def test_a_comment_only_edit_dirties_nothing(self, acceptance: Acceptance) -> None:
        first = accept(acceptance, "features", FEATURES)
        second = accept(
            acceptance,
            "features",
            FEATURES.replace(
                "    def materialize", "    # engineer them here\n\n    def materialize"
            ),
        )

        assert second.version_id != first.version_id
        assert second.definition_hash == first.definition_hash

    def test_a_copied_file_is_reminted_with_provenance(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        original = accept(acceptance, "eval", FEATURES)
        source = acceptance.cell_path("eval").read_text(encoding="utf-8")

        copy = accept(acceptance, "eval_v2", source)

        assert copy.uid != original.uid
        assert copy.copied_from == original.uid
        (row,) = store.index.conn.execute(
            "SELECT copied_from FROM cells WHERE uid = ?", (copy.uid,)
        )
        assert row["copied_from"] == original.uid
        selections = store.index.selections(store.branches.get(MAIN_BRANCH).branch_id)
        assert selections[original.uid] == original.version_id

    def test_a_dropped_uid_line_reattaches_instead_of_reminting(
        self, acceptance: Acceptance
    ) -> None:
        first = accept(acceptance, "features", FEATURES)

        rewritten = accept(
            acceptance, "features", FEATURES.replace("Engineer", "Engineer, v2,")
        )

        assert rewritten.uid == first.uid
        assert rewritten.copied_from is None

    def test_a_clone_reattaches_through_the_committed_index(
        self, store: FlowStore, flow_dir: Path
    ) -> None:
        """A store rebuilt beside an existing `flow.yaml` — history roots fresh,
        identity does not."""
        first = Acceptance(store).accept_path(
            write(Acceptance(store), "features", FEATURES)
        )
        store.close()
        for path in sorted((flow_dir / ".lumlflow").rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        (flow_dir / ".lumlflow").rmdir()

        rebuilt = FlowStore.init(flow_dir)
        acceptance = Acceptance(rebuilt)
        accepted = acceptance.accept_path(
            write(acceptance, "features", FEATURES)  # the uid line is gone again
        )

        assert accepted.uid == first.uid


class TestRename:
    def test_mv_is_an_implicit_rename_and_costs_nothing(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        accept(acceptance, "features", FEATURES)
        trained = accept(acceptance, "train_model", TRAIN_MODEL)
        report = accept(acceptance, "report", REPORT)
        source = acceptance.cell_path("train_model").read_text(encoding="utf-8")
        acceptance.cell_path("train_model").unlink()

        renamed = accept(acceptance, "train_xgb", source)

        assert (renamed.uid, renamed.renamed_from) == (trained.uid, "train_model")
        assert renamed.copied_from is None
        # Named by identity: a consumer may be between names itself.
        assert renamed.rewire == [report.uid]
        ops = [op for entry in transactions(store) for op in entry.ops]
        assert [op.new_slug for op in ops if isinstance(op, Renamed)] == ["train_xgb"]

        rewired = accept(
            acceptance, "report", REPORT.replace("train_model.model", "train_xgb.model")
        )
        assert rewired.definition_hash == report.definition_hash
        assert rewired.uid == report.uid


class TestBinding:
    def test_a_dangling_reference_is_flagged_with_a_suggestion(
        self, acceptance: Acceptance
    ) -> None:
        accept(acceptance, "features", FEATURES)

        accepted = accept(
            acceptance, "train_model", TRAIN_MODEL.replace("train_split", "train_spilt")
        )

        assert codes(accepted) == ["dangling_ref"]
        assert detail(accepted, "dangling_ref") == (
            "unknown reference `features.train_spilt`. "
            "did you mean `features.train_split`?"
        )

    def test_a_partial_reference_is_written_back_canonically(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        accept(acceptance, "features", FEATURES)

        accepted = accept(
            acceptance,
            "train_model",
            TRAIN_MODEL.replace('"features.train_split"', '"train_split"'),
        )

        text = acceptance.cell_path("train_model").read_text(encoding="utf-8")
        assert '"train": "features.train_split"' in text
        assert accepted.flags == []
        assert version(store, accepted).manifest.consumes["train"].ref == (
            "features.train_split"
        )

    def test_a_partial_reference_with_two_producers_lists_the_candidates(
        self, acceptance: Acceptance
    ) -> None:
        accept(acceptance, "features", FEATURES)
        accept(acceptance, "splits", FEATURES.replace("Features", "Splits"))

        accepted = accept(
            acceptance,
            "train_model",
            TRAIN_MODEL.replace('"features.train_split"', '"train_split"'),
        )

        assert codes(accepted) == ["ambiguous"]
        assert detail(accepted, "ambiguous") == (
            "`train_split` is produced by more than one cell. write one of "
            "`features.train_split`, `splits.train_split`"
        )

    def test_a_reference_binds_to_identity_not_to_the_name(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        features = accept(acceptance, "features", FEATURES)
        accepted = accept(acceptance, "train_model", TRAIN_MODEL)

        bound = store.objects.get(version(store, accepted).bound_source_ref).decode()
        assert f"'train': '{features.uid}.train_split'" in bound
        assert "features.train_split" not in bound

    def test_the_bound_source_drops_comments_and_keeps_the_docstring(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        accepted = accept(
            acceptance,
            "features",
            FEATURES.replace("class Features:", "# note\nclass Features:"),
        )

        bound = store.objects.get(version(store, accepted).bound_source_ref).decode()
        assert "# note" not in bound
        assert "Engineer the model features." in bound


class TestReacceptance:
    def test_a_namespace_change_rebinds_the_consumers_on_that_branch(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        first = accept(acceptance, "features", FEATURES)
        consumer = accept(acceptance, "train_model", TRAIN_MODEL)
        store.branches.delete("features", branch=MAIN_BRANCH)
        acceptance.cell_path("features").unlink()
        recreated = accept(acceptance, "features", FEATURES)

        (rebound,) = acceptance.reaccept(["train_model"], intent="rebound consumers")

        assert recreated.uid != first.uid
        assert rebound.definition_hash != consumer.definition_hash
        assert version(store, rebound).manifest.consumes["train"].uid == recreated.uid

    def test_a_deleted_cell_leaves_its_consumers_flagged_on_that_branch(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        """Delete drops one branch's selection and reports who named the cell;
        re-accepting them is what turns the report into a flag on the card."""
        accept(acceptance, "features", FEATURES)
        accept(acceptance, "train_model", TRAIN_MODEL)

        removed = store.branches.delete("features", branch=MAIN_BRANCH)
        (rebound,) = acceptance.reaccept(removed.dangling, branch=MAIN_BRANCH)

        assert removed.dangling == ["train_model"]
        assert codes(rebound) == ["dangling_ref"]
        assert "`features.train_split`" in detail(rebound, "dangling_ref")
        assert version(store, rebound).manifest.consumes["train"].uid is None

    def test_an_adopt_that_moves_a_name_rebinds_the_consumers_it_reports(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        """The other half of the adopt story: the branch reports who has to
        re-resolve, and acceptance is what re-resolves them."""
        accept(acceptance, "features", FEATURES)
        consumer = accept(acceptance, "train_model", TRAIN_MODEL)
        store.branches.fork("sweep", from_branch=MAIN_BRANCH)
        source = acceptance.cell_path("features").read_text(encoding="utf-8")
        acceptance.cell_path("features").unlink()
        acceptance.accept_path(
            write(acceptance, "raw_features", source), branch="sweep"
        )

        result = store.branches.adopt(
            "raw_features", from_branch="sweep", to_branch=MAIN_BRANCH
        )
        (rebound,) = acceptance.reaccept(result.reaccept, branch=MAIN_BRANCH)

        assert result.reaccept == ["train_model"]
        assert rebound.definition_hash != consumer.definition_hash
        assert codes(rebound) == ["dangling_ref"]
        assert "raw_features.train_split" in detail(rebound, "dangling_ref")
        assert version(store, rebound).manifest.consumes["train"].uid is None

    def test_a_reaccepted_consumer_goes_unsynced_naming_the_rewire(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        """Re-acceptance is a real edit to the branch's wiring, so the consumer
        stops reading current and says why in the words the card shows.

        The cause is the wiring one rather than `definition-changed`: what moved
        is where the input comes from, and reporting a daemon-driven rebind
        differently from a hand-edited one would name the same change twice.
        """
        accept(acceptance, "features", FEATURES)
        consumer = accept(acceptance, "train_model", TRAIN_MODEL)
        record_run(store, consumer)

        removed = store.branches.delete("features", branch=MAIN_BRANCH)
        acceptance.reaccept(removed.dangling, branch=MAIN_BRANCH)

        branch_id = store.branches.get(MAIN_BRANCH).branch_id
        verdict = staleness.derive_all(store.index, branch_id)[consumer.uid]
        assert verdict.state == "unsynced"
        assert [(cause.kind, cause.detail) for cause in verdict.causes] == [
            ("deps-rewired", "`train` now comes from a different cell")
        ]

    def test_reaccepting_an_unmoved_binding_writes_no_version(
        self, store: FlowStore, acceptance: Acceptance
    ) -> None:
        accept(acceptance, "features", FEATURES)
        consumer = accept(acceptance, "train_model", TRAIN_MODEL)
        steps = store.next_step

        (result,) = acceptance.reaccept(["train_model"])

        assert result.unchanged and result.version_id == consumer.version_id
        assert store.next_step == steps


class TestDivergence:
    def test_an_edit_from_a_superseded_parent_is_flagged_not_advanced(
        self, acceptance: Acceptance
    ) -> None:
        first = accept(acceptance, "features", FEATURES)
        accept(acceptance, "features", FEATURES.replace("Engineer", "Engineer again"))

        accepted = accept(
            acceptance,
            "features",
            FEATURES.replace("Engineer", "Engineer differently"),
            base_version_id=first.version_id,
        )

        assert codes(accepted) == ["divergent"]
        assert "save it to a new lane" in detail(accepted, "divergent")
