import builtins
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .._exceptions import FileError, FileUploadError, LumlAPIError
from .._types import (
    CreatedModel,
    ModelArtifact,
    ModelArtifactStatus,
    is_uuid,
)
from .._utils import find_by_value
from ..utils.file_handler import FileHandler
from ..utils.model_artifacts import ModelFileHandler
from ._validators import validate_collection

if TYPE_CHECKING:
    from .._client import AsyncLumlClient, LumlClient

file_handler = FileHandler()


class ModelArtifactResourceBase(ABC):
    """Abstract Resource for managing Model Artifacts."""

    @abstractmethod
    def get(
        self, model_value: str | int, *, collection_id: str | None = None
    ) -> ModelArtifact | None | Coroutine[Any, Any, ModelArtifact | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_name(
        self, collection_id: str | None, name: str
    ) -> ModelArtifact | None | Coroutine[Any, Any, ModelArtifact | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_id(
        self, collection_id: str | None, model_value: str
    ) -> ModelArtifact | None | Coroutine[Any, Any, ModelArtifact | None]:
        raise NotImplementedError()

    @abstractmethod
    def list(
        self, *, collection_id: str | None = None
    ) -> list[ModelArtifact] | Coroutine[Any, Any, list[ModelArtifact]]:
        raise NotImplementedError()

    @abstractmethod
    def download_url(
        self, model_id: str, *, collection_id: str | None = None
    ) -> dict | Coroutine[Any, Any, dict]:
        raise NotImplementedError()

    @abstractmethod
    def delete_url(
        self, model_id: str, *, collection_id: str | None = None
    ) -> dict | Coroutine[Any, Any, dict]:
        raise NotImplementedError()

    @abstractmethod
    def upload(
        self,
        file_path: str,
        model_name: str,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: str | None = None,
    ) -> ModelArtifact | Coroutine[Any, Any, ModelArtifact]:
        raise NotImplementedError()

    @abstractmethod
    def download(
        self,
        model_id: str,
        file_path: str | None = None,
        *,
        collection_id: str | None = None,
    ) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()

    @abstractmethod
    def create(
        self,
        collection_id: str | None,
        file_name: str,
        metrics: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> (
        dict[str, str | CreatedModel]
        | Coroutine[Any, Any, dict[str, str | CreatedModel]]
    ):
        raise NotImplementedError()

    @abstractmethod
    def update(
        self,
        model_id: str,
        file_name: str | None = None,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: ModelArtifactStatus | None = None,
        *,
        collection_id: str | None = None,
    ) -> ModelArtifact | Coroutine[Any, Any, ModelArtifact]:
        raise NotImplementedError()

    @abstractmethod
    def delete(
        self, model_id: str, *, collection_id: str | None = None
    ) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()


class ModelArtifactResource(ModelArtifactResourceBase):
    """Resource for managing Model Artifacts."""

    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    @validate_collection
    def get(
        self, model_value: str, *, collection_id: str | None = None
    ) -> ModelArtifact | None:
        """
        Get model artifact by ID or name.

        Retrieves model artifact details by its ID or name (model_name or file_name).
        Search by name is case-sensitive and matches exact model or file name.
        If collection_id is None, uses the default collection from client.

        Args:
            model_value: The ID or exact name of the model artifact to retrieve.
            collection_id: ID of the collection to search in. If not provided,
                uses the default collection set in the client.

        Returns:
            ModelArtifact object.

            Returns None if model artifact with the specified ID or name is not found.

        Raises:
            MultipleResourcesFoundError: If there are several model artifacts
                with that name.
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        model_by_name = luml.model_artifacts.get("my_model")
        model_by_id = luml.model_artifacts.get(
            "0199c455-21ee-74c6-b747-19a82f1a1e67"
        )
        ```

        Example response:
        ```python
        ModelArtifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            model_name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            status=ModelArtifactStatus.UPLOADED,
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
        if is_uuid(model_value):
            return self._get_by_id(collection_id, model_value)
        return self._get_by_name(collection_id, model_value)

    def _get_by_name(
        self, collection_id: str | None, name: str
    ) -> ModelArtifact | None:
        return find_by_value(
            self.list(collection_id=collection_id),
            name,
            condition=lambda m: m.model_name == name or m.file_name == name,
        )

    def _get_by_id(
        self, collection_id: str | None, model_value: str
    ) -> ModelArtifact | None:
        for model in self.list(collection_id=collection_id):
            if model.id == model_value:
                return model
        return None

    @validate_collection
    def list(self, *, collection_id: str | None = None) -> list[ModelArtifact]:
        """
        List all model artifacts in the collection.

        If collection_id is None, uses the default collection from client.

        Args:
            collection_id: ID of the collection to list models from. If not provided,
                uses the default collection set in the client.

        Returns:
            List of ModelArtifact objects.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        models = luml.model_artifacts.list()
        ```

        Example response:
        ```python
        [
            ModelArtifact(
                id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                model_name="my_model",
                file_name="model.fnnx",
                description="Trained model",
                collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                status=ModelArtifactStatus.UPLOADED,
                tags=["ml", "production"],
                created_at='2025-01-15T10:30:00.123456Z',
                updated_at=None
            )
        ]
        ```
        """
        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts"
        )
        if response is None:
            return []
        return [ModelArtifact.model_validate(model) for model in response]

    @validate_collection
    def download_url(self, model_id: str, *, collection_id: str | None = None) -> dict:
        """Get download URL for model artifact.

        Generates a secure download URL for the model file.
        If collection_id is None, uses the default collection from client.

        Args:
            model_id: ID of the model artifact to download.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            Dictionary containing the download URL.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If model artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        url_info = luml.model_artifacts.download_url(
            "0199c455-21ee-74c6-b747-19a82f1a1e67"
        )
        download_url = url_info["url"]
        ```
        """
        return self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}/download-url"
        )

    @validate_collection
    def delete_url(self, model_id: str, *, collection_id: str | None = None) -> dict:
        """Get delete URL for model artifact.

        Generates a secure delete URL for the model file in storage.
        If collection_id is None, uses the default collection from client.

        Args:
            model_id: ID of the model artifact to delete from storage.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            Dictionary containing the delete URL.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If model artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        url_info = luml.model_artifacts.delete_url(
            "0199c455-21ee-74c6-b747-19a82f1a1e67"
        )
        ```
        """
        return self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}/delete-url"
        )

    @validate_collection
    def upload(
        self,
        file_path: str,
        model_name: str,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: str | None = None,
    ) -> ModelArtifact:
        """Upload model artifact file to the collection.

        Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
        If collection_id is None, uses the default collection from client.

        Args:
            file_path: Path to the local model file to upload.
            model_name: Name for the model artifact.
            description: Optional description of the model.
            tags: Optional list of tags for organizing models.
            collection_id: ID of the collection to upload to. If not provided,
                uses the default collection set in the client.

        Returns:
            ModelArtifact: Uploaded model artifact object with
                UPLOADED or UPLOAD_FAILED status.

        Raises:
            FileError: If file size exceeds 5GB or unsupported format.
            FileUploadError: If upload to storage fails.
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        model = luml.model_artifacts.upload(
            file_path="/path/to/model.fnnx",
            model_name="Production Model",
            description="Trained on latest dataset",
            tags=["ml", "production"],
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        ```

        Response object:
        ```python
        ModelArtifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            file_name="output.dfs",
            model_name="500mb",
            description=None,
            metrics={
                'F1': 0.9598319029897976,
                'ACC': 0.9600000000000002,
                'BACC': 0.96,
                'B_F1': 0.9598319029897976,
                'SCORE': 0.96
            },
            manifest={
                'variant': 'pipeline',
                'name': None,
                'version': None,
                'description': '',
                'producer_name': 'falcon.beastbyte.ai',
                'producer_version': '0.8.0'
            },
            file_hash='b128c34757114835c4bf690a87e7cbe',
            size=524062720,
            unique_identifier='b31fa3cb54aa453d9ca625aa24617e7a',
            status=ModelArtifactStatus.UPLOADED,
            tags=None,
            created_at='2025-08-25T09:15:15.524206Z',
            updated_at='2025-08-25T09:16:05.816506Z'
        )
        ```
        """
        model_details = ModelFileHandler(file_path).model_details()

        file_format = model_details.file_name.split(".")[1]
        if file_format not in ["fnnx", "pyfnx", "dfs"]:
            raise FileError("File format error")

        created_model_data = self.create(
            file_name=model_details.file_name,
            metrics=model_details.metrics,
            manifest=model_details.manifest,
            file_hash=model_details.file_hash,
            file_index=model_details.file_index,
            size=model_details.size,
            model_name=model_name,
            description=description,
            tags=tags,
            collection_id=collection_id,
        )
        model = created_model_data.model

        try:
            upload_details = created_model_data.upload_details

            if upload_details.multipart:
                upload_id = file_handler.initiate_multipart_upload(upload_details.url)

                if not upload_id:
                    raise LumlAPIError("Failed to initiate multipart upload")

                multipart_urls = self._client.bucket_secrets.get_multipart_upload_urls(
                    upload_details.bucket_secret_id,
                    upload_details.bucket_location,
                    model_details.size,
                    upload_id,
                )

                response = file_handler.upload_multipart(
                    parts=multipart_urls.parts,
                    complete_url=multipart_urls.complete_url,
                    file_size=model.size,
                    file_path=file_path,
                    file_name=model.file_name,
                )
            else:
                response = file_handler.upload_simple_file_with_progress(
                    url=upload_details.url,
                    file_path=file_path,
                    file_size=model.size,
                    file_name=model.file_name,
                )

            status = (
                ModelArtifactStatus.UPLOADED
                if response.status_code == 200
                else ModelArtifactStatus.UPLOAD_FAILED
            )
        except FileUploadError as error:
            self.update(
                model_id=model.id,
                status=ModelArtifactStatus.UPLOAD_FAILED,
                collection_id=collection_id,
            )
            raise error

        return self.update(
            model_id=model.id,
            status=status,
            collection_id=collection_id,
        )

    @validate_collection
    def download(
        self,
        model_id: str,
        file_path: str | None = None,
        *,
        collection_id: str | None = None,
    ) -> None:
        """Download model artifact file from the collection.

        Downloads the model file to local storage with progress tracking.
        If collection_id is None, uses the default collection from client.

        Args:
            model_id: ID of the model artifact to download.
            file_path: Local path to save the downloaded file. If None,
                uses the original file name.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            None: File is saved to the specified path.

        Raises:
            ValueError: If model with specified ID not found.
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        # Download with original filename
        luml.model_artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e67")

        # Download to specific path
        luml.model_artifacts.download(
            "0199c455-21ee-74c6-b747-19a82f1a1e67",
            file_path="/local/path/downloaded_model.fnnx",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        ```
        """
        if file_path is None:
            model = self._get_by_id(collection_id=collection_id, model_value=model_id)
            if model is None:
                raise ValueError(f"Model with id {model_id} not found")
            file_path = model.file_name

        download_info = self.download_url(
            model_id=model_id, collection_id=collection_id
        )
        download_url = download_info["url"]

        file_handler.download_file_with_progress(
            url=download_url,
            file_path=file_path,
            file_name=f'model id="{model_id}"',
        )

    @validate_collection
    def create(
        self,
        collection_id: str | None,
        file_name: str,
        metrics: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> CreatedModel:
        """Create new model artifact record with upload URL.

        Creates a model artifact record and returns an upload URL for file storage.
        If collection_id is None, uses the default collection from client.

        Args:
            collection_id: ID of the collection to create model in.
            file_name: Name of the model file.
            metrics: Model performance metrics.
            manifest: Model manifest with metadata.
            file_hash: SHA hash of the model file.
            file_index: File index mapping for efficient access.
            size: Size of the model file in bytes.
            model_name: Optional name for the model.
            description: Optional description.
            tags: Optional list of tags.

        Returns:
            Dictionary containing upload URL and created ModelArtifact object.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        result = luml.model_artifacts.create(
            file_name="model.fnnx",
            metrics={"accuracy": 0.95},
            manifest={"version": "1.0"},
            file_hash="abc123",
            file_index={"layer1": (0, 1024)},
            size=1048576,
            model_name="Test Model"
        )
        upload_url = result.url
        model = result.model
        ```
        """
        response = self._client.post(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts",
            json={
                "file_name": file_name,
                "metrics": metrics,
                "manifest": manifest,
                "file_hash": file_hash,
                "file_index": file_index,
                "size": size,
                "model_name": model_name,
                "description": description,
                "tags": tags,
            },
        )
        return CreatedModel.model_validate(response)

    @validate_collection
    def update(
        self,
        model_id: str,
        file_name: str | None = None,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: ModelArtifactStatus | None = None,
        *,
        collection_id: str | None = None,
    ) -> ModelArtifact:
        """
        Update model artifact metadata.

        Updates the model artifact's metadata. Only provided parameters will be
        updated, others remain unchanged. If collection_id is None,
            uses the default collection from client.

        Args:
            model_id: ID of the model artifact to update.
            file_name: New file name.
            model_name: New model name.
            description: New description.
            tags: New list of tags.
            status: "pending_upload" | "uploaded" | "upload_failed" | "deletion_failed"
            collection_id: ID of the collection containing the model. Optional.

        Returns:
            ModelArtifact: Updated model artifact object.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If model artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        model = luml.model_artifacts.update(
            "0199c455-21ee-74c6-b747-19a82f1a1e67",
            model_name="Updated Model",
            status=ModelArtifactStatus.UPLOADED
        )
        ```
        """
        return self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}",
            json=self._client.filter_none(
                {
                    "file_name": file_name,
                    "model_name": model_name,
                    "description": description,
                    "tags": tags,
                    "status": status.value if status else None,
                }
            ),
        )

    @validate_collection
    def delete(self, model_id: str, *, collection_id: str | None = None) -> None:
        """Delete model artifact permanently.

        Permanently removes the model artifact record and associated file from storage.
        This action cannot be undone. If collection_id is None,
            uses the default collection from client.

        Args:
            model_id: ID of the model artifact to delete.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            None: No return value on successful deletion.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If model artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        luml.model_artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e67")
        ```

        Warning:
            This operation is irreversible. The model file and all metadata
            will be permanently lost from database, but you can still
                find model in your storage.
        """
        return self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}"
        )


class AsyncModelArtifactResource(ModelArtifactResourceBase):
    """Resource for managing Model Artifacts for async client."""

    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    @validate_collection
    async def get(
        self, model_value: str, *, collection_id: str | None = None
    ) -> ModelArtifact | None:
        """
        Get model artifact by ID or name.

        Retrieves model artifact details by its ID or name (model_name or file_name).
        Search by name is case-sensitive and matches exact model or file name.
        If collection_id is None, uses the default collection from client.

        Args:
            model_value: The ID or exact name of the model artifact to retrieve.
            collection_id: ID of the collection to search in. If not provided,
                uses the default collection set in the client.

        Returns:
            ModelArtifact object.

            Returns None if model artifact with the specified ID or name is not found.

        Raises:
            MultipleResourcesFoundError: If there are several model artifacts
                with that name.
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
            model_by_name = await luml.model_artifacts.get("my_model")
            model_by_id = await luml.model_artifacts.get(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )
        ```

        Example response:
        ```python
        ModelArtifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            model_name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            status=ModelArtifactStatus.UPLOADED,
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
        if is_uuid(model_value):
            return await self._get_by_id(collection_id, model_value)
        return await self._get_by_name(collection_id, model_value)

    async def _get_by_name(
        self, collection_id: str | None, name: str
    ) -> ModelArtifact | None:
        return find_by_value(
            await self.list(collection_id=collection_id),
            name,
            condition=lambda m: m.model_name == name or m.file_name == name,
        )

    async def _get_by_id(
        self, collection_id: str | None, model_value: str
    ) -> ModelArtifact | None:
        for model in await self.list(collection_id=collection_id):
            if model.id == model_value:
                return model
        return None

    @validate_collection
    async def list(self, *, collection_id: str | None = None) -> list[ModelArtifact]:
        """
        List all model artifacts in the collection.

        If collection_id is None, uses the default collection from client.

        Args:
            collection_id: ID of the collection to list models from. If not provided,
                uses the default collection set in the client.

        Returns:
            List of ModelArtifact objects.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
            models = await luml.model_artifacts.list()
        ```

        Example response:
        ```python
        [
            ModelArtifact(
                id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                model_name="my_model",
                file_name="model.fnnx",
                description="Trained model",
                collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                status=ModelArtifactStatus.UPLOADED,
                tags=["ml", "production"],
                created_at='2025-01-15T10:30:00.123456Z',
                updated_at=None
            )
        ]
        ```
        """
        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts"
        )
        if response is None:
            return []
        return [ModelArtifact.model_validate(model) for model in response]

    @validate_collection
    async def download_url(
        self, model_id: str, *, collection_id: str | None = None
    ) -> dict:
        """
        Get download URL for model artifact.

        Generates a secure download URL for the model file.
        If collection_id is None, uses the default collection from client.

        Args:
            model_id: ID of the model artifact to download.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            Dictionary containing the download URL.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If model artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
           await  luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
            url_info = await luml.model_artifacts.download_url(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )
        ```
        """
        return await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}/download-url"
        )

    @validate_collection
    async def delete_url(
        self, model_id: str, *, collection_id: str | None = None
    ) -> dict:
        """
        Get delete URL for model artifact.

        Generates a secure delete URL for the model file in storage.
        If collection_id is None, uses the default collection from client.

        Args:
            model_id: ID of the model artifact to delete from storage.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            Dictionary containing the delete URL.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If model artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
            url_info = await luml.model_artifacts.delete_url(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )
        ```
        """
        return await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}/delete-url"
        )

    @validate_collection
    async def create(
        self,
        collection_id: str | None,
        file_name: str,
        metrics: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> CreatedModel:
        """
        Create new model artifact record with upload URL.

        Creates a model artifact record and returns an upload URL for file storage.
        If collection_id is None, uses the default collection from client

        Args:
            collection_id: ID of the collection to create model in.
            file_name: Name of the model file.
            metrics: Model performance metrics.
            manifest: Model manifest with metadata.
            file_hash: SHA hash of the model file.
            file_index: File index mapping for efficient access.
            size: Size of the model file in bytes.
            model_name: Optional name for the model.
            description: Optional description.
            tags: Optional list of tags.

        Returns:
            Dictionary containing upload URL and created ModelArtifact object.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )

            result = await luml.model_artifacts.create(
                file_name="model.fnnx",
                metrics={"accuracy": 0.95},
                manifest={"version": "1.0"},
                file_hash="abc123",
                file_index={"layer1": (0, 1024)},
                size=1048576,
                model_name="Test Model"
            )
        ```


        Response object:
        ```python
            CreatedModel(
                model=ModelArtifact(
                     id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                     model_name="Production Model",
                     file_name="my_llm_attachments.pyfnx",
                     description="Trained on latest dataset",
                     collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                     status=ModelArtifactStatus.UPLOADED,
                     tags=["ml", "production"],
                     created_at='2025-01-15T10:30:00.123456Z',
                     updated_at='2025-01-15T10:35:00.123456Z'),
                upload_details=UploadDetails(
                    url=" https://luml-models.s3.eu-north-1.amazonaws.com/my_llm_attachments.pyfnx",
                    multipart=False,
                    bucket_location="my_llm_attachments.pyfnx",
                    bucket_secret_id="0199c455-21ee-74c6-b747-19a82f1a1873"))
        ```
        """
        response = await self._client.post(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts",
            json={
                "file_name": file_name,
                "metrics": metrics,
                "manifest": manifest,
                "file_hash": file_hash,
                "file_index": file_index,
                "size": size,
                "model_name": model_name,
                "description": description,
                "tags": tags,
            },
        )

        return CreatedModel.model_validate(response)

    @validate_collection
    async def upload(
        self,
        file_path: str,
        model_name: str,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: str | None = None,
    ) -> ModelArtifact:
        """Upload model artifact file to the collection.

        Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
        Maximum file size is 5GB. If collection_id is None,
            uses the default collection from client.

        Args:
            file_path: Path to the local model file to upload.
            model_name: Name for the model artifact.
            description: Optional description of the model.
            tags: Optional list of tags for organizing models.
            collection_id: ID of the collection to upload to. If not provided,
                uses the default collection set in the client.

        Returns:
            ModelArtifact: Uploaded model artifact object with
                UPLOADED or UPLOAD_FAILED status.

        Raises:
            FileError: If file size exceeds 5GB or unsupported format.
            FileUploadError: If upload to storage fails.
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
            model = await luml.model_artifacts.upload(
                file_path="/path/to/model.fnnx",
                model_name="Production Model",
                description="Trained on latest dataset",
                tags=["ml", "production"],
                collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
        ```

        Response object:
        ```python
            CreatedModel(
                model=ModelArtifact(
                     id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                     model_name="Production Model",
                     file_name="model.fnnx",
                     description="Trained on latest dataset",
                     collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                     status=ModelArtifactStatus.UPLOADED,
                     tags=["ml", "production"],
                     created_at='2025-01-15T10:30:00.123456Z',
                     updated_at='2025-01-15T10:35:00.123456Z'),
                upload_details=UploadDetails(
                    url=" https://luml-models.s3.eu-north-1.amazonaws.com/my_llm_attachments.pyfnx",
                    multipart=False,
                    bucket_location="my_llm_attachments.pyfnx",
                    bucket_secret_id="0199c455-21ee-74c6-b747-19a82f1a1873"))
        ```
        """
        model_details = ModelFileHandler(file_path).model_details()

        file_format = model_details.file_name.split(".")[1]
        if file_format not in ["fnnx", "pyfnx", "dfs"]:
            raise FileError("File format error")

        created_model_data = await self.create(
            file_name=model_details.file_name,
            metrics=model_details.metrics,
            manifest=model_details.manifest,
            file_hash=model_details.file_hash,
            file_index=model_details.file_index,
            size=model_details.size,
            model_name=model_name,
            description=description,
            tags=tags,
            collection_id=collection_id,
        )
        model = created_model_data.model
        try:
            upload_details = created_model_data.upload_details

            if upload_details.multipart:
                upload_id = file_handler.initiate_multipart_upload(upload_details.url)

                if not upload_id:
                    raise LumlAPIError("Failed to initiate multipart upload")

                multipart_urls = (
                    await self._client.bucket_secrets.get_multipart_upload_urls(
                        upload_details.bucket_secret_id,
                        upload_details.bucket_location,
                        model.size,
                        upload_id,
                    )
                )

                response = file_handler.upload_multipart(
                    parts=multipart_urls.parts,
                    complete_url=multipart_urls.complete_url,
                    file_size=model.size,
                    file_path=file_path,
                    file_name=model.file_name,
                )
            else:
                response = file_handler.upload_simple_file_with_progress(
                    url=upload_details.url,
                    file_path=file_path,
                    file_size=model.size,
                    file_name=model.file_name,
                )

            status = (
                ModelArtifactStatus.UPLOADED
                if response.status_code == 200
                else ModelArtifactStatus.UPLOAD_FAILED
            )
        except FileUploadError as error:
            await self.update(
                model.id,
                status=ModelArtifactStatus.UPLOAD_FAILED,
                collection_id=collection_id,
            )
            raise error

        return await self.update(model.id, status=status, collection_id=collection_id)

    @validate_collection
    async def download(
        self,
        model_id: str,
        file_path: str | None = None,
        *,
        collection_id: str | None = None,
    ) -> None:
        """
        Download model artifact file from the collection.

        Downloads the model file to local storage with progress tracking.
        If collection_id is None, uses the default collection from client.

        Args:
            model_id: ID of the model artifact to download.
            file_path: Local path to save the downloaded file. If None,
                uses the original file name.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            None: File is saved to the specified path.

        Raises:
            ValueError: If model with specified ID not found.
            ConfigurationError: If collection_id not provided and
                no default collection set.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )

            # Download with original filename
            await luml.model_artifacts.download(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )

            # Download to specific path
            await luml.model_artifacts.download(
                "0199c455-21ee-74c6-b747-19a82f1a1e67",
                file_path="/local/path/downloaded_model.fnnx",
                collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
        ```
        """
        if file_path is None:
            model = await self._get_by_id(
                collection_id=collection_id, model_value=model_id
            )
            if model is None:
                raise ValueError(f"Model with id {model_id} not found")
            file_path = model.file_name

        download_info = await self.download_url(
            model_id=model_id, collection_id=collection_id
        )
        download_url = download_info["url"]

        file_handler.download_file_with_progress(
            url=download_url,
            file_path=file_path,
            file_name=f'model id="{model_id}"',
        )

    @validate_collection
    async def update(
        self,
        model_id: str,
        file_name: str | None = None,
        model_name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: ModelArtifactStatus | None = None,
        *,
        collection_id: str | None = None,
    ) -> ModelArtifact:
        """
        Update model artifact metadata.

        Updates the model artifact's metadata. Only provided parameters will be
        updated, others remain unchanged. If collection_id is None,
            uses the default collection from client.

        Args:
            model_id: ID of the model artifact to update.
            file_name: New file name.
            model_name: New model name.
            description: New description.
            tags: New list of tags.
            status: "pending_upload" | "uploaded" | "upload_failed" | "deletion_failed"
            collection_id: ID of the collection containing the model. Optional.

        Returns:
            ModelArtifact: Updated model artifact object.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If model artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
            model = await luml.model_artifacts.update(
                "0199c455-21ee-74c6-b747-19a82f1a1e67",
                model_name="Updated Model",
                status=ModelArtifactStatus.UPLOADED
            )
        ```
        """
        return await self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}",
            json=self._client.filter_none(
                {
                    "file_name": file_name,
                    "model_name": model_name,
                    "description": description,
                    "tags": tags,
                    "status": status.value if status else None,
                }
            ),
        )

    @validate_collection
    async def delete(self, model_id: str, *, collection_id: str | None = None) -> None:
        """
        Delete model artifact permanently.

        Permanently removes the model artifact record and associated file from storage.
        This action cannot be undone. If collection_id is None,
            uses the default collection from client

        Args:
            model_id: ID of the model artifact to delete.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client

        Returns:
            None: No return value on successful deletion

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If model artifact with specified ID doesn't exist

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
                collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
            await luml.model_artifacts.delete(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )
        ```

        Warning:
            This operation is irreversible. The model file and all metadata
            will be permanently lost from database, but you can still
            find model in your storage.
        """
        return await self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/model_artifacts/{model_id}"
        )
