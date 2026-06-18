import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import StatusCode

from luml.experiments.evaluation.scorers.builtin._base import (
    LLMJudgeScorer,
    SupervisedLLMJudgeScorer,
    _call_judge,
    _client_model,
    _default_client,
    _disambiguate_scorer_names,
    _extract_input,
    _run_traced_judge,
    _try_parse,
)
from luml.experiments.evaluation.scorers.builtin._exceptions import JudgeModelError
from luml.experiments.evaluation.scorers.builtin.completeness import Completeness
from luml.experiments.evaluation.scorers.builtin.relevancy import Relevancy
from luml.llm import LLMClient


class _InMemoryExporter(SpanExporter):
    def __init__(self) -> None:
        self._spans: list[ReadableSpan] = []

    def export(self, spans: Any) -> SpanExportResult:  # noqa: ANN401
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def get_finished_spans(self) -> list[ReadableSpan]:
        return list(self._spans)


class TestTryParse:
    def test_valid_json_with_numeric_score(self) -> None:
        raw = json.dumps({"reasoning": "good", "score": 0.8})
        result = _try_parse(raw)
        assert result is not None
        assert result["score"] == 0.8
        assert result["reasoning"] == "good"

    def test_valid_json_with_int_score(self) -> None:
        raw = json.dumps({"reasoning": "perfect", "score": 1})
        result = _try_parse(raw)
        assert result is not None
        assert result["score"] == 1

    def test_invalid_json(self) -> None:
        assert _try_parse("not json") is None

    def test_missing_score_key(self) -> None:
        raw = json.dumps({"reasoning": "good"})
        assert _try_parse(raw) is None

    def test_bool_score_rejected(self) -> None:
        raw = json.dumps({"reasoning": "good", "score": True})
        assert _try_parse(raw) is None

    def test_string_score_rejected(self) -> None:
        raw = json.dumps({"reasoning": "good", "score": "0.5"})
        assert _try_parse(raw) is None

    def test_non_dict_json(self) -> None:
        raw = json.dumps([1, 2, 3])
        assert _try_parse(raw) is None


class TestCallJudge:
    def test_success_first_try(self) -> None:
        client = MagicMock(spec=LLMClient)
        client.complete.return_value = json.dumps({"reasoning": "ok", "score": 0.7})
        result = _call_judge(client, "sys", "user")
        assert result["score"] == 0.7
        assert client.complete.call_count == 1

    def test_success_on_retry(self) -> None:
        client = MagicMock(spec=LLMClient)
        client.complete.side_effect = [
            "bad json",
            json.dumps({"reasoning": "ok", "score": 0.5}),
        ]
        result = _call_judge(client, "sys", "user")
        assert result["score"] == 0.5
        assert client.complete.call_count == 2
        second_call_prompt = client.complete.call_args_list[1][0][1]
        assert "previous response was invalid" in second_call_prompt

    def test_failure_twice_raises_judge_model_error(self) -> None:
        client = MagicMock(spec=LLMClient)
        client.complete.side_effect = ["bad", "also bad"]
        with pytest.raises(JudgeModelError, match="numeric 'score'"):
            _call_judge(client, "sys", "user")
        assert client.complete.call_count == 2


class TestDefaultClient:
    def test_returns_provided_client(self) -> None:
        client = MagicMock(spec=LLMClient)
        assert _default_client(client) is client

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_creates_json_mode_openai_client_when_none(
        self, mock_cls: MagicMock
    ) -> None:
        result = _default_client(None)
        mock_cls.assert_called_once_with(response_format={"type": "json_object"})
        assert result is mock_cls.return_value


class TestExtractInput:
    def test_single_str_input_key_present(self) -> None:
        inputs = {"question": "what?", "other": "x"}
        result = _extract_input(inputs, "question", ("query",))
        assert result == "what?"

    def test_tuple_input_key_tried_in_order(self) -> None:
        inputs = {"query": "q1", "question": "q2"}
        result = _extract_input(inputs, ("custom", "query"), ("question",))
        assert result == "q1"

    def test_override_before_defaults(self) -> None:
        inputs = {"question": "q1", "custom": "c1"}
        result = _extract_input(inputs, "custom", ("question",))
        assert result == "c1"

    def test_fallback_to_default_keys(self) -> None:
        inputs = {"question": "q1"}
        result = _extract_input(inputs, None, ("question",))
        assert result == "q1"

    def test_second_default_key(self) -> None:
        inputs = {"query": "q1"}
        result = _extract_input(inputs, None, ("question", "query"))
        assert result == "q1"

    def test_no_keys_match_returns_str_inputs(self) -> None:
        inputs = {"other": "val"}
        result = _extract_input(inputs, None, ("question", "query"))
        assert result == str(inputs)

    def test_input_key_none_with_empty_tuple(self) -> None:
        inputs = {"x": 1}
        result = _extract_input(inputs, None, ())
        assert result == str(inputs)


class _ModelClient:
    """Minimal client that exposes a model, like ``OpenAIClient``."""

    def __init__(self, model: str | None = "gpt-4.1-mini") -> None:
        self._model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return "{}"


