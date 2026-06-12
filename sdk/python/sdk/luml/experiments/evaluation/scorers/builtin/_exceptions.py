from luml.llm import LLMError


class JudgeModelError(LLMError):
    """Raised when the judge LLM fails to produce valid JSON with a numeric score."""
