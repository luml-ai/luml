from luml_agent.services.orchestrator.prompts import (
    _GUIDE_REF,
    build_debug_prompt,
    build_fork_prompt,
    build_implement_prompt,
)


class TestBuildImplementPromptRoot:
    def test_root_prompt_includes_objective(self) -> None:
        payload = {"prompt": "Train a classifier on iris dataset"}
        result = build_implement_prompt(
            payload, {}, worktree_path="/tmp/wt", base_branch="main",
        )
        assert "Train a classifier on iris dataset" in result

    def test_root_prompt_includes_environment(self) -> None:
        result = build_implement_prompt(
            {"prompt": "test"},
            {},
            worktree_path="/tmp/wt",
            base_branch="develop",
        )
        assert "/tmp/wt" in result
        assert "develop" in result
        assert "uv" in result

    def test_root_prompt_references_guide_md(self) -> None:
        result = build_implement_prompt(
            {"prompt": "test"}, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert ".luml-agent/guide.md" in result

    def test_root_prompt_includes_metric_rules(self) -> None:
        result = build_implement_prompt(
            {"prompt": "test"}, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert "Metric Rules" in result
        assert "always maximizes" in result

    def test_root_prompt_does_not_include_parent_experiments(self) -> None:
        result = build_implement_prompt(
            {"prompt": "test"}, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert "Parent Experiments" not in result


class TestBuildImplementPromptForkChild:
    def test_fork_child_uses_proposal_as_primary(self) -> None:
        payload = {
            "proposal": {"prompt": "Try gradient boosting", "title": "GBM"},
            "objective": "Train a classifier",
        }
        result = build_implement_prompt(
            payload, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert result.index("Try gradient boosting") < result.index(
            "Train a classifier",
        )

    def test_fork_child_labels_objective_as_context(self) -> None:
        payload = {
            "proposal": {"prompt": "Try XGBoost", "title": "XGB"},
            "objective": "Build a model",
        }
        result = build_implement_prompt(
            payload, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert "context only" in result.lower()

    def test_fork_child_includes_metric_consistency(self) -> None:
        payload = {
            "proposal": {"prompt": "Try SVM", "title": "SVM"},
            "objective": "classify",
            "discovered_metric_keys": ["accuracy", "loss"],
        }
        result = build_implement_prompt(
            payload, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert "Metric Rules" in result
        assert "accuracy" in result
        assert "loss" in result

    def test_fork_child_includes_experiment_ids(self) -> None:
        payload = {
            "proposal": {"prompt": "Try RF", "title": "RF"},
            "objective": "classify",
            "experiment_ids": ["exp-abc", "exp-def"],
        }
        result = build_implement_prompt(
            payload, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert "exp-abc" in result
        assert "exp-def" in result
        assert "luml-inspect" in result

    def test_fork_child_references_guide_md(self) -> None:
        payload = {
            "proposal": {"prompt": "Try RF", "title": "RF"},
            "objective": "classify",
        }
        result = build_implement_prompt(
            payload, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert ".luml-agent/guide.md" in result

    def test_fork_child_no_metrics_shows_none(self) -> None:
        payload = {
            "proposal": {"prompt": "Try RF", "title": "RF"},
            "objective": "classify",
        }
        result = build_implement_prompt(
            payload, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert "(none specified)" in result

    def test_fork_child_no_experiment_ids_shows_none(self) -> None:
        payload = {
            "proposal": {"prompt": "Try RF", "title": "RF"},
            "objective": "classify",
        }
        result = build_implement_prompt(
            payload, {},
            worktree_path="/tmp/wt", base_branch="main",
        )
        assert "(none available)" in result


class TestBuildDebugPrompt:
    def test_includes_exit_code(self) -> None:
        payload = {
            "failure_context": {"exit_code": 1, "logs": "err"},
            "objective": "fix it",
        }
        result = build_debug_prompt(payload, "diff here", "err", {})
        assert "1" in result

    def test_includes_objective(self) -> None:
        payload = {
            "failure_context": {"exit_code": 1},
            "objective": "Train a model",
        }
        result = build_debug_prompt(payload, "", "logs", {})
        assert "Train a model" in result

    def test_includes_git_diff(self) -> None:
        diff = "+added line\n-removed line"
        payload = {"failure_context": {"exit_code": 1}, "objective": ""}
        result = build_debug_prompt(payload, diff, "logs", {})
        assert "+added line" in result
        assert "-removed line" in result

    def test_truncates_logs_at_max_log_tail(self) -> None:
        long_logs = "x" * 50000
        payload = {"failure_context": {"exit_code": 1}, "objective": ""}
        result = build_debug_prompt(
            payload, "", long_logs,
            {"max_log_tail": 20000},
        )
        log_section_start = result.index("```\n", result.index("Failure Logs"))
        log_section = result[log_section_start:]
        assert len(log_section) < 25000

    def test_uses_default_max_log_tail(self) -> None:
        long_logs = "a" * 15000
        payload = {"failure_context": {"exit_code": 1}, "objective": ""}
        result = build_debug_prompt(payload, "", long_logs, {})
        assert "10000" in result

    def test_short_logs_not_truncated(self) -> None:
        logs = "short error"
        payload = {"failure_context": {"exit_code": 1}, "objective": ""}
        result = build_debug_prompt(payload, "", logs, {})
        assert "short error" in result

    def test_references_guide_md(self) -> None:
        payload = {"failure_context": {"exit_code": 1}, "objective": ""}
        result = build_debug_prompt(payload, "", "", {})
        assert ".luml-agent/guide.md" in result

    def test_includes_experiment_tracking_preservation(self) -> None:
        payload = {"failure_context": {"exit_code": 1}, "objective": ""}
        result = build_debug_prompt(payload, "", "", {})
        assert "experiment tracking" in result.lower()


class TestBuildForkPrompt:
    def test_includes_objective(self) -> None:
        payload = {"objective": "Train a classifier on iris dataset"}
        result = build_fork_prompt(payload, {})
        assert "Train a classifier on iris dataset" in result

    def test_includes_experiment_ids(self) -> None:
        payload = {
            "objective": "test",
            "experiment_ids": ["exp-abc", "exp-def"],
        }
        result = build_fork_prompt(payload, {})
        assert "exp-abc" in result
        assert "exp-def" in result
        assert "luml-inspect" in result

    def test_references_fork_json(self) -> None:
        result = build_fork_prompt({"objective": "test"}, {})
        assert ".luml-agent/fork.json" in result

    def test_includes_decomposition_guidelines(self) -> None:
        result = build_fork_prompt({"objective": "test"}, {})
        assert "diverse" in result.lower()
        assert "self-contained" in result.lower()

    def test_includes_output_format(self) -> None:
        result = build_fork_prompt({"objective": "test"}, {})
        assert ".luml-agent/fork.json" in result
        assert '"prompt"' in result
        assert '"title"' in result

    def test_includes_max_children(self) -> None:
        result = build_fork_prompt(
            {"objective": "test"},
            {"max_children_per_fork": 5},
        )
        assert "5" in result

    def test_default_max_children(self) -> None:
        result = build_fork_prompt({"objective": "test"}, {})
        assert "3" in result

    def test_includes_metric_keys(self) -> None:
        payload = {
            "objective": "test",
            "discovered_metric_keys": ["accuracy", "loss"],
        }
        result = build_fork_prompt(payload, {})
        assert "accuracy" in result
        assert "loss" in result
        assert "metric consistency" in result.lower()

    def test_no_metrics_shows_none(self) -> None:
        result = build_fork_prompt({"objective": "test"}, {})
        assert "(none specified)" in result

    def test_no_experiment_ids_shows_none(self) -> None:
        result = build_fork_prompt({"objective": "test"}, {})
        assert "(none available)" in result

    def test_includes_no_code_modification_rule(self) -> None:
        result = build_fork_prompt({"objective": "test"}, {})
        assert "Do NOT modify any code files" in result


class TestGuideRefInAllPrompts:
    def test_guide_ref_constant(self) -> None:
        assert ".luml-agent/guide.md" in _GUIDE_REF

    def test_root_implement_has_guide_ref(self) -> None:
        result = build_implement_prompt(
            {"prompt": "x"}, {},
            worktree_path="", base_branch="",
        )
        assert _GUIDE_REF in result

    def test_fork_child_has_guide_ref(self) -> None:
        result = build_implement_prompt(
            {"proposal": {"prompt": "x", "title": "t"}, "objective": "o"},
            {},
            worktree_path="", base_branch="",
        )
        assert _GUIDE_REF in result

    def test_debug_has_guide_ref(self) -> None:
        result = build_debug_prompt(
            {"failure_context": {"exit_code": 1}, "objective": ""},
            "", "", {},
        )
        assert _GUIDE_REF in result
