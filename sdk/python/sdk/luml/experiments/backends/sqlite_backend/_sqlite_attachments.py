# flake8: noqa: E501
import uuid

from sdk.luml.artifacts._base import _BaseFile
from sdk.luml.experiments.backends.data_types import (
    AttachmentRecord,
    FileNode,
)
from sdk.luml.experiments.backends.sqlite_backend._sqlite_base import _SQLiteBase
from sdk.luml.utils.tar import create_and_index_tar


class SQLiteAttachmentMixin(_SQLiteBase):
    def log_attachment(
        self, experiment_id: str, name: str, data: bytes | str, binary: bool = False
    ) -> None:
        """
        Logs an attachment for a specific experiment by saving the data to a file and updating
        the corresponding database record.

        Args:
            experiment_id (str): The unique identifier of the experiment where the attachment
                will be logged.
            name (str): The name of the attachment file.
            data (bytes | str): The content of the attachment to be logged. This must be either
                bytes or a string.
            binary (bool): Whether the attachment data should be saved in binary mode. Defaults
                to False.

        Raises:
            ValueError: If the provided `data` is not of type `bytes` or `str`.
        """
        self._ensure_experiment_initialized(experiment_id)

        attachments_dir = self._get_attachments_dir(experiment_id)

        if not isinstance(data, bytes | str):
            raise ValueError("Attachment data must be bytes or str")

        file_path = attachments_dir / name
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("wb+" if binary else "w+") as f:
            f.write(data)
        size = file_path.stat().st_size

        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        relative_path = str(
            file_path.relative_to(self._get_attachments_dir(experiment_id))
        )
        cursor.execute("SELECT id FROM attachments WHERE name = ?", (name,))
        existing = cursor.fetchone()
        if existing and existing[0] is not None:
            cursor.execute(
                "UPDATE attachments SET file_path = ?, size = ? WHERE name = ?",
                (relative_path, size, name),
            )
        elif existing:
            cursor.execute(
                "UPDATE attachments SET id = ?, file_path = ?, size = ? WHERE name = ?",
                (str(uuid.uuid4()), relative_path, size, name),
            )
        else:
            cursor.execute(
                "INSERT INTO attachments (id, name, file_path, size) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), name, relative_path, size),
            )

        conn.commit()

    def get_attachment(self, experiment_id: str, name: str) -> bytes:
        """
        Fetches the content of a specific attachment file associated with an experiment.

        This method retrieves the contents of an attachment file from the directory
        corresponding to a given experiment. The file is identified by its name and
        the ID of the experiment. If the experiment has not been initialized or
        the specified attachment cannot be found, appropriate errors are raised.

        Args:
            experiment_id (str): Identifier for the experiment whose attachment is
                being accessed.
            name (str): Name of the attachment file to retrieve.

        Returns:
            Any: The binary content of the specified attachment file.

        Raises:
            ValueError: If the specified attachment file is not found within the
                directory of the given experiment.
        """
        self._ensure_experiment_initialized(experiment_id)

        attachments_dir = self._get_attachments_dir(experiment_id)
        file_path = attachments_dir / name

        if not file_path.exists():
            raise ValueError(
                f"Attachment {name} not found in experiment {experiment_id}"
            )

        with file_path.open("rb") as f:
            return f.read()

    def list_attachments(self, experiment_id: str) -> list[AttachmentRecord]:
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, file_path, size, created_at FROM attachments ORDER BY file_path"
        )
        return [
            AttachmentRecord(
                id=id_,
                name=name,
                file_path=file_path or "",
                size=size,
                created_at=created_at,
            )
            for id_, name, file_path, size, created_at in cursor.fetchall()
        ]

    def list_attachments_tree(
        self, experiment_id: str, parent_path: str | None = None
    ) -> list[FileNode]:
        """
        Retrieves a structured representation of the attachments associated with a specific
        experiment, organized as a tree. Distinguishes between individual files and folders,
        aggregating folder sizes based on their contents.

        Args:
            experiment_id: A string representing the identifier for the experiment whose
                attachments are being queried.
            parent_path: An optional string representing the parent folder path used as a
                base for filtering and structuring the attachments. Defaults to None.

        Returns:
            A list of `FileNode` objects organized into a tree structure. Each `FileNode`
            represents either a file or a folder. Files have their size specified, while
            folder sizes are aggregated based on their contents.
        """
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        prefix = (parent_path.rstrip("/") + "/") if parent_path else ""

        if prefix:
            cursor.execute(
                "SELECT name, size FROM attachments WHERE name LIKE ? ORDER BY name",
                (prefix + "%",),
            )
        else:
            cursor.execute("SELECT name, size FROM attachments ORDER BY name")

        result: list[FileNode] = []
        folder_sizes: dict[str, int] = {}

        for name, size in cursor.fetchall():
            relative = name[len(prefix) :]
            parts = relative.split("/")

            if len(parts) == 1:
                result.append(
                    FileNode(name=parts[0], type="file", size=size, path=name)
                )
            else:
                folder_name = parts[0]
                folder_path = prefix + folder_name
                folder_sizes[folder_path] = folder_sizes.get(folder_path, 0) + (
                    size or 0
                )

        for folder_path, total_size in folder_sizes.items():
            folder_name = folder_path[len(prefix) :]
            result.append(
                FileNode(
                    name=folder_name, type="folder", path=folder_path, size=total_size
                )
            )

        return result

    def export_attachments(
        self, experiment_id: str
    ) -> tuple[_BaseFile, _BaseFile] | None:
        """
        Exports attachments associated with a specific experiment.

        This function retrieves, archives, and indexes the attachments of a specified
        experiment by creating a tarball. Depending on the presence of attachments,
        it may return created files or None.

        Args:
            experiment_id (str): The unique identifier of the experiment whose
                attachments need to be exported.

        Returns:
            tuple[_BaseFile, _BaseFile] | None: A tuple containing the created tarball
                and index file if attachments exist, or `None` if no attachments are
                found.
        """
        return create_and_index_tar(self._get_attachments_dir(experiment_id))
