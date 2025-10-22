import json
import logging
import os
import tempfile
import traceback
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from conda_manager import ModelCondaManager
from fnnx.envs.conda import CondaLikeEnvManager, install_micromamba
from fnnx.handlers._common import unpack_model
from pydantic import BaseModel, Field, create_model
from utils.logging import log_success

from .file_handler import FileHandler

logger = logging.getLogger(__name__)


class ModelHandler:
    def __init__(self, url: str | None = None) -> None:
        self._model_url = os.getenv("MODEL_ARTIFACT_URL") if url is None else url
        self._file_handler = FileHandler()
        self._cached_models = {}  # url -> local_path mapping
        self._request_model_schema = None
        self.model_envs = None
        self.conda_worker = None

        try:
            self.model_path = self._get_model_path()
            self.extracted_path = self._unpacked_model_path()
            self._remove_model_archive()
            self.model_envs = self._create_model_env()

            if self.model_envs:
                model_data = {
                    "manifest": self._get_manifest(),
                    "dtypes_schemas": self._load_dtypes_schemas(),
                    "request_schema": self._get_request_model(),
                    "model_path": self.extracted_path,
                }

                self.conda_worker = ModelCondaManager(
                    self._get_env_name(),
                    self.model_envs["manager"],
                    self.extracted_path,
                    model_data,
                )
                self.conda_worker.start()
        except Exception as error:
            logger.error(
                f"Model handler initialization failed: {error}\nTraceback: {traceback.format_exc()}"
            )
            self._file_handler.remove_file(self.model_path)
            self.model_path = None

    def _download_model(self, url: str) -> str:
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name or "model.dfs"

        temp_dir = tempfile.mkdtemp(prefix="dfs_model_")
        local_path = Path(temp_dir) / filename

        return self._file_handler.download_file(url, str(local_path))

    def _get_model_path(self) -> str:
        if not self._model_url:
            raise ValueError("Model URL is empty!")

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

    @log_success("Model archive removed successfully.")
    def _remove_model_archive(self) -> None:
        self._file_handler.remove_file(self.model_path)

    @staticmethod
    def _get_base_type(dtype_inner: str) -> type:
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

    @staticmethod
    def _create_nested_list_type(base_type: type, shape: list[int | str]) -> type:
        for _ in range(len(shape)):
            base_type = list[base_type]
        return base_type

    def _get_field_type(
        self, content_type: str, dtype: str, shape: list[int | str] | None = None
    ) -> type:
        if content_type == "NDJSON":
            if dtype.startswith("Array["):
                inner = dtype[6:-1]
                base_type = self._get_base_type(inner)
            elif dtype.startswith("NDContainer["):
                inner = dtype[12:-1]
                base_type = dict[str, Any]
            else:
                raise ValueError(f"Unsupported dtype for NDJSON: {dtype}")

            if shape:
                return self._create_nested_list_type(base_type, shape)
            else:
                return list[base_type]

        elif content_type == "JSON":
            return dict[str, Any]

        return Any

    def _create_input_model(self, manifest: dict) -> type[BaseModel]:
        fields = {}

        for input_spec in manifest["inputs"]:
            name = input_spec["name"]
            dtype = input_spec["dtype"]
            content_type = input_spec["content_type"]
            field_type = self._get_field_type(
                content_type, dtype, shape=input_spec.get("shape", None)
            )

            description = input_spec.get("description", f"Input field of type {dtype}")

            fields[name] = (field_type, Field(..., description=description))
        return create_model("InputsModel", **fields)

    @staticmethod
    def _create_dynamic_attributes_model(manifest: dict) -> type[BaseModel]:
        fields = {}
        for attr in manifest.get("dynamic_attributes", []):
            name = attr["name"]
            desc = attr.get("description", f"Dynamic attribute '{name}'")
            fields[name] = (str | None, Field(default=f"<<<{name}>>>", description=desc))
        return create_model("DynamicAttributesModel", **fields)

    @log_success("Model unpacked successfully.")
    def _unpacked_model_path(self) -> str:
        if self.model_path is None:
            raise ValueError("Model not available - failed to download")
        extracted_path, *_ = unpack_model(self.model_path)
        return extracted_path

    @log_success("Model manifest.json loaded successfully.")
    def _get_manifest(self) -> dict[str, Any]:
        manifest_path = Path(self.extracted_path) / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                return json.load(f)
        return {}

    def _get_env(self) -> dict[str, Any] | None:
        env_path = Path(self.extracted_path) / "env.json"
        if env_path.exists():
            with open(env_path) as f:
                return json.load(f)
        return None

    @log_success("Model dtypes.json loaded successfully.")
    def _load_dtypes_schemas(self) -> dict[str, Any]:
        dtypes_path = Path(self.extracted_path) / "dtypes.json"
        if dtypes_path.exists():
            with open(dtypes_path) as f:
                return json.load(f)
        return {}

    @log_success("Request Model generated successfully.")
    def _get_request_model(self) -> dict[str, Any]:
        if self._request_model_schema is None:
            manifest = self._get_manifest()
            input_model = self._create_input_model(manifest)
            dynamic_attrs_model = self._create_dynamic_attributes_model(manifest)

            self._request_model_schema = create_model(
                "ComputeRequest",
                inputs=(input_model, Field(..., description="Input data for the model")),
                dynamic_attributes=(
                    dynamic_attrs_model,
                    Field(..., description="Dynamic attributes"),
                ),
            )
        return self._request_model_schema.model_json_schema()

    def _get_env_name(self) -> str:
        if self.model_envs["path"]:
            return self.model_envs["path"].split("/")[-1]
        else:
            return self.model_envs["name"]

    @staticmethod
    def _get_default_env_spec() -> dict[str, Any]:
        return {
            "python3::conda_pip": {
                "python_version": "3.12.6",
                "build_dependencies": [],
                "dependencies": [
                    {
                        "package": f"uvicorn=={importlib_metadata.version('uvicorn')}",
                        "extra_pip_args": None,
                        "condition": None,
                    },
                    {
                        "package": f"fnnx[core]=={importlib_metadata.version('fnnx')}",
                        "extra_pip_args": None,
                        "condition": None,
                    },
                ],
            }
        }

    @log_success("Model env created successfully.")
    def _create_model_env(self) -> dict[str, Any] | None:
        env_spec = self._get_env()
        if not env_spec:
            env_spec = self._get_default_env_spec()

        try:
            install_micromamba()
            env_type, env_config = next(iter(env_spec.items()))

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
                    version = importlib_metadata.version(pkg_name)
                    env_config["dependencies"].append({"package": f"{pkg_name}=={version}"})

            env_manager = CondaLikeEnvManager(env_config)
            env_path = env_manager.ensure()
            env_name = f"fnnx-{env_manager.env_id}"

            return {"name": env_name, "path": env_path, "manager": env_manager}

        except Exception as e:
            logger.error(
                f"[CREATE_ENV] Failed to create model environment: {e}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            return None
