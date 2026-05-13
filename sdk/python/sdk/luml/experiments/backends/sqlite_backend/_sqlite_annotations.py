# flake8: noqa: E501
import sqlite3
import uuid
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from luml.experiments.backends.sqlite import SQLiteBackend  # noqa: F401

from luml.experiments.backends.data_types import (
    AnnotationKind,
    AnnotationRecord,
    AnnotationSummary,
    AnnotationValueType,
    ExpectationSummaryItem,
    FeedbackSummaryItem,
)
from luml.experiments.backends.sqlite_backend._sqlite_base import _SQLiteBase


class SQLiteAnnotationMixin(_SQLiteBase):
    def _has_annotation_tables(self, experiment_id: str) -> bool:
        conn = self._get_experiment_connection(experiment_id)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        return version >= 1

    def _require_annotation_tables(self, experiment_id: str) -> None:
        if not self._has_annotation_tables(experiment_id):
            raise ValueError(
                f"Experiment '{experiment_id}' uses an older schema that "
                "does not support annotations. Re-create the experiment "
                "to enable annotation support."
            )

    @staticmethod
    def _serialize_annotation_value(value: int | bool | str) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _deserialize_annotation_value(
        raw: str, value_type: AnnotationValueType
    ) -> int | bool | str:
        if value_type == AnnotationValueType.BOOL:
            return raw.lower() == "true"
        if value_type == AnnotationValueType.INT:
            return int(raw)
        return raw

    @staticmethod
    def _row_to_annotation(row: sqlite3.Row) -> AnnotationRecord:
        vt = AnnotationValueType(row[5])
        return AnnotationRecord(
            id=row[0],
            name=row[1],
            annotation_kind=AnnotationKind(row[2]),
            value_type=vt,
            value=SQLiteAnnotationMixin._deserialize_annotation_value(row[3], vt),
            user=row[4],
            created_at=row[6],
            rationale=row[7],
        )

    @staticmethod
    def _validate_feedback_value_type(
        annotation_kind: AnnotationKind, value_type: AnnotationValueType
    ) -> None:
        if (
            annotation_kind == AnnotationKind.FEEDBACK
            and value_type != AnnotationValueType.BOOL
        ):
            raise ValueError("Feedback annotations must use value_type='bool'")

    def log_eval_annotation(
        self,
        experiment_id: str,
        dataset_id: str,
        eval_id: str,
        name: str,
        annotation_kind: AnnotationKind,
        value_type: AnnotationValueType,
        value: int | bool | str,
        user: str,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        """
        Logs an annotation for a specific evaluation within an experiment and records it in the database.

        This function stores metadata, rationale, and value of the annotation associated with a specific
        evaluation ID. It ensures the consistency of the annotation's type and validates the necessary
        conditions before committing the record into the database.

        Args:
            experiment_id (str): The id of the experiment.
            dataset_id (str): The id of the dataset within the experiment.
            eval_id (str): The id of the eval within the dataset.
            name (str): The name of the annotation being logged.
            annotation_kind (AnnotationKind): The type of the annotation
            value_type (AnnotationValueType): Defines the expected type of the annotation value.
            value (int | bool | str): The actual value of the annotation.
            user (str): The user who created the annotation.
            rationale (str | None): The rationale or reasoning behind the annotation, if applicable.

        Returns:
            AnnotationRecord: Object containing the logged annotation's details from the database.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> record = backend.log_eval_annotation(
            ...     experiment_id="exp-001",
            ...     dataset_id="dataset-abc",
            ...     eval_id="eval-xyz",
            ...     name="quality",
            ...     annotation_kind=AnnotationKind.FEEDBACK,
            ...     value_type=AnnotationValueType.BOOL,
            ...     value=True,
            ...     user="alice",
            ...     rationale="Looks correct",
            ... )
            AnnotationRecord(
                id="annot-001",
                name="quality",
                annotation_kind=AnnotationKind.FEEDBACK,
                value=True,
                user="alice",
                value_type=AnnotationValueType.BOOL,
                created_at=datetime(2024, 6, 1, 10, 0, 0),
                rationale="Looks correct"
            )
        """
        self._validate_feedback_value_type(annotation_kind, value_type)
        self._require_annotation_tables(experiment_id)
        annotation_id = str(uuid.uuid4())
        write_lock = self._get_experiment_write_lock(experiment_id)
        with write_lock:
            conn = self._get_experiment_connection(experiment_id)
            conn.execute(
                """INSERT INTO eval_annotations
                   (id, dataset_id, eval_id, name, annotation_kind, value_type, value, user, rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    annotation_id,
                    dataset_id,
                    eval_id,
                    name,
                    annotation_kind.value,
                    value_type.value,
                    self._serialize_annotation_value(value),
                    user,
                    rationale,
                ),
            )
            conn.commit()
            row = conn.execute(
                """SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
                   FROM eval_annotations WHERE id = ?""",
                (annotation_id,),
            ).fetchone()
        return self._row_to_annotation(row)

    def get_eval_annotations(
        self, experiment_id: str, dataset_id: str, eval_id: str
    ) -> list[AnnotationRecord]:
        """
        Retrieves evaluation annotations associated with a specific experiment, dataset,
        and evaluation identifier. The annotations are fetched from a database table and
        returned as a list of AnnotationRecord objects.

        Args:
            experiment_id: Unique identifier for the experiment.
            dataset_id: Unique identifier for the dataset within the experiment.
            eval_id: Unique identifier for the evaluation phase.

        Returns:
            A list of AnnotationRecord objects representing the annotations retrieved for the
            specified dataset and evaluation phase. Returns an empty list if annotation
            tables are not available for the given experiment.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_eval_annotations("exp-001", "dataset-abc", "eval-xyz")
            [
                AnnotationRecord(
                    id="annot-001",
                    name="quality",
                    annotation_kind=AnnotationKind.FEEDBACK,
                    value=True,
                    user="alice",
                    value_type=AnnotationValueType.BOOL,
                    created_at=datetime(2024, 6, 1, 10, 0, 0),
                    rationale="Looks correct"
                )
            ]
        """
        if not self._has_annotation_tables(experiment_id):
            return []
        conn = self._get_experiment_connection(experiment_id)
        rows = conn.execute(
            """SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
               FROM eval_annotations
               WHERE dataset_id = ? AND eval_id = ?
               ORDER BY created_at""",
            (dataset_id, eval_id),
        ).fetchall()
        return [self._row_to_annotation(r) for r in rows]

    def log_span_annotation(
        self,
        experiment_id: str,
        trace_id: str,
        span_id: str,
        name: str,
        annotation_kind: AnnotationKind,
        value_type: AnnotationValueType,
        value: int | bool | str,
        user: str,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        """
        Logs a span annotation for a specific experiment, enabling traceability and observability within
        the system. This method ensures that the provided annotation is valid, persists the annotation
        data in the experiment database, and retrieves the newly created annotation record.

        Args:
            experiment_id (str): Identifier for the experiment where the annotation will be logged.
            trace_id (str): Identifier for the trace to which the span belongs.
            span_id (str): Identifier for the span to be annotated.
            name (str): Name of the annotation being logged.
            annotation_kind (AnnotationKind): Type or category of the annotation, specifying its role or
                purpose.
            value_type (AnnotationValueType): Data type of the annotation's value, ensuring compatibility
                and validity.
            value (int | bool | str): The actual value associated with the annotation, adhering to the
                specified value type.
            user (str): Identifier of the user or system initiating the creation of the annotation.
            rationale (str | None): Optional explanation or justification for the annotation.

        Returns:
            AnnotationRecord: An object containing the details of the newly created annotation, including
            associated metadata and identifier.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> record = backend.log_span_annotation(
            ...     experiment_id="exp-001",
            ...     trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            ...     span_id="span-abc",
            ...     name="latency_ok",
            ...     annotation_kind=AnnotationKind.FEEDBACK,
            ...     value_type=AnnotationValueType.BOOL,
            ...     value=True,
            ...     user="alice",
            ... )
            AnnotationRecord(
                id="annot-002",
                name="latency_ok",
                annotation_kind=AnnotationKind.FEEDBACK,
                value=True,
                user="alice",
                value_type=AnnotationValueType.BOOL,
                created_at=datetime(2024, 6, 1, 10, 0, 0),
                rationale=None,
            )
        """
        self._validate_feedback_value_type(annotation_kind, value_type)
        self._require_annotation_tables(experiment_id)
        annotation_id = str(uuid.uuid4())
        write_lock = self._get_experiment_write_lock(experiment_id)
        with write_lock:
            conn = self._get_experiment_connection(experiment_id)
            conn.execute(
                """INSERT INTO span_annotations
                   (id, trace_id, span_id, name, annotation_kind, value_type, value, user, rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    annotation_id,
                    trace_id,
                    span_id,
                    name,
                    annotation_kind.value,
                    value_type.value,
                    self._serialize_annotation_value(value),
                    user,
                    rationale,
                ),
            )
            conn.commit()
            row = conn.execute(
                """SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
                   FROM span_annotations WHERE id = ?""",
                (annotation_id,),
            ).fetchone()
        return self._row_to_annotation(row)

    def get_span_annotations(
        self, experiment_id: str, trace_id: str, span_id: str
    ) -> list[AnnotationRecord]:
        """
        Fetches annotations for a specific span in a trace within the context of an experiment.

        This method retrieves all annotations associated with a span, identified by its trace
        and span IDs, within a given experiment. The annotations are returned as a list of
        `AnnotationRecord` objects, sorted by their creation timestamp. If no annotation tables
        exist for the given experiment, an empty list is returned.

        Args:
            experiment_id (str): The unique identifier of the experiment.
            trace_id (str): The unique identifier of the trace.
            span_id (str): The unique identifier of the span whose annotations are to be fetched.

        Returns:
            list[AnnotationRecord]: A list of annotations for the specified span. If no
            annotations are found, the returned list will be empty.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_span_annotations(
            ...     "exp-001",
            ...     "4bf92f3577b34da6a3ce929d0e0e4736",
            ...     "span-abc",
            ... )
            [
                AnnotationRecord(
                    id="annot-002",
                    name="latency_ok",
                    annotation_kind=AnnotationKind.FEEDBACK,
                    value=True,
                    user="alice",
                    value_type=AnnotationValueType.BOOL,
                    created_at=datetime(2024, 6, 1, 10, 0, 0),
                    rationale=None
                )
            ]
        """
        if not self._has_annotation_tables(experiment_id):
            return []
        conn = self._get_experiment_connection(experiment_id)
        rows = conn.execute(
            """SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
               FROM span_annotations
               WHERE trace_id = ? AND span_id = ?
               ORDER BY created_at""",
            (trace_id, span_id),
        ).fetchall()
        return [self._row_to_annotation(r) for r in rows]

    def update_annotation(
        self,
        experiment_id: str,
        annotation_id: str,
        target: Literal["eval", "span"],
        value: int | bool | str | None = None,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        """
        Updates an annotation record in the specified table with the provided fields.

        This method allows modification of an existing annotation record by updating its
        `value` and/or `rationale` fields in the corresponding database table. The table is
        selected based on the target type ("eval" or "span"). If no fields are provided for
        update, an error is raised.

        Args:
            experiment_id (str): The unique identifier for the experiment associated with the
                annotation.
            annotation_id (str): The unique identifier for the annotation to be updated.
            target (Literal["eval", "span"]): Specifies the annotation table to use. "eval"
                refers to evaluation annotations and "span" refers to span annotations.
            value (int | bool | str | None, optional): The new value to set for the annotation.
                If not provided, the value field will not be updated.
            rationale (str | None, optional): The new rationale to set for the annotation. If
                not provided, the rationale field will not be updated.

        Returns:
            AnnotationRecord: An updated annotation record object after the update operation.

        Raises:
            ValueError: If no fields (`value` or `rationale`) are specified for update or if
                the specified annotation does not exist in the database.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.update_annotation(
            ...     experiment_id="exp-001",
            ...     annotation_id="annot-001",
            ...     target="eval",
            ...     value=False,
            ...     rationale="Reconsidered after review",
            ... )
            AnnotationRecord(
                id="annot-001",
                name="quality",
                annotation_kind=AnnotationKind.FEEDBACK,
                value=False,
                user="alice",
                value_type=AnnotationValueType.BOOL,
                created_at=datetime(2024, 6, 1, 10, 0, 0),
                rationale="Reconsidered after review",
            )
        """
        self._require_annotation_tables(experiment_id)
        table = "eval_annotations" if target == "eval" else "span_annotations"
        conn = self._get_experiment_connection(experiment_id)

        sets: list[str] = []
        params: list[str] = []
        if value is not None:
            sets.append("value = ?")
            params.append(self._serialize_annotation_value(value))
        if rationale is not None:
            sets.append("rationale = ?")
            params.append(rationale)
        if not sets:
            raise ValueError("No fields to update")

        params.append(annotation_id)
        conn.execute(
            f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        conn.commit()
        row = conn.execute(
            f"SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale FROM {table} WHERE id = ?",  # noqa: S608
            (annotation_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Annotation '{annotation_id}' not found")
        return self._row_to_annotation(row)

    def delete_annotation(
        self, experiment_id: str, annotation_id: str, target: Literal["eval", "span"]
    ) -> None:
        """
        Deletes a specific annotation from the database for a given experiment.

        This method removes an annotation identified by its annotation_id from the
        appropriate table associated with the target type (either "eval" or "span")
        within the specified experiment. If the experiment does not have annotation
        tables, the method exits without performing any operation.

        Args:
            experiment_id (str): The unique identifier for the experiment.
            annotation_id (str): The unique identifier for the annotation to be deleted.
            target (Literal["eval", "span"]): Specifies the target table from which the
                annotation should be deleted. Must be either "eval" or "span".

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.delete_annotation("exp-001", "annot-001", target="eval")
        """
        if not self._has_annotation_tables(experiment_id):
            return
        table = "eval_annotations" if target == "eval" else "span_annotations"
        conn = self._get_experiment_connection(experiment_id)
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (annotation_id,))  # noqa: S608
        conn.commit()

    @staticmethod
    def _build_annotation_summary(
        feedback_rows: list[sqlite3.Row],
        expectation_rows: list[sqlite3.Row],
    ) -> AnnotationSummary:
        """
        Builds an annotation summary from feedback and expectation data.

        The method processes two sets of rows: feedback data and expectation
        data, aggregating and casting values where appropriate, to create a
        structured summary.

        Args:
            feedback_rows (list[sqlite3.Row]): A list of sqlite3.Row objects representing
                feedback data. Each row should contain name, value, and count.
            expectation_rows (list[sqlite3.Row]): A list of sqlite3.Row objects representing
                expectation data. Each row should contain name, total, positive, negative,
                and raw value information.

        Returns:
            AnnotationSummary: A structured summary of the feedback and expectations,
            including aggregated feedback items and processed expectation details.
        """

        feedback_items: dict[str, FeedbackSummaryItem] = {}
        for row in feedback_rows:
            name, value, count = row[0], row[1], row[2]
            if name not in feedback_items:
                feedback_items[name] = FeedbackSummaryItem(
                    name=name, total=0, counts={}
                )
            item = feedback_items[name]
            item.total += count
            item.counts[value] = count

        def _cast_value(raw: str | None, value_type: str | None) -> int | str | None:
            if raw is None:
                return None
            if value_type == "int":
                return int(raw)
            return raw

        return AnnotationSummary(
            feedback=sorted(feedback_items.values(), key=lambda x: x.name),
            expectations=[
                ExpectationSummaryItem(
                    name=row[0],
                    total=row[1],
                    positive=row[2],
                    negative=row[3],
                    value=_cast_value(row[4], row[5]),
                )
                for row in expectation_rows
            ],
        )

    def get_evals_annotation_summaries(
        self, experiment_id: str, eval_ids: list[str]
    ) -> dict[str, AnnotationSummary]:
        """
        Retrieves annotation summaries for a batch of evaluations within an experiment.

        Args:
            experiment_id (str): The unique identifier of the experiment.
            eval_ids (list[str]): A list of evaluation IDs to retrieve summaries for.

        Returns:
            dict[str, AnnotationSummary]: A dictionary mapping each eval ID to its annotation
            summary. Eval IDs with no annotations are excluded from the result.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_evals_annotation_summaries("exp-001", ["eval-xyz", "eval-abc"])
            {
                "eval-xyz": AnnotationSummary(
                    feedback=[FeedbackSummaryItem(name="quality", total=2, counts={"true": 1, "false": 1})],
                    expectations=[],
                ),
            }
        """
        if not self._has_annotation_tables(experiment_id) or not eval_ids:
            return {}
        conn = self._get_experiment_connection(experiment_id)
        feedback_by_eval: dict[str, list] = {}
        expectation_by_eval: dict[str, list] = {}
        for i in range(0, len(eval_ids), 900):
            batch = eval_ids[i : i + 900]
            placeholders = ",".join("?" * len(batch))
            for row in conn.execute(
                f"""SELECT eval_id, name, value, COUNT(*) AS cnt
                   FROM eval_annotations
                   WHERE eval_id IN ({placeholders}) AND annotation_kind = 'feedback'
                   GROUP BY eval_id, name, value
                   ORDER BY name, value""",
                batch,
            ).fetchall():
                feedback_by_eval.setdefault(row[0], []).append(row[1:])
            for row in conn.execute(
                f"""SELECT eval_id, name, COUNT(*) AS total,
                       SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                       SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                       MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                       MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
                   FROM eval_annotations
                   WHERE eval_id IN ({placeholders}) AND annotation_kind = 'expectation'
                   GROUP BY eval_id, name
                   ORDER BY name""",
                batch,
            ).fetchall():
                expectation_by_eval.setdefault(row[0], []).append(row[1:])
        return {
            eval_id: self._build_annotation_summary(
                feedback_by_eval.get(eval_id, []),
                expectation_by_eval.get(eval_id, []),
            )
            for eval_id in eval_ids
            if eval_id in feedback_by_eval or eval_id in expectation_by_eval
        }

    def get_eval_annotation_summary(
        self, experiment_id: str, dataset_id: str
    ) -> AnnotationSummary:
        """
        Retrieves a summary of evaluation annotations for a specific experiment and dataset.

        This method queries annotation data associated with the provided experiment
        and dataset identifiers, specifically gathering details about feedback and
        expectation annotations. Feedback annotations provide a count of distinct
        name-value pairs, while expectation annotations summarize details such as
        total occurrences, positive and negative boolean counts, and sample values
        for non-boolean annotations.

        Args:
            experiment_id (str): Unique identifier for the experiment to retrieve
                annotation data from.
            dataset_id (str): Unique identifier for the dataset within the specified
                experiment.

        Returns:
            AnnotationSummary: A summary of feedback and expectations contained in
                the evaluation annotations for the given experiment and dataset.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_eval_annotation_summary("exp-001", "dataset-abc")
            AnnotationSummary(
                feedback=[FeedbackSummaryItem(name="quality", total=3, counts={"true": 2, "false": 1})],
                expectations=[],
            )
        """
        if not self._has_annotation_tables(experiment_id):
            return AnnotationSummary(feedback=[], expectations=[])
        conn = self._get_experiment_connection(experiment_id)
        feedback_rows = conn.execute(
            """SELECT name, value, COUNT(*) AS cnt
               FROM eval_annotations
               WHERE dataset_id = ? AND annotation_kind = 'feedback'
               GROUP BY name, value
               ORDER BY name, value""",
            (dataset_id,),
        ).fetchall()
        expectation_rows = conn.execute(
            """SELECT name, COUNT(*) AS total,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                   MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                   MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
               FROM eval_annotations
               WHERE dataset_id = ? AND annotation_kind = 'expectation'
               GROUP BY name
               ORDER BY name""",
            (dataset_id,),
        ).fetchall()
        return self._build_annotation_summary(feedback_rows, expectation_rows)

    def get_traces_annotation_summaries(
        self, experiment_id: str, trace_ids: list[str]
    ) -> dict[str, AnnotationSummary]:
        """
        Retrieves annotation summaries for specified traces in a given experiment. This method aggregates
        feedback and expectation annotations for each trace, combining them to build summaries of annotations.
        For annotation kinds, 'feedback' aggregates counts of values, while 'expectation' provides both
        aggregate counts and value-specific information.

        Args:
            experiment_id (str): The unique identifier of the experiment.
            trace_ids (list[str]): A list of trace IDs for which annotation summaries are to be retrieved.

        Returns:
            dict[str, AnnotationSummary]: A dictionary mapping each trace ID to its annotation summary.
            If no annotations are present, or the input trace list is empty, an empty dictionary is returned.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_traces_annotation_summaries(
            ...     "exp-001",
            ...     ["4bf92f3577b34da6a3ce929d0e0e4736", "5bf92f3577b34da6a3ce929d0e0e4737"],
            ... )
            {
                "4bf92f3577b34da6a3ce929d0e0e4736": AnnotationSummary(
                    feedback=[FeedbackSummaryItem(name="latency_ok", total=1, counts={"true": 1})],
                    expectations=[],
                ),
            }
        """
        if not self._has_annotation_tables(experiment_id) or not trace_ids:
            return {}
        conn = self._get_experiment_connection(experiment_id)
        feedback_by_trace: dict[str, list] = {}
        expectation_by_trace: dict[str, list] = {}
        for i in range(0, len(trace_ids), 900):
            batch = trace_ids[i : i + 900]
            placeholders = ",".join("?" * len(batch))
            for row in conn.execute(
                f"""SELECT trace_id, name, value, COUNT(*) AS cnt
                   FROM span_annotations
                   WHERE trace_id IN ({placeholders}) AND annotation_kind = 'feedback'
                   GROUP BY trace_id, name, value
                   ORDER BY name, value""",
                batch,
            ).fetchall():
                feedback_by_trace.setdefault(row[0], []).append(row[1:])
            for row in conn.execute(
                f"""SELECT trace_id, name, COUNT(*) AS total,
                       SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                       SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                       MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                       MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
                   FROM span_annotations
                   WHERE trace_id IN ({placeholders}) AND annotation_kind = 'expectation'
                   GROUP BY trace_id, name
                   ORDER BY name""",
                batch,
            ).fetchall():
                expectation_by_trace.setdefault(row[0], []).append(row[1:])
        return {
            trace_id: self._build_annotation_summary(
                feedback_by_trace.get(trace_id, []),
                expectation_by_trace.get(trace_id, []),
            )
            for trace_id in trace_ids
            if trace_id in feedback_by_trace or trace_id in expectation_by_trace
        }

    def get_trace_annotation_summary(
        self, experiment_id: str, trace_id: str
    ) -> AnnotationSummary:
        """
        Retrieves the annotation summary for a specific trace in a given experiment. The summary includes
        feedback and expectation annotations grouped by name and processed according to their type and values.

        Args:
            experiment_id (str): The unique identifier of the experiment.
            trace_id (str): The unique identifier of the trace.

        Returns:
            AnnotationSummary: An object containing summarized feedback and expectations annotations
            for the specified trace.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_trace_annotation_summary("exp-001", "4bf92f3577b34da6a3ce929d0e0e4736")
            AnnotationSummary(
                feedback=[FeedbackSummaryItem(name="latency_ok", total=1, counts={"true": 1})],
                expectations=[],
            )
        """
        if not self._has_annotation_tables(experiment_id):
            return AnnotationSummary(feedback=[], expectations=[])
        conn = self._get_experiment_connection(experiment_id)
        feedback_rows = conn.execute(
            """SELECT name, value, COUNT(*) AS cnt
               FROM span_annotations
               WHERE trace_id = ? AND annotation_kind = 'feedback'
               GROUP BY name, value
               ORDER BY name, value""",
            (trace_id,),
        ).fetchall()
        expectation_rows = conn.execute(
            """SELECT name, COUNT(*) AS total,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                   MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                   MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
               FROM span_annotations
               WHERE trace_id = ? AND annotation_kind = 'expectation'
               GROUP BY name
               ORDER BY name""",
            (trace_id,),
        ).fetchall()
        return self._build_annotation_summary(feedback_rows, expectation_rows)

    def get_all_traces_annotation_summary(
        self, experiment_id: str
    ) -> AnnotationSummary:
        """
        Retrieves an annotation summary, including detailed feedback and expectation statistics, for a
        specified experiment given its identifier.

        This method extracts and organizes data from the annotation tables of an experiment, if available,
        to generate a summary of the feedback and expectations associated with that experiment. If the
        annotation tables are not present, it will return an empty summary object.

        Args:
            experiment_id (str): The unique identifier of the experiment from which annotation data
                will be retrieved.

        Returns:
            AnnotationSummary: A summary object containing feedback-related statistics and expectation
                values derived from the experiment's annotations.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_all_traces_annotation_summary("exp-001")
            AnnotationSummary(
                feedback=[
                    FeedbackSummaryItem(
                        name="latency_ok",
                        total=5,
                        counts={"true": 4, "false": 1}
                    )
                ],
                expectations=[]
            )
        """
        if not self._has_annotation_tables(experiment_id):
            return AnnotationSummary(feedback=[], expectations=[])
        conn = self._get_experiment_connection(experiment_id)
        feedback_rows = conn.execute(
            """SELECT name, value, COUNT(*) AS cnt
               FROM span_annotations
               WHERE annotation_kind = 'feedback'
               GROUP BY name, value
               ORDER BY name, value""",
        ).fetchall()
        expectation_rows = conn.execute(
            """SELECT name, COUNT(*) AS total,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                   MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                   MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
               FROM span_annotations
               WHERE annotation_kind = 'expectation'
               GROUP BY name
               ORDER BY name""",
        ).fetchall()
        return self._build_annotation_summary(feedback_rows, expectation_rows)
