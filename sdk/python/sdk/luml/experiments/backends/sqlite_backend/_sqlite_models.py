# flake8: noqa: E501
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sdk.luml.experiments.backends.sqlite import SQLiteBackend

from sdk.luml.experiments.backends.data_types import (
    Model,
)
from sdk.luml.experiments.backends.sqlite_backend._sqlite_base import _SQLiteBase


class SQLiteModelMixin(_SQLiteBase):
    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Model:
        return Model(
            id=row[0],
            name=row[1],
            created_at=row[2],
            tags=json.loads(row[3]) if row[3] else [],
            path=row[4],
            size=row[5],
            experiment_id=row[6],
            source=row[7],
            description=row[8],
        )

    def _fetch_model(self, cursor: sqlite3.Cursor, model_id: str) -> Model | None:
        cursor.execute(
            "SELECT id, name, created_at, tags, path, size, experiment_id, source, description FROM models WHERE id = ?",
            (model_id,),
        )
        row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def log_model(
        self,
        experiment_id: str,
        model_path: str,
        name: str | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        description: str | None = None,
    ) -> tuple[Model, str]:
        """
        Logs a machine learning model to the specified experiment by storing its metadata and
        copying the model file to the appropriate storage location.

        Args:
            experiment_id (str): The unique identifier of the experiment to which the model
                is logged.
            model_path (str): The file path of the model to be logged.
            name (str | None, optional): The name of the model. If not provided, the stem of
                the model file name is used.
            tags (list[str] | None, optional): A list of tags associated with the model to
                provide metadata for organizational or informational purposes.
            source (str | None, optional): Path of the script or file that logged the model.
            description (str | None, optional): Human-readable description of the model.

        Returns:
            tuple[Model, str]: A tuple containing the `Model` object representing the logged
                model's metadata and the absolute destination path of the copied model file.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> model, dest_path = backend.log_model(
            ...     experiment_id="exp-001",
            ...     model_path="/tmp/resnet50.pt",
            ...     name="resnet50_v1",
            ...     tags=["production", "v1"],
            ... )
            >>> model
            Model(
                id="model-abc",
                name="resnet50_v1",
                created_at=datetime(2024, 6, 1, 12, 0, 0),
                tags=["production", "v1"],
                path="/storage/exp-001/models/resnet50_v1.pt",
                experiment_id="exp-001",
            )
            >>> dest_path
            "/storage/exp-001/models/resnet50_v1.pt"
        """
        self._ensure_experiment_initialized(experiment_id)

        import shutil

        exp_dir = self._get_experiment_dir(experiment_id)
        models_dir = exp_dir / "models"
        models_dir.mkdir(exist_ok=True)

        model_src = Path(model_path)
        dest = models_dir / model_src.name
        shutil.copy2(model_src, dest)

        model_id = str(uuid.uuid4())
        tags_json = json.dumps(tags) if tags else None

        rel_path = str(dest.relative_to(self.base_path))

        conn = self._get_meta_connection()
        cursor = conn.cursor()
        size = dest.stat().st_size

        cursor.execute(
            "INSERT INTO models (id, name, tags, path, size, experiment_id, source, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (model_id, name or model_src.stem, tags_json, rel_path, size, experiment_id, source, description),
        )
        conn.commit()

        now = datetime.now(UTC)
        model = Model(
            id=model_id,
            name=name or model_src.stem,
            created_at=now,
            tags=tags or [],
            path=rel_path,
            size=size,
            experiment_id=experiment_id,
            source=source,
            description=description,
        )
        return model, str(dest)

    def get_models(self, experiment_id: str) -> list[Model]:
        """
        Fetches all models associated with a given experiment ID.

        This method queries the database for all models that are linked to the
        specified experiment ID. Each row fetched from the database is converted
        to a `Model` object and returned as part of a list.

        Args:
            experiment_id (str): The identifier of the experiment whose models
                need to be fetched.

        Returns:
            list[Model]: A list of `Model` objects associated with the given
                experiment ID.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_models("exp-001")
            [
                Model(
                    id="model-abc",
                    name="resnet50_v1",
                    created_at=datetime(2024, 6, 1, 12, 0, 0),
                    tags=["production", "v1"],
                    path="/artifacts/resnet50_v1.pt",
                    experiment_id="exp-001",
                ),
                Model(
                    id="model-def",
                    name="resnet50_v2",
                    created_at=datetime(2024, 6, 2, 9, 0, 0),
                    tags=[],
                    path=None,
                    experiment_id="exp-001",
                ),
            ]
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, created_at, tags, path, size, experiment_id, source, description FROM models WHERE experiment_id = ?",
            (experiment_id,),
        )
        return [self._row_to_model(row) for row in cursor.fetchall()]

    def get_model(self, model_id: str) -> Model:
        """
        Retrieves a model instance based on the provided model ID.

        Uses an internal meta connection to locate and fetch the model by the
        given model ID. If the model does not exist, a ValueError is raised.

        Args:
            model_id (str): The unique identifier of the model to retrieve.

        Returns:
            Model: The retrieved model instance.

        Raises:
            ValueError: If the model with the specified ID is not found.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_model("model-abc")
            Model(
                id="model-abc",
                name="resnet50_v1",
                created_at=datetime(2024, 6, 1, 12, 0, 0),
                tags=["production", "v1"],
                path="/artifacts/resnet50_v1.pt",
                experiment_id="exp-001",
            )

            >>> backend.get_model("nonexistent-id")
            ValueError: Model nonexistent-id not found
        """
        conn = self._get_meta_connection()
        model = self._fetch_model(conn.cursor(), model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        return model

    def list_batch_experiments_models(
        self, experiment_ids: list[str]
    ) -> dict[str, list[Model]]:
        """
        Retrieves models associated with a list of experiment IDs. Models are organized into a dictionary
        where the key is the experiment ID, and the value is a list of `Model` objects belonging to that
        experiment. If no experiment IDs are provided, an empty dictionary is returned.

        Args:
            experiment_ids (list[str]): A list of experiment IDs for which models need to be fetched.

        Returns:
            dict[str, list[Model]]: A dictionary where keys are experiment IDs and values are lists of
            models associated with those experiment IDs.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.list_batch_experiments_models(["exp-001", "exp-002"])
            {
                "exp-001": [
                    Model(
                        id="model-abc",
                        name="resnet50_v1",
                        created_at=datetime(2024, 6, 1, 12, 0, 0),
                        tags=["production"],
                        path="/artifacts/resnet50_v1.pt",
                        experiment_id="exp-001",
                    ),
                ],
                "exp-002": [
                    Model(
                        id="model-def",
                        name="bert_base",
                        created_at=datetime(2024, 6, 2, 9, 0, 0),
                        tags=[],
                        path=None,
                        experiment_id="exp-002",
                    ),
                ],
            }
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        models_by_experiment: dict[str, list[Model]] = {}
        if experiment_ids:
            placeholders = ", ".join("?" for _ in experiment_ids)

            cursor.execute(
                f"SELECT id, name, created_at, tags, path, size, experiment_id "
                f"FROM models WHERE experiment_id IN ({placeholders})",
                experiment_ids,
            )
            for row in cursor.fetchall():
                models_by_experiment.setdefault(row[6], []).append(
                    self._row_to_model(row)
                )

        return models_by_experiment

    def list_experiment_models(self, experiment_id: str) -> list[Model]:
        """
        Fetches a list of models associated with the specified experiment.

        This method queries the database for all models tied to an experiment identified
        by the provided `experiment_id`. Each model is returned as an instance of the
        `Model` class. The models include details such as their IDs, names, creation
        timestamps, tags, associated paths, and experiment IDs.

        Args:
            experiment_id (str): The unique identifier of the experiment whose
                models are to be retrieved.

        Returns:
            list[Model]: A list of `Model` instances representing the models
                associated with the specified experiment.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.list_experiment_models("exp-001")
            [
                Model(
                    id="model-abc",
                    name="resnet50_v1",
                    created_at=datetime(2024, 6, 1, 12, 0, 0),
                    tags=["production", "v1"],
                    path="/artifacts/resnet50_v1.pt",
                    experiment_id="exp-001",
                ),
                Model(
                    id="model-def",
                    name="resnet50_v2",
                    created_at=datetime(2024, 6, 1, 14, 30, 0),
                    tags=[],
                    path=None,
                    experiment_id="exp-001",
                ),
            ]
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, created_at, tags, path, size, experiment_id "
            "FROM models WHERE experiment_id = ?",
            (experiment_id,),
        )

        return [self._row_to_model(row) for row in cursor.fetchall()]

    def update_model(
        self,
        model_id: str,
        name: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> Model | None:
        """
        Updates the attributes of a model in the database given its model ID.

        This method allows updating the name, tags, and description of a model. If no fields are
        provided for updating, it fetches and returns the original model. The tags,
        if provided, are stored as a JSON string in the database.

        Args:
            model_id (str): The unique identifier of the model to update.
            name (str | None): The new name for the model. Defaults to None.
            tags (list[str] | None): A list of string tags to associate with the model.
                Defaults to None.
            description (str | None): Human-readable description of the model. Defaults to None.

        Returns:
            Model | None: The updated model as a `Model` object if the update is
            successful, or None if the model with the given ID does not exist.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.update_model("model-abc", name="resnet50_v2", tags=["production", "v2"])
            Model(
                id="model-abc",
                name="resnet50_v2",
                created_at=datetime(2024, 6, 1, 12, 0, 0),
                tags=["production", "v2"],
                path="/artifacts/resnet50_v1.pt",
                experiment_id="exp-001",
            )

            >>> backend.update_model("nonexistent-id")
            None
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        fields: list[str] = []
        values: list[Any] = []

        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if tags is not None:
            fields.append("tags = ?")
            values.append(json.dumps(tags))
        if description is not None:
            fields.append("description = ?")
            values.append(description)

        if not fields:
            return self._fetch_model(cursor, model_id)

        values.append(model_id)
        cursor.execute(
            f"UPDATE models SET {', '.join(fields)} WHERE id = ?",  # noqa: S608
            values,
        )
        conn.commit()

        return self._fetch_model(cursor, model_id)

    def delete_model(self, model_id: str) -> None:
        """
        Deletes a model and its files from the database and filesystem.

        The method removes a model entry from the database and, if a file path for the
        model exists, deletes the associated file from the specified directory.

        Args:
            model_id (str): The unique identifier of the model to be deleted.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM models WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        if row and row[0]:
            model_file = self.base_path / row[0]
            if model_file.exists():
                model_file.unlink()

        cursor.execute("DELETE FROM models WHERE id = ?", (model_id,))
        conn.commit()
