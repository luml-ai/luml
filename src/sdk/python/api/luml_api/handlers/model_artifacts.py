import hashlib
import json
import os
import tarfile

from luml_api._types import ArtifactFileDetails


class ModelFileHandler:
    _tabular_producer_tags = [
        "dataforce.studio::tabular_classification:v1",
        "dataforce.studio::tabular_regression:v1",
    ]
    _tabular_metrics_tags = [
        "falcon.beastbyte.ai::tabular_classification_metrics:v1",
        "falcon.beastbyte.ai::tabular_regression_metrics:v1",
    ]
    _registry_metrics_tags = ["dataforce.studio::registry_metrics:v1"]

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self._manifest: dict = {}
        self._metadata: list[dict] = []
        self._file_index: dict[str, tuple[int, int]] = {}

    def artifact_details(self) -> ArtifactFileDetails:
        self._load_archive()
        return ArtifactFileDetails(
            file_name=os.path.basename(self._file_path),
            file_hash=self._compute_hash(),
            size=os.path.getsize(self._file_path),
            manifest=self._manifest,
            extra_values=self._extra_values(),
            file_index=self._file_index,
        )

    def _load_archive(self) -> None:
        """Read manifest, metadata and the file index in a single tar pass."""
        with tarfile.open(self._file_path, "r") as tar:
            self._file_index = {
                member.name: (member.offset_data, member.size)
                for member in tar.getmembers()
                if member.isfile()
            }

            manifest_file = tar.extractfile(tar.getmember("manifest.json"))
            self._manifest = (
                json.loads(manifest_file.read().decode("utf-8"))
                if manifest_file
                else {}
            )

            try:
                meta_file = tar.extractfile(tar.getmember("meta.json"))
                self._metadata = (
                    json.loads(meta_file.read().decode("utf-8")) if meta_file else []
                )
            except Exception:
                self._metadata = []

    def _compute_hash(self) -> str:
        hash_sha256 = hashlib.sha256()
        with open(self._file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8388608), b""):  # 8mb
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _payload_for_tags(self, tags: list[str]) -> dict | None:
        for meta_item in self._metadata:
            if isinstance(meta_item, dict) and any(
                tag in tags for tag in meta_item.get("producer_tags", [])
            ):
                return meta_item.get("payload", {})
        return None

    def _extra_values(self) -> dict:
        producer_tags = self._manifest.get("producer_tags", [])
        if any(tag in self._tabular_producer_tags for tag in producer_tags):
            payload = self._payload_for_tags(self._tabular_metrics_tags) or {}
            performance = (payload.get("metrics") or {}).get("performance")
            if performance:
                eval_metrics = performance.get("eval_holdout") or performance.get(
                    "eval_cv", {}
                )
                return {k: v for k, v in eval_metrics.items() if k != "N_SAMPLES"}

        custom_metrics = self._payload_for_tags(self._registry_metrics_tags)
        if custom_metrics:
            return custom_metrics.get("metrics", {})

        return {}
