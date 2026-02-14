import importlib
import uuid
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, Literal

from luml.artifacts._base import DiskFile, FileMap
from luml.artifacts.model import ModelReference
from luml.experiments.backends import Backend, BackendRegistry
from luml.experiments.backends._data_types import (
    Experiment,
    ExperimentData,
    Group,
    Model,
)

if TYPE_CHECKING:
    from luml.artifacts.experiment import ExperimentReference

_FLAVOR_REGISTRY: dict[str, tuple[str, str]] = {
    "sklearn": ("luml.integrations.sklearn.packaging", "save_sklearn"),
    "xgboost": ("luml.integrations.xgboost.packaging", "save_xgboost"),
    "lightgbm": ("luml.integrations.lightgbm.packaging", "save_lightgbm"),
    "catboost": ("luml.integrations.catboost.packaging", "save_catboost"),
    "langgraph": ("luml.integrations.langgraph.packaging", "save_langgraph"),
}

_MODULE_PREFIX_TO_FLAVOR: dict[str, str] = {
    "sklearn": "sklearn",
    "xgboost": "xgboost",
    "lightgbm": "lightgbm",
    "catboost": "catboost",
    "langgraph": "langgraph",
}


class ExperimentTracker:
    """
    Local experiment tracking for ML experiments.

    Tracks metrics, parameters, artifacts, and traces for machine learning experiments.
    Supports multiple backend storage options via connection strings.

    Args:
        connection_string: Backend connection string. Format: 'backend://config'.
            Default is 'sqlite://./experiments' for local SQLite storage.

    Example:
    ```python
    tracker = ExperimentTracker("sqlite://./my_experiments")
    exp_id = tracker.start_experiment(
        name="my_experiment", group="my_group", tags=["baseline"]
    )
    tracker.log_static("learning_rate", 0.001)
    tracker.log_dynamic("loss", 0.5, step=1)
    tracker.end_experiment(exp_id)
    ```
    """

    def __init__(self, connection_string: str = "sqlite://./experiments") -> None:
        self.backend = self._parse_connection_string(connection_string)
        self.current_experiment_id: str | None = None

    @staticmethod
    def _parse_connection_string(connection_string: str) -> Backend:
        if "://" not in connection_string:
            raise ValueError("Invalid connection string format. Use 'backend://config'")

        backend_type, config = connection_string.split("://", 1)

        return BackendRegistry.get_backend(backend_type)(config)

    def start_experiment(
        self,
        name: str | None = None,
        group: str = "default",
        experiment_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Starts a new experiment by initializing it with the backend and setting
        the experiment's metadata.

        Args:
            name (str | None): The name of the experiment. If not provided,
                the experiment will be initialized without a specific name
            group (str): The group to which the experiment belongs. Defaults to
                "default".
            experiment_id (str | None): A unique identifier for the experiment. If not
                provided, a new UUID will be generated as the experiment ID.
            tags (list[str] | None): A list of tags to associate with the experiment.
                Can be None if no tags are necessary.

        Returns:
            str: The unique identifier of the started experiment.
        """
        if experiment_id is None:
            experiment_id = str(uuid.uuid4())

        self.backend.initialize_experiment(experiment_id, group, name, tags)
        self.current_experiment_id = experiment_id
        return experiment_id

    def end_experiment(self, experiment_id: str | None = None) -> None:
        """
        End an active experiment tracking session.

        Args:
            experiment_id: ID of experiment to end.
            Uses current experiment if not specified.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment(name="my_exp")
        tracker.end_experiment(exp_id)
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment to end.")

        self.backend.end_experiment(exp_id)

        if exp_id == self.current_experiment_id:
            self.current_experiment_id = None

    def log_static(
        self,
        key: str,
        value: Any,  # noqa: ANN401
        experiment_id: str | None = None,
    ) -> None:
        """
        Log static parameters or metadata (values that don't change during training).

        Args:
            key: Parameter name.
            value: Parameter value (can be any serializable type).
            experiment_id: Experiment ID. Uses current experiment if not specified.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        tracker.log_static("learning_rate", 0.001)
        tracker.log_static("model_architecture", "resnet50")
        tracker.log_static("batch_size", 32)
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_static(exp_id, key, value)

    def log_dynamic(
        self,
        key: str,
        value: int | float,
        step: int | None = None,
        experiment_id: str | None = None,
    ) -> None:
        """
        Log time-series metrics (values that change during training).

        Args:
            key: Metric name.
            value: Metric value (numeric).
            step: Training step/epoch number.
            experiment_id: Experiment ID. Uses current experiment if not specified.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        for epoch in range(10):
            loss = train_epoch()
            tracker.log_dynamic("train_loss", loss, step=epoch)
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_dynamic(exp_id, key, value, step)

    def log_span(
        self,
        trace_id: str,
        span_id: str,
        name: str,
        start_time_unix_nano: int,
        end_time_unix_nano: int,
        parent_span_id: str | None = None,
        kind: int = 0,
        status_code: int = 0,
        status_message: str | None = None,
        attributes: dict[str, Any] | None = None,  # noqa: ANN401
        events: list[dict[str, Any]] | None = None,  # noqa: ANN401
        links: list[dict[str, Any]] | None = None,  # noqa: ANN401
        trace_flags: int = 0,
        experiment_id: str | None = None,
    ) -> None:
        """
        Log an OpenTelemetry-compatible span to the experiment.

        Records a single span representing a unit of work within a trace.
        Spans can be nested via ``parent_span_id`` to form a trace tree.

        Args:
            trace_id (str): Unique identifier for the trace this span belongs to.
            span_id (str): Unique identifier for this span.
            name (str): Human-readable name describing the operation.
            start_time_unix_nano (int): Span start time in nanoseconds since Unix epoch.
            end_time_unix_nano (int): Span end time in nanoseconds since Unix epoch.
            parent_span_id (str | None): Span ID of the parent span, or ``None`` for
                root spans.
            kind (int): Span kind following the OpenTelemetry spec (0=INTERNAL,
                1=SERVER, 2=CLIENT, 3=PRODUCER, 4=CONSUMER). Defaults to 0.
            status_code (int): Status code (0=UNSET, 1=OK, 2=ERROR). Defaults to 0.
            status_message (str | None): Optional status description, typically set
                for error spans.
            attributes (dict[str, Any] | None): Key-value pairs of span attributes.
            events (list[dict[str, Any]] | None): Timestamped event records attached
                to the span.
            links (list[dict[str, Any]] | None): Links to other spans, each containing
                at minimum ``trace_id`` and ``span_id`` keys.
            trace_flags (int): W3C trace flags. Defaults to 0.
            experiment_id (str | None): Experiment ID. Uses current experiment if
                not specified.

        Raises:
            ValueError: If no experiment is active and ``experiment_id`` is not provided.

        Example:
        ```python
        import time

        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        start = time.time_ns()
        # ... do work ...
        end = time.time_ns()
        tracker.log_span(
            trace_id="abc123",
            span_id="span_1",
            name="data_preprocessing",
            start_time_unix_nano=start,
            end_time_unix_nano=end,
            attributes={"input_rows": 1000},
        )
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_span(
            exp_id,
            trace_id,
            span_id,
            name,
            start_time_unix_nano,
            end_time_unix_nano,
            parent_span_id,
            kind,
            status_code,
            status_message,
            attributes,
            events,
            links,
            trace_flags,
        )

    def log_eval_sample(
        self,
        eval_id: str,
        dataset_id: str,
        inputs: dict[str, Any],  # noqa: ANN401
        outputs: dict[str, Any] | None = None,  # noqa: ANN401
        references: dict[str, Any] | None = None,  # noqa: ANN401
        scores: dict[str, Any] | None = None,  # noqa: ANN401
        metadata: dict[str, Any] | None = None,  # noqa: ANN401
        experiment_id: str | None = None,
    ) -> None:
        """
        Log a single evaluation sample to the experiment.

        Records one data point from a model evaluation run, including its inputs,
        model outputs, ground-truth references, computed scores, and optional metadata.

        Args:
            eval_id (str): Unique identifier for this evaluation sample.
            dataset_id (str): Identifier of the evaluation dataset this sample
                belongs to.
            inputs (dict[str, Any]): Input data fed to the model for this sample.
            outputs (dict[str, Any] | None): Model outputs/predictions for this sample.
            references (dict[str, Any] | None): Ground-truth or reference values to
                compare against.
            scores (dict[str, Any] | None): Computed evaluation scores (e.g. accuracy,
                F1, BLEU).
            metadata (dict[str, Any] | None): Additional metadata for the sample (e.g.
                latency, token counts).
            experiment_id (str | None): Experiment ID. Uses current experiment if
                not specified.

        Raises:
            ValueError: If no experiment is active and ``experiment_id`` is not provided.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        tracker.log_eval_sample(
            eval_id="sample_001",
            dataset_id="test_set_v2",
            inputs={"prompt": "Summarize this text..."},
            outputs={"response": "The text discusses..."},
            references={"expected": "A summary of..."},
            scores={"bleu": 0.72, "rouge_l": 0.65},
        )
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_eval_sample(
            exp_id,
            eval_id,
            dataset_id,
            inputs,
            outputs,
            references,
            scores,
            metadata,
        )

    def link_eval_sample_to_trace(
        self,
        eval_dataset_id: str,
        eval_id: str,
        trace_id: str,
        experiment_id: str | None = None,
    ) -> None:
        """
        Link an evaluation sample to a trace.

        Associates a previously logged evaluation sample with an execution trace,
        enabling correlation between evaluation results and the traced execution
        that produced them.

        Args:
            eval_dataset_id (str): Identifier of the evaluation dataset the sample
                belongs to.
            eval_id (str): Identifier of the evaluation sample to link.
            trace_id (str): Identifier of the trace to link to.
            experiment_id (str | None): Experiment ID. Uses current experiment if
                not specified.

        Raises:
            ValueError: If no experiment is active and ``experiment_id`` is not provided.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        tracker.log_eval_sample(
            eval_id="sample_001",
            dataset_id="test_set_v2",
            inputs={"prompt": "Hello"},
        )
        tracker.link_eval_sample_to_trace(
            eval_dataset_id="test_set_v2",
            eval_id="sample_001",
            trace_id="trace_abc",
        )
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.link_eval_sample_to_trace(
            exp_id, eval_dataset_id, eval_id, trace_id
        )

    def log_attachment(
        self,
        name: str,
        data: Any,  # noqa: ANN401
        binary: bool = False,
        experiment_id: str | None = None,
    ) -> None:
        """
        Log files or artifacts to the experiment.

        Args:
            name: Attachment name/filename.
            data: Data to attach (string, bytes, or file path).
            binary: Whether data is binary. Default is False.
            experiment_id: Experiment ID. Uses current experiment if not specified.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        tracker.log_attachment("model_config.json", config_json)
        tracker.log_attachment("plot.png", image_bytes, binary=True)
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_attachment(exp_id, name, data, binary)

    def get_experiment(self, experiment_id: str) -> ExperimentData:
        """
        Retrieve full experiment data by ID.

        Returns the complete experiment record including metadata, static parameters,
        dynamic metrics, and attachment information.

        Args:
            experiment_id (str): Unique identifier of the experiment to retrieve.

        Returns:
            ExperimentData: Complete experiment data containing ``experiment_id``,
                ``metadata``, ``static_params``, ``dynamic_metrics``, and
                ``attachments``.

        Example:
        ```python
        tracker = ExperimentTracker()
        data = tracker.get_experiment("my-experiment-id")
        print(data.metadata.name)
        print(data.static_params)
        print(data.dynamic_metrics)
        ```
        """
        return self.backend.get_experiment_data(experiment_id)

    def get_attachment(self, name: str, experiment_id: str | None = None) -> Any:  # noqa: ANN401
        """
        Retrieve a previously logged attachment by name.

        Args:
            name (str): Name of the attachment as specified during
                :meth:`log_attachment`.
            experiment_id (str | None): Experiment ID. Uses current experiment if
                not specified.

        Returns:
            Any: The attachment data as bytes.

        Raises:
            ValueError: If no experiment is active and ``experiment_id`` is not provided.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        tracker.log_attachment("config.json", '{"lr": 0.001}')
        config = tracker.get_attachment("config.json")
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        return self.backend.get_attachment(exp_id, name)

    def list_experiments(self) -> list[Experiment]:
        """
        List all experiments in the backend.

        Returns:
            List of Experiment objects with metadata.

        Example:
        ```python
        tracker = ExperimentTracker()
        experiments = tracker.list_experiments()
        for exp in experiments:
            print(f"{exp.id}: {exp.name}")
        ```
        """
        return self.backend.list_experiments()

    def delete_experiment(self, experiment_id: str) -> None:
        """
        Delete an experiment and all its associated data.

        Permanently removes the experiment record along with its static parameters,
        dynamic metrics, spans, evaluation samples, attachments, and models from
        the backend.

        Args:
            experiment_id (str): Unique identifier of the experiment to delete.

        Example:
        ```python
        tracker = ExperimentTracker()
        tracker.delete_experiment("old-experiment-id")
        ```
        """
        self.backend.delete_experiment(experiment_id)

    def create_group(self, name: str, description: str | None = None) -> Group:
        """
        Create a new experiment group.

        Groups organize related experiments (e.g. by project, task, or hypothesis).
        Experiments are assigned to a group via the ``group`` parameter of
        :meth:`start_experiment`.

        Args:
            name (str): Unique name for the group.
            description (str | None): Optional human-readable description of the group's
                purpose.

        Returns:
            Group: The created group with ``id``, ``name``, ``description``, and
                ``created_at`` fields.

        Example:
        ```python
        tracker = ExperimentTracker()
        group = tracker.create_group(
            "hyperparameter_search", description="LR sweep experiments"
        )
        exp_id = tracker.start_experiment(group=group.name)
        ```
        """
        return self.backend.create_group(name, description)

    def list_groups(self) -> list[Group]:
        """
        List all experiment groups in the backend.

        Returns:
            list[Group]: List of Group objects, each containing ``id``, ``name``,
                ``description``, and ``created_at`` fields.

        Example:
        ```python
        tracker = ExperimentTracker()
        groups = tracker.list_groups()
        for group in groups:
            print(f"{group.name}: {group.description}")
        ```
        """
        return self.backend.list_groups()

    @staticmethod
    def _detect_flavor(model: Any) -> str:  # noqa: ANN401
        module = type(model).__module__ or ""
        for prefix, flavor in _MODULE_PREFIX_TO_FLAVOR.items():
            if module.startswith(prefix):
                return flavor
        supported = ", ".join(sorted(_FLAVOR_REGISTRY.keys()))
        raise ValueError(
            f"Cannot auto-detect flavor for {type(model).__qualname__} "
            f"(module: {module}). Supported flavors: {supported}. "
            f"Pass flavor= explicitly or save the model first "
            f"and pass a ModelReference."
        )

    @staticmethod
    def _save_model_with_flavor(
        model: Any,  # noqa: ANN401
        inputs: Any,  # noqa: ANN401
        flavor: str,
        **kwargs: Any,  # noqa: ANN401
    ) -> ModelReference:
        if flavor not in _FLAVOR_REGISTRY:
            supported = ", ".join(sorted(_FLAVOR_REGISTRY.keys()))
            raise ValueError(f"Unknown flavor '{flavor}'. Supported: {supported}")
        module_path, func_name = _FLAVOR_REGISTRY[flavor]
        module = importlib.import_module(module_path)
        save_fn = getattr(module, func_name)
        if inputs is not None:
            return save_fn(model, inputs, **kwargs)
        return save_fn(model, **kwargs)

    def log_model(
        self,
        model: ModelReference | Any,  # noqa: ANN401
        *,
        name: str | None = None,
        tags: list[str] | None = None,
        flavor: str | None = None,
        inputs: Any = None,  # noqa: ANN401
        experiment_id: str | None = None,
        dependencies: Literal["default", "all"] | list[str] = "default",
        extra_dependencies: list[str] | None = None,
        extra_code_modules: list[str] | Literal["auto"] | None = None,
        manifest_model_name: str | None = None,
        manifest_model_version: str | None = None,
        manifest_model_description: str | None = None,
        manifest_extra_producer_tags: list[str] | None = None,
        **save_kwargs: Any,  # noqa: ANN401
    ) -> ModelReference:
        """
        Log a model to the experiment.

        Accepts either a pre-saved ``ModelReference`` or a raw model object. When a
        raw model is provided, it is serialized automatically using the detected or
        explicitly specified flavor. The serialized artifact is stored in the backend
        and the temporary file is cleaned up.

        Args:
            model (ModelReference | Any): A ``ModelReference`` pointing to an
                already-saved model, or a raw model object to be serialized.
            name (str | None): Optional display name for the model.
            tags (list[str] | None): Optional tags to associate with the model.
            flavor (str | None): Serialization flavor (e.g. ``"sklearn"``,
                ``"xgboost"``). Auto-detected from the model's module if not
                provided. Supported flavors: sklearn, xgboost, lightgbm, catboost,
                langgraph.
            inputs (Any): Sample input data used for model signature inference.
                Required by ``sklearn``, optional for ``xgboost`` and ``lightgbm``,
                and not used by ``catboost`` or ``langgraph``.
            experiment_id (str | None): Experiment ID. Uses current experiment if
                not specified.
            dependencies (Literal["default", "all"] | list[str]): Dependency capture
                strategy. ``"default"`` captures direct dependencies, ``"all"``
                captures the full environment, or pass an explicit list of package
                names.
            extra_dependencies (list[str] | None): Additional package dependencies
                to include beyond those captured by ``dependencies``.
            extra_code_modules (list[str] | Literal["auto"] | None): Extra Python
                modules to bundle with the model. ``"auto"`` attempts automatic
                detection.
            manifest_model_name (str | None): Model name for the artifact manifest.
            manifest_model_version (str | None): Model version for the artifact
                manifest.
            manifest_model_description (str | None): Model description for the
                artifact manifest.
            manifest_extra_producer_tags (list[str] | None): Additional producer
                tags for the artifact manifest.
            **save_kwargs (Any): Additional keyword arguments forwarded to the
                flavor-specific save function.

        Returns:
            ModelReference: Reference to the stored model in the backend.

        Raises:
            ValueError: If no experiment is active and ``experiment_id`` is not
                provided, or if the flavor cannot be auto-detected.

        Example:
        ```python
        from sklearn.ensemble import RandomForestClassifier

        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        model = RandomForestClassifier().fit(X_train, y_train)
        model_ref = tracker.log_model(model, name="rf_v1", inputs=X_train)
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")

        temp_ref: ModelReference | None = None

        if isinstance(model, ModelReference):
            model_ref = model
        else:
            if flavor is None:
                flavor = self._detect_flavor(model)
            save_kwargs.update(
                {
                    k: v
                    for k, v in {
                        "dependencies": dependencies,
                        "extra_dependencies": extra_dependencies,
                        "extra_code_modules": extra_code_modules,
                        "manifest_model_name": manifest_model_name,
                        "manifest_model_version": manifest_model_version,
                        "manifest_model_description": manifest_model_description,
                        "manifest_extra_producer_tags": manifest_extra_producer_tags,
                    }.items()
                    if v is not None and v != "default"
                }
            )
            model_ref = self._save_model_with_flavor(
                model, inputs, flavor, **save_kwargs
            )
            temp_ref = model_ref

        _, stored_path = self.backend.log_model(exp_id, str(model_ref.path), name, tags)

        if temp_ref is not None:
            Path(temp_ref.path).unlink(missing_ok=True)

        return ModelReference(stored_path)

    def get_models(self, experiment_id: str | None = None) -> list[Model]:
        """
        List all models logged to an experiment.

        Args:
            experiment_id (str | None): Experiment ID. Uses current experiment if
                not specified.

        Returns:
            list[Model]: List of Model objects, each containing ``id``, ``name``,
                ``created_at``, ``tags``, ``path``, and ``experiment_id`` fields.

        Raises:
            ValueError: If no experiment is active and ``experiment_id`` is not provided.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        tracker.log_model(model, name="rf_v1", inputs=X_train)
        models = tracker.get_models()
        for m in models:
            print(f"{m.name} logged at {m.created_at}")
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        return self.backend.get_models(exp_id)

    def get_model(self, model_id: str) -> Model:
        """
        Retrieve a single model by its ID.

        Args:
            model_id (str): Unique identifier of the model to retrieve.

        Returns:
            Model: The model record containing ``id``, ``name``, ``created_at``,
                ``tags``, ``path``, and ``experiment_id`` fields.

        Example:
        ```python
        tracker = ExperimentTracker()
        model = tracker.get_model("model-uuid-123")
        print(f"{model.name}: {model.path}")
        ```
        """
        return self.backend.get_model(model_id)

    def link_to_model(
        self, model_reference: ModelReference, experiment_id: str | None = None
    ) -> None:
        """
        Link experiment data to a saved model.

        Attaches experiment tracking data (metrics, parameters, artifacts) to a model
        for reproducibility and model versioning.

        Args:
            model_reference: ModelReference object to link to.
            experiment_id: Experiment ID. Uses current experiment if not specified.

        Example:
        ```python
        from luml.integrations.sklearn import save_sklearn

        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment(name="sklearn_model")
        tracker.log_static("model_type", "RandomForest")

        model_ref = save_sklearn(model, X_train)
        tracker.link_to_model(model_ref)
        ```
        """
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        exp_db = self.backend.export_experiment_db(exp_id)
        attachments_result = self.backend.export_attachments(exp_id)
        if attachments_result is None:
            raise ValueError(f"No attachments found for experiment {exp_id}")
        attachments, index = attachments_result
        tag = "dataforce.studio::experiment_snapshot:v1"
        with NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip:
            zip_path = temp_zip.name

        if isinstance(exp_db, DiskFile):
            path = exp_db.path
            with zipfile.ZipFile(
                zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1
            ) as zipf:
                zipf.write(path, "exp.db")
        else:
            raise NotImplementedError(
                "Only DiskArtifact is supported for exp_db at the moment."
            )

        zipped_exp_db = DiskFile(zip_path)

        model_reference._append_metadata(
            idx=None,
            tags=[tag],
            payload={},
            data=[
                FileMap(file=zipped_exp_db, remote_path="exp.db.zip"),
                FileMap(file=attachments, remote_path="attachments.tar"),
                FileMap(file=index, remote_path="attachments.index.json"),
            ],
            prefix=tag,
        )

        Path(zip_path).unlink(missing_ok=True)

    def enable_tracing(self) -> None:
        """
        Enable OpenTelemetry tracing for the experiment.

        Sets up automatic tracing of function calls and links traces to the experiment.
        Useful for tracking execution flow in ML pipelines.

        Example:
        ```python
        tracker = ExperimentTracker()
        tracker.enable_tracing()
        exp_id = tracker.start_experiment()
        # All traced functions will be logged to this experiment
        ```
        """
        from luml.experiments.tracing import setup_tracing, set_experiment_tracker  # noqa: I001

        setup_tracing()
        set_experiment_tracker(self)

    def export(
        self, output_path: str, experiment_id: str | None = None
    ) -> "ExperimentReference":
        """
        Export the entire experiment tracking data and save as an artifact.

        Args:
            output_path: Path to save the exported artifact.

        Example:
        ```python
        tracker = ExperimentTracker()
        exp_id = tracker.start_experiment()
        # Log data...
        tracker.end_experiment()
        tracker.export("experiment_data.tar", experiment_id=exp_id)
        ```
        """
        from luml.artifacts.experiment import save_experiment

        experiment_id = experiment_id or self.current_experiment_id
        if experiment_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        return save_experiment(self, experiment_id, output_path=output_path)
