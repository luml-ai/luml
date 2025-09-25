from __future__ import annotations

import asyncio
import json
import numpy as np
import tempfile
import os
from typing import Any, Mapping, Sequence

from fnnx.device import DeviceMap
from fnnx.handlers.local import LocalHandlerConfig
from fnnx.runtime import Runtime
from dfs_webworker.store import Store
from dfs_webworker.utils import success


JsonLike = Mapping[str, Any] | Sequence[Any] | None


class FnnxPyFunc:
    def __init__(self, model_path: str, accelerator: str = "cpu", auto_cleanup: bool = False):
        self.model_path = model_path
        self.accelerator = accelerator
        self.auto_cleanup = auto_cleanup
        self._runtime: Runtime | None = None

    def _ensure_runtime(self) -> Runtime:
        if self._runtime is None:
            self._runtime = Runtime(
                bundle_path=self.model_path,
                device_map=DeviceMap(accelerator=self.accelerator, node_device_map={}),
                handler_config=LocalHandlerConfig(auto_cleanup=self.auto_cleanup),
            )
        return self._runtime


    def compute(self, inputs: JsonLike, dynamic_attributes: JsonLike) -> Any:
        runtime = self._ensure_runtime()
        try:
            return asyncio.run(runtime.compute_async(inputs or {}, dynamic_attributes or {}))
        except NotImplementedError:
            return runtime.compute(inputs or {}, dynamic_attributes or {})

    def __call__(self, payload: JsonLike) -> Any:
        return self.compute(payload, dynamic_attributes=None)

    @property
    def runtime(self) -> Runtime:
        return self._ensure_runtime()


def _to_jsonable(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if hasattr(obj, 'item'):  # numpy scalars
        return obj.item()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, tuple):
        return [_to_jsonable(v) for v in obj]
    return obj


def pyfunc_init(model: bytes):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pyfnx') as temp_file:
            temp_file.write(model)
            temp_path = temp_file.name

        model_id = Store.save(FnnxPyFunc(model_path=temp_path))
        return success(model_id=model_id)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize pyfunc model: {str(e)}")


def pyfunc_compute(model_id: str, inputs: dict, dynattrs: str = "{}") -> dict:
    try:
        fnnx_pyfunc = Store.get(model_id)

        dynamic_attributes = json.loads(dynattrs) if dynattrs else {}
        outputs = fnnx_pyfunc.compute(inputs, dynamic_attributes)

        serialized_outputs = _to_jsonable(outputs)
        return success(predictions=serialized_outputs)
    except KeyError:
        raise ValueError(f"Model with ID {model_id} not found")
    except Exception as e:
        raise RuntimeError(f"Failed to compute predictions: {str(e)}")


def pyfunc_deinit(model_id: str) -> Any | None:
    try:
        fnnx_pyfunc = Store.get(model_id)
        if hasattr(fnnx_pyfunc, 'model_path') and os.path.exists(fnnx_pyfunc.model_path):
            os.remove(fnnx_pyfunc.model_path)
        Store.delete(model_id)
        return success()
    except KeyError:
        print(f"Model with ID {model_id} not found")
        pass
    except Exception as e:
        raise RuntimeError(f"Failed to deinitialize model: {str(e)}")

