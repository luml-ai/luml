from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class BaseScorer(ABC):
    @abstractmethod
    def get_name(self) -> str:
        pass

    def __repr__(self) -> str:
        return f"Scorer[{self.get_name()}]"


class UnsupervisedScorer(BaseScorer):
    @abstractmethod
    def score(
        self, inputs: dict[str, Any], output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        pass


class SupervisedScorer(BaseScorer):
    @abstractmethod
    def score(
        self, inputs: dict[str, Any], expected_output: Any, output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        pass


class UnsupervisedFuncScorer(UnsupervisedScorer):
    def __init__(self, name: str, score_fn: Callable) -> None:
        self.name = name
        self.score_fn = score_fn

    def score(
        self, inputs: dict[str, Any], output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        return self.score_fn(inputs, output)

    def get_name(self) -> str:
        return self.name


class SupervisedFuncScorer(SupervisedScorer):
    def __init__(self, name: str, score_fn: Callable) -> None:
        self.name = name
        self.score_fn = score_fn

    def score(
        self, inputs: dict[str, Any], expected_output: Any, output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        return self.score_fn(inputs, expected_output, output)

    def get_name(self) -> str:
        return self.name


def unsupervised_scorer(fn: Callable) -> UnsupervisedFuncScorer:
    name: str = getattr(fn, "__name__", "unnamed_scorer")
    return UnsupervisedFuncScorer(name=name, score_fn=fn)


def supervised_scorer(fn: Callable) -> SupervisedFuncScorer:
    name: str = getattr(fn, "__name__", "unnamed_scorer")
    return SupervisedFuncScorer(name=name, score_fn=fn)
