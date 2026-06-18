from luml.llm import LLMError


class ScorerError(Exception):
    """Base class for errors raised by built-in scorers."""


class JudgeModelError(LLMError):
    """Raised when the judge LLM fails to produce valid JSON with a numeric score."""


class MissingExpectedOutputError(ScorerError):
    """Raised when a supervised scorer is run without an ``expected_output``.

    Supervised scorers (e.g. ``Correctness``) compare the model response
    against a reference; an empty or missing ``expected_output`` makes the
    comparison meaningless, so we fail fast instead of asking the judge to
    score against nothing.
    """
