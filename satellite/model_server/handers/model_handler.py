import json
import os
import logging
import asyncio
from pathlib import Path
from typing import Any, Union
from urllib.parse import urlparse
import tempfile
from fnnx.handlers._common import unpack_model
from fnnx.runtime import Runtime
from pydantic import Field, create_model
from fnnx.device import DeviceMap
from fnnx.handlers.local import LocalHandlerConfig

# from fnnx.envs.conda import install_micromamba, CondaLikeEnvManager
from .conda_custom import install_micromamba, CondaLikeEnvManager
from .conda_worker import ComputeWorker
from .file_handler import FileHandler

logger = logging.getLogger(__name__)

try:
    import numpy as _np  # optional

    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False


class ModelHandler:
    def __init__(self, url: str | None = None):
        self._model_url = (
            os.getenv("MODEL_ARTIFACT_URL") or os.getenv("MODEL_ARTIFACT_PATH", "")
            if url is None
            else url
        )
        self._file_handler = FileHandler()
        self._cached_models = {}  # url -> local_path mapping
        self._request_model_schema = None
        self._model_envs = None
        self._conda_worker = None
        try:
            self.model_path = self.get_model_path()
            self.extracted_path = self.unpacked_model_path()
            self._model_envs = self.create_model_env()

            if self._model_envs:
                self._conda_worker = ComputeWorker(self._model_envs, self.extracted_path)
                self._conda_worker.start()
            else:
                logger.warning("No model envs created, skipping worker startup")
        except Exception as e:
            logger.error(str(e))
            self.model_path = None

    def _download_model(self, url: str) -> str:
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name or "model.dfs"

        temp_dir = tempfile.mkdtemp(prefix="dfs_model_")
        local_path = Path(temp_dir) / filename

        return self._file_handler.download_file(url, str(local_path))

    def get_model_path(self) -> str:
        if not self._model_url:
            raise ValueError(
                "Model URL is empty! Set MODEL_ARTIFACT_PATH or MODEL_ARTIFACT_URL environment variable"
            )

        if not self._model_url.startswith(("http://", "https://")):
            if not Path(self._model_url).exists():
                raise FileNotFoundError(f"Local model file does not exist: {self._model_url}")
            return self._model_url

        if self._model_url in self._cached_models:
            cached_path = self._cached_models[self._model_url]
            if Path(cached_path).exists():
                return cached_path

        local_path = self._download_model(self._model_url)

        self._cached_models[self._model_url] = local_path

        return local_path

    @staticmethod
    def get_base_type(dtype_inner: str):
        return {
            "string": str,
            "integer": int,
            "float": float,
            "float32": float,
            "float64": float,
            "int": int,
            "int32": int,
            "int64": int,
            "boolean": bool,
        }.get(dtype_inner, Any)

    def to_jsonable(self, obj):
        if _HAS_NUMPY:
            if isinstance(obj, _np.ndarray):
                return obj.tolist()
            if isinstance(obj, _np.generic):
                return obj.item()
        if isinstance(obj, dict):
            return {k: self.to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.to_jsonable(v) for v in obj]
        if isinstance(obj, tuple):
            return [self.to_jsonable(v) for v in obj]
        return obj

    @staticmethod
    def create_nested_list_type(base_type, shape):
        for _ in range(len(shape)):
            base_type = list[base_type]
        return base_type

    def get_field_type(
        self, content_type: str, dtype: str, shape: list[Union[int, str]] | None = None
    ):
        if content_type == "NDJSON":
            if dtype.startswith("Array["):
                inner = dtype[6:-1]
                base_type = self.get_base_type(inner)
            elif dtype.startswith("NDContainer["):
                inner = dtype[12:-1]
                base_type = dict[str, Any]
            else:
                raise ValueError(f"Unsupported dtype for NDJSON: {dtype}")

            if shape:
                return self.create_nested_list_type(base_type, shape)
            else:
                return list[base_type]

        elif content_type == "JSON":
            return dict[str, Any]

        return Any

    def create_input_model(self, manifest: dict):
        fields = {}

        for input_spec in manifest["inputs"]:
            name = input_spec["name"]
            dtype = input_spec["dtype"]
            content_type = input_spec["content_type"]
            field_type = self.get_field_type(
                content_type, dtype, shape=input_spec.get("shape", None)
            )

            description = input_spec.get("description", f"Input field of type {dtype}")

            fields[name] = (field_type, Field(..., description=description))
        return create_model("InputsModel", **fields)

    @staticmethod
    def create_dynamic_attributes_model(manifest: dict):
        fields = {}
        for attr in manifest.get("dynamic_attributes", []):
            name = attr["name"]
            desc = attr.get("description", f"Dynamic attribute '{name}'")
            fields[name] = (str | None, Field(default=f"<<<{name}>>>", description=desc))
        return create_model("DynamicAttributesModel", **fields)

    def unpacked_model_path(self):
        if self.model_path is None:
            raise ValueError("Model not available - failed to download")
        extracted_path, *_ = unpack_model(self.model_path)
        return extracted_path

    def get_manifest(self):
        manifest_path = Path(self.unpacked_model_path()) / "manifest.json"
        with open(manifest_path) as f:
            return json.load(f)

    def get_env(self):
        env_path = Path(self.unpacked_model_path()) / "env.json"
        with open(env_path) as f:
            return json.load(f)

    def load_dtypes_schemas(self) -> dict[str, Any]:
        dtypes_path = Path(self.unpacked_model_path()) / "dtypes.json"
        if dtypes_path.exists():
            with open(dtypes_path) as f:
                return json.load(f)
        return {}

    def get_request_model(self):
        if self._request_model_schema is None:
            manifest = self.get_manifest()
            input_model = self.create_input_model(manifest)
            dynamic_attrs_model = self.create_dynamic_attributes_model(manifest)

            self._request_model_schema = create_model(
                "ComputeRequest",
                inputs=(input_model, Field(..., description="Input data for the model")),
                dynamic_attributes=(
                    dynamic_attrs_model,
                    Field(..., description="Dynamic attributes"),
                ),
            )
        return self._request_model_schema

    async def compute_result(self, inputs, dynamic_attributes):
        if self._conda_worker and self._conda_worker.is_alive():
            return await self._conda_worker.compute(
                inputs.model_dump(), dynamic_attributes.model_dump()
            )
        else:
            handler = Runtime(
                bundle_path=self.extracted_path,
                device_map=DeviceMap(accelerator="cpu", node_device_map={}),
                handler_config=LocalHandlerConfig(auto_cleanup=False),
            )
            try:
                result = await handler.compute_async(
                    inputs.model_dump(), dynamic_attributes.model_dump()
                )
            except NotImplementedError:
                result = await asyncio.to_thread(
                    handler.compute, inputs.model_dump(), dynamic_attributes.model_dump()
                )
            return self.to_jsonable(result)

    def create_model_env(self):
        try:
            env_spec = self.get_env()
            if not env_spec:
                return None

            install_micromamba()

            env_name, env_config = next(iter(env_spec.items()))

            if "dependencies" not in env_config:
                env_config["dependencies"] = []

            existing_packages = set()
            for dep in env_config["dependencies"]:
                if isinstance(dep, dict) and "package" in dep:
                    existing_packages.add(
                        dep["package"].split("==")[0].split(">=")[0].split("<=")[0].strip()
                    )

            for pkg_name in ["uvicorn"]:
                if pkg_name not in existing_packages:
                    env_config["dependencies"].append({"package": pkg_name})

            env_manager = CondaLikeEnvManager(env_config)
            env_path = env_manager.ensure()

            return {"name": env_name, "path": env_path, "manager": env_manager}

        except Exception as e:
            logger.error(f"Failed to create model environment: {e}")
            return None
