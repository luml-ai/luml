from typing import Any, Literal, TypedDict

from luml.artifacts.model import ModelReference


class PackagingFixture(TypedDict):
    ref: ModelReference
    inputs: dict[str, Any]  # noqa: ANN401
    expected: list[Any]  # noqa: ANN401
    preds_key: list[str]
    compare: Literal["float", "int", "float_2d"]
