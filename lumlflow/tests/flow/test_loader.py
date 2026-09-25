from textwrap import dedent

from lumlflow.flow.dsl import loader
from lumlflow.flow.store.models import OutputSpec


def codes(flags: list) -> list[str]:
    return [flag.code for flag in flags]


def detail(flags: list, code: str) -> str:
    return next(flag.detail or "" for flag in flags if flag.code == code)


class TestClassification:
    def test_a_class_with_materialize_is_the_cell(self) -> None:
        parsed = loader.parse(
            dedent("""
            class TrainXGB:
                '''Train the churn model.'''

                consumes = {"train": "features.train_split"}
                produces = {"model": "model", "run": "experiment"}

                def materialize(self, ctx, train):
                    return {}
            """)
        )

        assert parsed.cell is not None
        assert parsed.cell.name == "TrainXGB"
        assert parsed.cell.classification == "cell"
        assert parsed.cell.consumes == {"train": "features.train_split"}
        assert parsed.cell.produces == {
            "model": OutputSpec(type="model"),
            "run": OutputSpec(type="experiment"),
        }
        assert parsed.flags == []

    def test_two_candidates_are_ambiguous_and_still_yield_a_cell(self) -> None:
        parsed = loader.parse(
            dedent("""
            class First:
                def materialize(self, ctx):
                    return {}

            class Second:
                produces = {"data": "asset"}
            """)
        )

        assert codes(parsed.flags) == ["ambiguous"]
        assert "`First`, `Second`" in detail(parsed.flags, "ambiguous")
        assert parsed.cell is not None and parsed.cell.name == "First"

    def test_a_file_with_no_qualifying_class_is_invalid(self) -> None:
        parsed = loader.parse("def helper():\n    return 1\n")

        assert codes(parsed.flags) == ["invalid"]
        assert parsed.cell is None

    def test_a_class_with_only_a_docstring_is_a_note(self) -> None:
        parsed = loader.parse(
            dedent("""
            class Findings:
                '''## What we learned

                The seed matters.
                '''
            """)
        )

        assert parsed.cell is not None
        assert parsed.cell.classification == "note"
        assert parsed.cell.docstring is not None
        assert "What we learned" in parsed.cell.docstring
        assert parsed.flags == []

    def test_a_note_stays_a_note_once_its_uid_is_written_back(self) -> None:
        parsed = loader.parse(
            dedent("""
            class Findings:
                '''Notes.'''
                uid = "01J9W3ZK7QABCDEF0123456789"
            """)
        )

        assert parsed.cell is not None
        assert parsed.cell.classification == "note"
        assert parsed.cell.uid == "01J9W3ZK7QABCDEF0123456789"

    def test_declarations_without_materialize_are_incomplete_never_a_note(self) -> None:
        parsed = loader.parse(
            dedent("""
            class HalfWritten:
                '''Work in progress.'''

                consumes = {"train": "features.train_split"}
            """)
        )

        assert codes(parsed.flags) == ["incomplete"]
        assert parsed.cell is not None and parsed.cell.classification == "cell"

    def test_a_file_that_does_not_parse_is_invalid_not_an_exception(self) -> None:
        parsed = loader.parse("class Broken:\n    def materialize(self ctx)\n")

        assert codes(parsed.flags) == ["invalid"]
        assert "does not parse" in detail(parsed.flags, "invalid")
        assert parsed.cell is None


class TestDeclarations:
    def test_a_non_literal_declaration_is_flagged_and_dropped(self) -> None:
        parsed = loader.parse(
            dedent("""
            class Sweep:
                params = {"lr": 3e-4 * 2}

                def materialize(self, ctx):
                    return {}
            """)
        )

        assert codes(parsed.flags) == ["invalid"]
        assert "not a literal" in detail(parsed.flags, "invalid")
        assert parsed.cell is not None and parsed.cell.params == {}

    def test_an_output_word_outside_the_vocabulary_is_flagged_and_kept(self) -> None:
        parsed = loader.parse(
            dedent("""
            class Trainer:
                produces = {"model": "modell"}

                def materialize(self, ctx):
                    return {}
            """)
        )

        assert codes(parsed.flags) == ["invalid"]
        assert "model, dataset, experiment, or asset" in detail(parsed.flags, "invalid")
        assert parsed.cell is not None
        assert parsed.cell.produces == {"model": OutputSpec(type="asset")}

    def test_a_dict_override_rides_in_place_of_the_word(self) -> None:
        parsed = loader.parse(
            dedent("""
            class Trainer:
                produces = {"frame": {"type": "asset", "kind": "frame",
                                      "persist": False}}

                def materialize(self, ctx):
                    return {}
            """)
        )

        assert parsed.cell is not None
        assert parsed.cell.produces == {
            "frame": OutputSpec(type="asset", kind="frame", persist=False)
        }
        assert parsed.flags == []

    def test_params_volatility_and_env_sensitivity_are_recorded(self) -> None:
        parsed = loader.parse(
            dedent("""
            class Trainer:
                params = {"lr": 0.0003, "seed": 1337}
                volatility = "external"
                env_sensitive = True

                def materialize(self, ctx):
                    return {}
            """)
        )

        assert parsed.cell is not None
        assert parsed.cell.params == {"lr": 0.0003, "seed": 1337}
        assert (parsed.cell.volatility, parsed.cell.env_sensitive) == ("external", True)