class TestClientModel:
    def test_reads_private_model_attr(self) -> None:
        assert _client_model(_ModelClient("gpt-4o-mini")) == "gpt-4o-mini"

    def test_reads_public_model_attr(self) -> None:
        client = MagicMock(spec=LLMClient)
        client.model = "claude"
        assert _client_model(client) == "claude"

    def test_returns_none_when_no_model(self) -> None:
        # spec=LLMClient exposes only ``complete``, so model probing fails.
        assert _client_model(MagicMock(spec=LLMClient)) is None


class TestDisambiguateScorerNames:
    def test_lone_scorer_keeps_bare_name(self) -> None:
        scorer = Relevancy(client=_ModelClient("gpt-4.1-mini"))
        _disambiguate_scorer_names([scorer])
        assert scorer.get_name() == "relevancy"

    def test_different_clients_suffixed_by_model(self) -> None:
        a = Relevancy(client=_ModelClient("gpt-4.1-mini"))
        b = Relevancy(client=_ModelClient("gpt-4o-mini"))
        _disambiguate_scorer_names([a, b])
        assert a.get_name() == "relevancy_gpt-4.1-mini"
        assert b.get_name() == "relevancy_gpt-4o-mini"

    def test_different_input_keys_suffixed_by_key_only(self) -> None:
        client = _ModelClient("gpt-4.1-mini")
        a = Relevancy(client=client, input_key="prompt")
        b = Relevancy(client=client, input_key="question")
        _disambiguate_scorer_names([a, b])
        assert a.get_name() == "relevancy_prompt"
        assert b.get_name() == "relevancy_question"

    def test_same_input_key_different_clients_suffixed_by_model_only(self) -> None:
        # Case 3: input_key is identical, so it is not used; only model differs.
        a = Relevancy(client=_ModelClient("gpt-4.1-mini"), input_key="prompt")
        b = Relevancy(client=_ModelClient("gpt-4o-mini"), input_key="prompt")
        _disambiguate_scorer_names([a, b])
        assert a.get_name() == "relevancy_gpt-4.1-mini"
        assert b.get_name() == "relevancy_gpt-4o-mini"

    def test_both_dimensions_differ_uses_both(self) -> None:
        a = Relevancy(client=_ModelClient("gpt-4.1-mini"), input_key="prompt")
        b = Relevancy(client=_ModelClient("gpt-4o-mini"), input_key="question")
        _disambiguate_scorer_names([a, b])
        assert a.get_name() == "relevancy_prompt_gpt-4.1-mini"
        assert b.get_name() == "relevancy_question_gpt-4o-mini"

    def test_explicit_names_untouched(self) -> None:
        a = Relevancy(client=_ModelClient("gpt-4.1-mini"), name="rel_a")
        b = Relevancy(client=_ModelClient("gpt-4o-mini"), name="rel_b")
        _disambiguate_scorer_names([a, b])
        assert a.get_name() == "rel_a"
        assert b.get_name() == "rel_b"

    def test_different_scorer_types_not_grouped(self) -> None:
        rel = Relevancy(client=_ModelClient("gpt-4.1-mini"))
        comp = Completeness(client=_ModelClient("gpt-4o-mini"))
        _disambiguate_scorer_names([rel, comp])
        assert rel.get_name() == "relevancy"
        assert comp.get_name() == "completeness"

    def test_truly_identical_scorers_still_collide(self) -> None:
        client = _ModelClient("gpt-4.1-mini")
        a = Relevancy(client=client)
        b = Relevancy(client=client)
        _disambiguate_scorer_names([a, b])
        assert a.get_name() == "relevancy"
        assert b.get_name() == "relevancy"

    def test_idempotent(self) -> None:
        a = Relevancy(client=_ModelClient("gpt-4.1-mini"))
        b = Relevancy(client=_ModelClient("gpt-4o-mini"))
        _disambiguate_scorer_names([a, b])
        _disambiguate_scorer_names([a, b])
        assert a.get_name() == "relevancy_gpt-4.1-mini"
        assert b.get_name() == "relevancy_gpt-4o-mini"


class _StubUnsupervisedScorer(LLMJudgeScorer):
    def default_name(self) -> str:
        return "stub"

    def build_prompt(
        self,
        inputs: dict[str, Any],
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]:
        return ("system", f"user: {output}")


class _StubSupervisedScorer(SupervisedLLMJudgeScorer):
    def default_name(self) -> str:
        return "stub_supervised"

    def build_prompt(
        self,
        inputs: dict[str, Any],
        expected_output: Any,  # noqa: ANN401
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]:
        return ("system", f"expected={expected_output} output={output}")


