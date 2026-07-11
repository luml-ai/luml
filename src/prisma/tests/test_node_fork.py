import json
from pathlib import Path

from luml_prisma.services.orchestrator.nodes.base import NodeResult
from luml_prisma.services.orchestrator.nodes.fork import (
    ForkNodeHandler,
    _ensure_gitignore_entry,
    _read_fork_file,
    _read_fork_json,
    _read_proposals,
)


class TestForkNodeHandler:
    def test_type_id(self) -> None:
        assert ForkNodeHandler().type_id() == "fork"

    def test_can_fork(self) -> None:
        assert ForkNodeHandler().can_fork(
            NodeResult(success=True),
        ) is False


class TestReadProposals:
    def test_reads_valid_proposals(
        self, tmp_path: Path,
    ) -> None:
        proposals_dir = tmp_path / ".proposals"
        proposals_dir.mkdir()
        (proposals_dir / "proposal_1.json").write_text(
            json.dumps({"title": "A", "prompt": "do A"}),
        )
        (proposals_dir / "proposal_2.json").write_text(
            json.dumps({"title": "B", "prompt": "do B"}),
        )

        result = _read_proposals(proposals_dir, 3)
        assert len(result) == 2
        assert result[0]["title"] == "A"
        assert result[1]["prompt"] == "do B"

    def test_respects_max_count(
        self, tmp_path: Path,
    ) -> None:
        proposals_dir = tmp_path / ".proposals"
        proposals_dir.mkdir()
        for i in range(1, 6):
            (proposals_dir / f"proposal_{i}.json").write_text(
                json.dumps({
                    "title": f"P{i}", "prompt": f"do {i}",
                }),
            )

        result = _read_proposals(proposals_dir, 3)
        assert len(result) == 3

    def test_skips_missing_files(
        self, tmp_path: Path,
    ) -> None:
        proposals_dir = tmp_path / ".proposals"
        proposals_dir.mkdir()
        (proposals_dir / "proposal_2.json").write_text(
            json.dumps({"title": "B", "prompt": "do B"}),
        )

        result = _read_proposals(proposals_dir, 3)
        assert len(result) == 1

    def test_skips_invalid_json(
        self, tmp_path: Path,
    ) -> None:
        proposals_dir = tmp_path / ".proposals"
        proposals_dir.mkdir()
        (proposals_dir / "proposal_1.json").write_text(
            "not json",
        )
        (proposals_dir / "proposal_2.json").write_text(
            json.dumps({"title": "B", "prompt": "ok"}),
        )

        result = _read_proposals(proposals_dir, 3)
        assert len(result) == 1
        assert result[0]["title"] == "B"

    def test_empty_dir(self, tmp_path: Path) -> None:
        proposals_dir = tmp_path / ".proposals"
        proposals_dir.mkdir()
        assert _read_proposals(proposals_dir, 3) == []


class TestReadForkFile:
    def test_reads_valid_fork_file(
        self, tmp_path: Path,
    ) -> None:
        (tmp_path / ".luml-fork.json").write_text(
            json.dumps(["do A", "do B", "do C"]),
        )
        result = _read_fork_file(str(tmp_path), 5)
        assert result == ["do A", "do B", "do C"]

    def test_respects_max_count(
        self, tmp_path: Path,
    ) -> None:
        (tmp_path / ".luml-fork.json").write_text(
            json.dumps(["a", "b", "c", "d", "e"]),
        )
        result = _read_fork_file(str(tmp_path), 3)
        assert result == ["a", "b", "c"]

    def test_returns_none_for_missing_file(
        self, tmp_path: Path,
    ) -> None:
        assert _read_fork_file(str(tmp_path), 3) is None

    def test_returns_none_for_invalid_json(
        self, tmp_path: Path,
    ) -> None:
        (tmp_path / ".luml-fork.json").write_text(
            "not json {{{",
        )
        assert _read_fork_file(str(tmp_path), 3) is None

    def test_returns_none_for_non_list(
        self, tmp_path: Path,
    ) -> None:
        (tmp_path / ".luml-fork.json").write_text(
            json.dumps({"key": "val"}),
        )
        assert _read_fork_file(str(tmp_path), 3) is None

    def test_returns_none_for_list_with_non_strings(
        self, tmp_path: Path,
    ) -> None:
        (tmp_path / ".luml-fork.json").write_text(
            json.dumps(["ok", 42, "also ok"]),
        )
        assert _read_fork_file(str(tmp_path), 5) is None


