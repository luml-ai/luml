import importlib
from typing import Any, cast

from fnnx.variants.pyfunc import PyFunc
from langgraph.pregel import Pregel
from langgraph.types import Command


# copied from luml.utils.imports; template should not depend on luml sdk
def dyn_import(spec: str) -> Any:  # noqa: ANN401
    module_path, obj_name = spec.split("::", 1)
    module = importlib.import_module(module_path)
    return getattr(module, obj_name)


def normalize(obj):  # noqa: ANN001, ANN201
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj

    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}

    if isinstance(obj, list | tuple):
        return [normalize(x) for x in obj]

    import dataclasses

    if dataclasses.is_dataclass(obj):
        return normalize(dataclasses.asdict(obj))  # type: ignore

    try:
        from pydantic import BaseModel

        if isinstance(obj, BaseModel):
            return obj.model_dump()
    except ImportError:
        pass

    return repr(obj)


class LangGraphFunc(PyFunc):
    def warmup(self) -> None:
        graph_path = self.fnnx_context.get_value("graph_path")
        graph_creator_callable_path = self.fnnx_context.get_filepath(
            "graph_creator_callable.pkl"
        )

        if graph_path:
            self.graph: Pregel = cast(Pregel, dyn_import(graph_path))
        elif graph_creator_callable_path:
            import cloudpickle

            with open(graph_creator_callable_path, "rb") as f:
                graph_creator_callable = cloudpickle.load(f)
            self.graph: Pregel = graph_creator_callable()
        else:
            raise ValueError(
                "graph_path or graph_creator_callable.pkl not found in fnnx_context"
            )

        if not isinstance(self.graph, Pregel):
            raise TypeError("Restored object is not a Pregel instance")

    def _prepare_inputs(self, payload: dict) -> dict:
        graph_input = payload.get("graph_input")
        command = payload.get("command")
        context = payload.get("context")
        config = payload.get("config")
        if command is not None and graph_input is not None:
            raise ValueError("Provide either command or graph_input, not both.")
        arg = Command(**command) if command is not None else graph_input
        kwargs = {}
        if context is not None:
            kwargs["context"] = context
        if config is not None:
            kwargs["config"] = config
        return {"input": arg, **kwargs}

    def _prepare_outputs(self, outputs: dict) -> dict:
        if "__interrupt__" in outputs:
            interrupts = outputs.pop("__interrupt__")
            result = outputs
        else:
            interrupts = None
            result = outputs
        return {"result": result, "interrupts": interrupts}

    def _response(self, raw_output: dict) -> dict:
        return {"graph_output": self._prepare_outputs(normalize(raw_output))}  # type: ignore

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        kwargs = self._prepare_inputs(inputs["payload"])
        raw_output = self.graph.invoke(**kwargs)
        return self._response(raw_output)

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        kwargs = self._prepare_inputs(inputs["payload"])
        raw_output = await self.graph.ainvoke(**kwargs)
        return self._response(raw_output)
