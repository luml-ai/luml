import hashlib
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
from utils.logging import log_success

from .file_handler import FileHandler

logger = logging.getLogger(__name__)


class ModelHandler:
    def __init__(self, url: str | None = None) -> None:
        self._model_url = os.getenv("MODEL_ARTIFACT_URL") if url is None else url
        self._models_cache_dir = self._get_model_cache_dir()
        self._file_handler = FileHandler()
        self._request_model_schema = None
        self._response_model_schema = None
        self._model_envs = None
        self.conda_worker = None

        try:
            self.extracted_path = self._get_or_extract_model(self._model_url)
            self._model_envs = self._create_model_env()

            if self._model_envs:
                self.conda_worker = ModelCondaManager(
                    self._get_env_name(),
                    self._model_envs["manager"],
                    self.extracted_path,
                    self._get_model_data_for_worker(),
                )
                self.conda_worker.start()
        except Exception as error:
            logger.error(
                f"Model handler initialization failed: {error}\nTraceback: {traceback.format_exc()}"
            )
            raise

    @log_success("Model data for worker generated successfully.")
    def _get_model_data_for_worker(self) -> dict[str, Any]:
        return {
            "model_name": os.getenv("MODEL_NAME", ""),
            "manifest": self._get_manifest(),
            "dtypes_schemas": self._load_dtypes_schemas(),
            "model_path": self.extracted_path,
        }

    @staticmethod
    def _get_model_cache_dir() -> Path:
        models_cache_dir = Path("/app/models")
        models_cache_dir.mkdir(parents=True, exist_ok=True)
        return models_cache_dir

    @staticmethod
    def _generate_model_id(url: str) -> str:
        parsed_url = urlparse(url)
        url_path = parsed_url.path.split("?")[0]  # Remove query params
        return hashlib.md5(url_path.encode()).hexdigest()

    @log_success("Model downloaded successfully.")
    def _download_model(self, url: str) -> Path:
        temp_dir = tempfile.mkdtemp(prefix="dfs_model_download_")
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name.split("?")[0] or "model.dfs"
        model_archive_path = Path(temp_dir) / filename
        self._file_handler.download_file(url, model_archive_path)
        return model_archive_path

    @log_success("Model archive removed successfully.")
    def _clean_model_archive(self, file_path: Path) -> None:
        self._file_handler.remove_file(file_path)

    @log_success("Model unpacked successfully.")
    def _unpack_model_archive(self, model_archive_path: Path, extraction_dir: Path) -> str:
        return self._file_handler.unpack_tar_archive(model_archive_path, extraction_dir)

    @log_success("Unpacked Model path extracted successfully.")
    def _get_or_extract_model(self, url: str) -> str:
        model_id = self._generate_model_id(url)
        extraction_dir = self._models_cache_dir / model_id

        # if self._file_handler.dir_exist(extraction_dir):
        #     logger.info(f"Using cached model {model_id} from {extraction_dir}")
        #     return str(extraction_dir)
        #
        # logger.info("Model not in cache, downloading...")
        model_archive_path = self._download_model(url)

        extracted_path = self._unpack_model_archive(model_archive_path, extraction_dir)
        self._clean_model_archive(model_archive_path)

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

    def _get_env_name(self) -> str:
        if not self._model_envs:
            raise ValueError("Model environment not initialized")
        if self._model_envs.get("path"):
            return self._model_envs["path"].split("/")[-1]
        else:
            return self._model_envs["name"]

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
            for pkg_name in [
                "uvicorn",
            ]:
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
