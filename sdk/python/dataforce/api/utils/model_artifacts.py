import hashlib
import json
import os
import tarfile

from dataforce.api._types import ModelDetails


class ModelFileHandler:
    _tabular_producer_tags = [
        "dataforce.studio::tabular_classification:v1",
        "dataforce.studio::tabular_regression:v1",
    ]
    _tabular_tags = [
        "falcon.beastbyte.ai::tabular_classification_metrics:v1",
        "falcon.beastbyte.ai::tabular_regression_metrics:v1",
    ]

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self._metadata: list[dict] | None = None
        self._manifest: dict | None = None

    def _get_type_tag(self, producer_tags: list[str]) -> str | None:
        for tag in producer_tags:
            if tag in self._tabular_producer_tags:
                return tag
        return None

    def _get_metadata_by_tag(self, available_tags: list[str]) -> dict | None:
        metadata = self.get_metadata()

        for meta_item in metadata:
            if isinstance(meta_item, dict) and "producer_tags" in meta_item:
                producer_tags = meta_item["producer_tags"]
                for tag in producer_tags:
                    if tag in available_tags:
                        return meta_item.get("payload", {})
        return None

    def _get_tabular_metadata(self) -> dict | None:
        result = self._get_metadata_by_tag(self._tabular_tags)
        return result.get("metrics") if result else None

    def get_file_name(self) -> str:
        return os.path.basename(self._file_path)

    def get_size(self) -> int:
        return os.path.getsize(self._file_path)

    def get_file_hash(self) -> str:
        hash_sha256 = hashlib.sha256()
        with open(self._file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8388608), b""):  # 8mb
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def get_metadata(self) -> list[dict]:
        if self._metadata is None:
            try:
                with tarfile.open(self._file_path, "r") as tar:
                    meta_file = tar.extractfile(tar.getmember("meta.json"))
                    self._metadata = (
                        json.loads(meta_file.read().decode("utf-8"))
                        if meta_file
                        else []
                    )
            except (Exception, KeyError):
                self._metadata = []
        return self._metadata

    def get_metrics(self) -> dict:
        manifest = self.get_manifest()
        type_tag = self._get_type_tag(manifest.get("producer_tags", []))

        if type_tag:
            tabular_metrics = self._get_tabular_metadata()
            if tabular_metrics and "performance" in tabular_metrics:
                performance = tabular_metrics["performance"]
                eval_metrics = performance.get("eval_holdout") or performance.get(
                    "eval_cv", {}
                )

                return {k: v for k, v in eval_metrics.items() if k != "N_SAMPLES"}

        custom_metrics = self._get_metadata_by_tag(
            ["dataforce.studio::registry_metrics:v1"]
        )
        if custom_metrics:
            return custom_metrics.get("metrics", {})

        return {}

    def get_manifest(self) -> dict:
        if self._manifest is None:
            with tarfile.open(self._file_path, "r") as tar:
                manifest_file = tar.extractfile(tar.getmember("manifest.json"))
                self._manifest = (
                    json.loads(manifest_file.read().decode("utf-8"))
                    if manifest_file
                    else {}
                )
        return self._manifest

    def get_file_index(self) -> dict[str, tuple[int, int]]:
        file_index = {}
        with tarfile.open(self._file_path, "r") as tar:
            for member in tar.getmembers():
                if member.isfile():
                    file_index[member.name] = (member.offset_data, member.size)
        return file_index

    def model_details(self) -> ModelDetails:
        return ModelDetails(
            file_name=self.get_file_name(),
            file_hash=self.get_file_hash(),
            size=self.get_size(),
            manifest=self.get_manifest(),
            metrics=self.get_metrics(),
            file_index=self.get_file_index(),
        )
