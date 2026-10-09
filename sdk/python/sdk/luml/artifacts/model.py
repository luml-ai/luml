from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING, Any

from luml._constants import FNNX_PRODUCER_NAME

if TYPE_CHECKING:
    from fnnx.extras.reader import Reader  # type: ignore[import-untyped]

    from luml.utils.reference_profile import TaskType

from luml.artifacts._base import (
    DiskReference,
    FileMap,
    MemoryFile,
)
from luml.card.builder import CardBuilder

LLM_KIND_TAG_PREFIX = FNNX_PRODUCER_NAME + "::kind_llm:"
SKLEARN_TAG_PREFIX = FNNX_PRODUCER_NAME + "::sklearn:"
TABULAR_KIND_TAG = FNNX_PRODUCER_NAME + "::kind_tabular:v1"
KIND_TAG_PREFIX = FNNX_PRODUCER_NAME + "::kind_"


class ModelReference(DiskReference):
    def validate(self) -> bool:
        try:
            self.read()
            return True
        except Exception as e:
            print(f"Validation failed: {e}")  # noqa: T201
            return False

    def add_model_card(self, html_content: str | CardBuilder) -> None:
        if not isinstance(html_content, str):
            if isinstance(html_content, CardBuilder):
                html_content = html_content.build()
            else:
                msg = "html_content must be a string or CardBuilder instance"
                raise TypeError(msg)

        tag = "dataforce.studio::model_card:v1"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(
            zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            zip_file.writestr("index.html", html_content)

        zip_buffer.seek(0)
        file = MemoryFile(zip_buffer.read())

        self._append_metadata(
            idx=None,
            tags=[tag],
            payload={},
            prefix=tag,
            data=[FileMap(file=file, remote_path="model_card.zip")],
        )

    def add_reference_profile(
        self,
        reference_data: Any,  # noqa: ANN401
        *,
        horizons: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build and embed a monitoring profile in a local sklearn artifact."""
        manifest = self.get_manifest()
        producer_tags = manifest.get("producer_tags")
        if not isinstance(producer_tags, list) or not all(
            isinstance(tag, str) for tag in producer_tags
        ):
            raise ValueError("Artifact manifest has invalid producer_tags")
        if any(tag.startswith(LLM_KIND_TAG_PREFIX) for tag in producer_tags):
            raise ValueError(
                "Cannot add a tabular reference profile to an LLM artifact"
            )
        if not any(tag.startswith(SKLEARN_TAG_PREFIX) for tag in producer_tags):
            raise ValueError(
                "Reference profiles can only be built for sklearn artifacts"
            )

        import cloudpickle  # type: ignore[import-untyped]
        from sklearn.base import is_classifier  # type: ignore[import-untyped]

        from luml.utils.packaging import TABULAR_MONITORING_TAG, add_reference_profile

        estimator = cloudpickle.loads(
            self.extract_file("variant_artifacts/extra_files/estimator.pkl")
        )
        predict = getattr(estimator, "predict", None)
        if not callable(predict):
            raise ValueError(
                "The bundled sklearn estimator does not implement predict()"
            )

        classifier = is_classifier(estimator)
        task_type: TaskType
        if horizons is not None:
            task_type = "forecasting"
        else:
            task_type = "classification" if classifier else "regression"
        predict_proba = (
            estimator.predict_proba
            if classifier and callable(getattr(estimator, "predict_proba", None))
            else None
        )
        class_names = (
            [str(name) for name in estimator.classes_]
            if classifier and hasattr(estimator, "classes_")
            else None
        )
        tags_to_add = [TABULAR_MONITORING_TAG]
        if not any(tag.startswith(KIND_TAG_PREFIX) for tag in producer_tags):
            tags_to_add.insert(0, TABULAR_KIND_TAG)

        return add_reference_profile(
            self.path,
            reference_data,
            task_type,
            predict,
            predict_proba=predict_proba,
            output_names=list(horizons) if horizons is not None else ["y"],
            class_names=class_names,
            horizons=list(horizons) if horizons is not None else None,
            additional_producer_tags=tags_to_add,
        )

    def read(self) -> Reader:
        from fnnx.extras.reader import Reader

        return Reader(self.path)