class TestEnsureGitignoreEntry:
    def test_creates_gitignore(
        self, tmp_path: Path,
    ) -> None:
        gitignore = tmp_path / ".gitignore"
        _ensure_gitignore_entry(gitignore, ".proposals/")
        assert ".proposals/" in gitignore.read_text()

    def test_appends_to_existing(
        self, tmp_path: Path,
    ) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n")
        _ensure_gitignore_entry(gitignore, ".proposals/")
        content = gitignore.read_text()
        assert "node_modules/" in content
        assert ".proposals/" in content

    def test_does_not_duplicate(
        self, tmp_path: Path,
    ) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".proposals/\n")
        _ensure_gitignore_entry(gitignore, ".proposals/")
        assert (
            gitignore.read_text().count(".proposals/") == 1
        )


class TestReadForkJson:
    def test_reads_object_proposals(self, tmp_path: Path) -> None:
        luml_dir = tmp_path / ".prisma"
        luml_dir.mkdir()
        (luml_dir / "fork.json").write_text(json.dumps([
            {"prompt": "Try SVM", "title": "SVM"},
            {"prompt": "Try RF", "title": "RF"},
        ]))
        result = _read_fork_json(str(tmp_path), 5)
        assert result is not None
        assert len(result) == 2
        assert result[0]["prompt"] == "Try SVM"
        assert result[1]["title"] == "RF"

    def test_reads_string_proposals_as_objects(self, tmp_path: Path) -> None:
        luml_dir = tmp_path / ".prisma"
        luml_dir.mkdir()
        (luml_dir / "fork.json").write_text(json.dumps(["do A", "do B"]))
        result = _read_fork_json(str(tmp_path), 5)
        assert result is not None
        assert len(result) == 2
        assert result[0] == {"prompt": "do A"}
        assert result[1] == {"prompt": "do B"}

    def test_respects_max_count(self, tmp_path: Path) -> None:
        luml_dir = tmp_path / ".prisma"
        luml_dir.mkdir()
        (luml_dir / "fork.json").write_text(json.dumps([
            {"prompt": f"p{i}", "title": f"t{i}"} for i in range(10)
        ]))
        result = _read_fork_json(str(tmp_path), 3)
        assert result is not None
        assert len(result) == 3

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert _read_fork_json(str(tmp_path), 3) is None

    def test_returns_none_for_non_list(self, tmp_path: Path) -> None:
        luml_dir = tmp_path / ".prisma"
        luml_dir.mkdir()
        (luml_dir / "fork.json").write_text(json.dumps({"key": "val"}))
        assert _read_fork_json(str(tmp_path), 3) is None

    def test_returns_none_for_empty_valid_items(self, tmp_path: Path) -> None:
        luml_dir = tmp_path / ".prisma"
        luml_dir.mkdir()
        (luml_dir / "fork.json").write_text(json.dumps([42, True, None]))
        assert _read_fork_json(str(tmp_path), 5) is None

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        luml_dir = tmp_path / ".prisma"
        luml_dir.mkdir()
        (luml_dir / "fork.json").write_text("not json {{{")
        import pytest
        with pytest.raises(json.JSONDecodeError):
            _read_fork_json(str(tmp_path), 3)

    def test_skips_objects_without_prompt(self, tmp_path: Path) -> None:
        luml_dir = tmp_path / ".prisma"
        luml_dir.mkdir()
        (luml_dir / "fork.json").write_text(json.dumps([
            {"title": "no prompt"},
            {"prompt": "has prompt", "title": "ok"},
        ]))
        result = _read_fork_json(str(tmp_path), 5)
        assert result is not None
        assert len(result) == 1
        assert result[0]["prompt"] == "has prompt"


class TestChildPayloadConstruction:
    def test_child_payload_has_proposal_dict(self) -> None:
        proposals = [
            {"prompt": "Try SVM", "title": "SVM"},
            {"prompt": "Try RF", "title": "RF"},
        ]
        parent_objective = "Train classifier"
        parent_experiment_ids = ["exp-1", "exp-2"]
        parent_metric_keys = ["accuracy", "loss"]

        spawn_next = []
        for proposal in proposals:
            from luml_prisma.services.orchestrator.nodes.base import NodeSpawnSpec
            child_payload = {
                "proposal": proposal,
                "objective": parent_objective,
                "experiment_ids": parent_experiment_ids,
                "discovered_metric_keys": parent_metric_keys,
            }
            spawn_next.append(NodeSpawnSpec(
                node_type="implement",
                payload=child_payload,
                reason="fork",
            ))

        assert len(spawn_next) == 2
        p0 = spawn_next[0].payload
        assert p0["proposal"] == {"prompt": "Try SVM", "title": "SVM"}
        assert p0["objective"] == "Train classifier"
        assert p0["experiment_ids"] == ["exp-1", "exp-2"]
        assert p0["discovered_metric_keys"] == ["accuracy", "loss"]

        p1 = spawn_next[1].payload
        assert p1["proposal"]["prompt"] == "Try RF"