class TestParseJudgment:
    def test_clamps_score_above_1(self) -> None:
        scorer = _StubUnsupervisedScorer.__new__(_StubUnsupervisedScorer)
        scorer._name = "stub"
        result = scorer.parse_judgment({"score": 1.5, "reasoning": "high"})
        assert result["stub"] == 1.0

    def test_clamps_score_below_0(self) -> None:
        scorer = _StubUnsupervisedScorer.__new__(_StubUnsupervisedScorer)
        scorer._name = "stub"
        result = scorer.parse_judgment({"score": -0.3, "reasoning": "low"})
        assert result["stub"] == 0.0

    def test_normal_score(self) -> None:
        scorer = _StubUnsupervisedScorer.__new__(_StubUnsupervisedScorer)
        scorer._name = "stub"
        result = scorer.parse_judgment({"score": 0.75, "reasoning": "good"})
        assert result["stub"] == 0.75
        assert result["stub_reasoning"] == "good"

    def test_missing_reasoning_defaults_to_empty(self) -> None:
        scorer = _StubUnsupervisedScorer.__new__(_StubUnsupervisedScorer)
        scorer._name = "stub"
        result = scorer.parse_judgment({"score": 0.5})
        assert result["stub_reasoning"] == ""

    def test_key_names_use_scorer_name(self) -> None:
        scorer = _StubUnsupervisedScorer.__new__(_StubUnsupervisedScorer)
        scorer._name = "my_scorer"
        result = scorer.parse_judgment({"score": 0.6, "reasoning": "r"})
        assert "my_scorer" in result
        assert "my_scorer_reasoning" in result


class TestLLMJudgeScorer:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_calls_build_prompt_and_judge(self, mock_openai: MagicMock) -> None:
        client = MagicMock(spec=LLMClient)
        client.complete.return_value = json.dumps({"reasoning": "ok", "score": 0.9})
        scorer = _StubUnsupervisedScorer(client=client)
        result = scorer.score({"question": "q"}, "output")
        assert result["stub"] == 0.9
        assert "stub_reasoning" in result
        client.complete.assert_called_once_with("system", "user: output")

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_custom_name_honored(self, mock_openai: MagicMock) -> None:
        client = MagicMock(spec=LLMClient)
        client.complete.return_value = json.dumps({"reasoning": "ok", "score": 0.8})
        scorer = _StubUnsupervisedScorer(client=client, name="custom")
        assert scorer.get_name() == "custom"
        result = scorer.score({}, "out")
        assert "custom" in result
        assert "custom_reasoning" in result

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_passed_client_used_as_is(self, mock_openai: MagicMock) -> None:
        client = MagicMock(spec=LLMClient)
        client.complete.return_value = json.dumps({"reasoning": "ok", "score": 0.5})
        scorer = _StubUnsupervisedScorer(client=client)
        scorer.score({}, "out")
        mock_openai.assert_not_called()
        client.complete.assert_called_once()


class TestSupervisedLLMJudgeScorer:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_passes_expected_output(self, mock_openai: MagicMock) -> None:
        client = MagicMock(spec=LLMClient)
        client.complete.return_value = json.dumps({"reasoning": "ok", "score": 0.7})
        scorer = _StubSupervisedScorer(client=client)
        result = scorer.score({"q": "q"}, "expected", "actual")
        assert result["stub_supervised"] == 0.7
        client.complete.assert_called_once_with(
            "system", "expected=expected output=actual"
        )

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_custom_name(self, mock_openai: MagicMock) -> None:
        client = MagicMock(spec=LLMClient)
        client.complete.return_value = json.dumps({"reasoning": "r", "score": 0.6})
        scorer = _StubSupervisedScorer(client=client, name="my_sup")
        assert scorer.get_name() == "my_sup"
        result = scorer.score({}, "exp", "out")
        assert "my_sup" in result


class TestRunTracedJudge:
    def test_emits_llm_judge_span_with_attributes(self) -> None:
        exporter = _InMemoryExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        with patch(
            "luml.experiments.evaluation.scorers.builtin._base._tracer",
            provider.get_tracer(__name__),
        ):
            client = MagicMock(spec=LLMClient)
            client.complete.return_value = json.dumps(
                {"reasoning": "ok", "score": 0.85}
            )
            scorer = _StubUnsupervisedScorer.__new__(_StubUnsupervisedScorer)
            scorer._name = "test_scorer"
            scorer._client = client

            _run_traced_judge(scorer, client, "sys", "user")

        provider.shutdown()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "llm_judge"
        assert span.attributes["eval.scorer.name"] == "test_scorer"
        assert span.attributes["eval.scorer.score"] == 0.85
        assert span.status.status_code == StatusCode.OK

    def test_span_records_error_on_judge_model_error(self) -> None:
        exporter = _InMemoryExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        with patch(
            "luml.experiments.evaluation.scorers.builtin._base._tracer",
            provider.get_tracer(__name__),
        ):
            client = MagicMock(spec=LLMClient)
            client.complete.side_effect = ["bad", "also bad"]
            scorer = _StubUnsupervisedScorer.__new__(_StubUnsupervisedScorer)
            scorer._name = "failing"
            scorer._client = client

            with pytest.raises(JudgeModelError):
                _run_traced_judge(scorer, client, "sys", "user")

        provider.shutdown()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR
        events = span.events
        assert any(
            e.name == "exception"
            and "JudgeModelError" in str(e.attributes.get("exception.type", ""))
            for e in events
        )
