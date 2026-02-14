import asyncio
from abc import ABC, abstractmethod
import json
from promptopt.llm import LLM
from promptopt.dataclasses import Field, JsonModel

METRIC_MODEL = JsonModel([Field("score", "integer")])

METRIC_PROMPT_TEMPLATE = """
You are evaluating the performance of an AI system based on a given prediction and true value.
You task is to score the prediction on a scale from 1 to 5, where 1 is the worst and 5 is the best.
The quality of the prediction is determined by the following user-defined criterion: ```{criterion}```
The prediction and the true value are represented as JSON objects.
Prediction: {prediction}
True value: {true_value}
Your answer should be a JSON object with a single field "score" containing the score from 1 to 5 (integer).
"""


class BaseMetric(ABC):
    @abstractmethod
    async def score(
        self, predictions: list[dict], targets: list[dict], **kwargs
    ) -> float:
        pass


class ExactMatch(BaseMetric):
    async def score(
        self, predictions: list[dict], targets: list[dict], **kwargs
    ) -> float:
        if len(predictions) != len(targets):
            raise ValueError("Prediction and target lists must have the same length.")

        exact_matches = [
            1 if pred == tgt else 0 for pred, tgt in zip(predictions, targets)
        ]
        return sum(exact_matches) / len(exact_matches)


class LLMJudge(BaseMetric):
    def __init__(self, criterion: str):
        self.criterion = criterion

    async def score(
        self, predictions: list[dict], targets: list[dict], llm: LLM, **kwargs
    ) -> float:
        if len(predictions) != len(targets):
            raise ValueError("Prediction and target lists must have the same length.")

        async def get_score(pred, tgt):
            template = METRIC_PROMPT_TEMPLATE.format(
                criterion=self.criterion,
                prediction=json.dumps(pred),
                true_value=json.dumps(tgt),
            )
            messages = [{"role": "user", "content": template}]
            return json.loads(await llm.generate(messages, out_schema=METRIC_MODEL))[
                "score"
            ]

        scores = await asyncio.gather(
            *[get_score(pred, tgt) for pred, tgt in zip(predictions, targets)]
        )

        return sum(scores) / len(scores)
