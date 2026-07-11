from typing import Any, Literal

from fnnx.envs.uv import UvEnvManager
from fnnx.handlers.stdio import StdIOHandler, StdIOHandlerConfig
from fnnx.runtime import Runtime

from tests.integrations._types import PackagingFixture

HANDLER_CONFIG = StdIOHandlerConfig(env_manager=UvEnvManager)


def _run(path: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return Runtime(path, handler=StdIOHandler, handler_config=HANDLER_CONFIG).compute(
        inputs, dynamic_attributes={}
    )


def _get_preds(out: dict[str, Any], preds_key: list[str]) -> Any:  # noqa: ANN401
    result: Any = out
    for key in preds_key:
        result = result[key]
    return result


def _assert_preds(
    preds: Any,  # noqa: ANN401
    expected: list[Any],  # noqa: ANN401
    compare: Literal["float", "int", "float_2d"],
    atol: float = 1e-5,
) -> None:
    assert len(preds) == len(expected)
    if compare == "int":
        assert [int(p) for p in preds] == expected
    elif compare == "float":
        assert all(abs(p - e) < atol for p, e in zip(preds, expected, strict=False))
    elif compare == "float_2d":
        assert all(
            abs(p - e) < atol
            for row_p, row_e in zip(preds, expected, strict=False)
            for p, e in zip(row_p, row_e, strict=False)
        )


def _assert_fixture(f: PackagingFixture) -> None:
    _assert_preds(
        _get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]),
        f["expected"],
        f["compare"],
    )
