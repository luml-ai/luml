import builtins
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Coroutine, Iterator
from typing import TYPE_CHECKING, Any

from luml.api._exceptions import FileError, FileUploadError
from luml.api._types import (
    Artifact,
    ArtifactsList,
    ArtifactStatus,
    ArtifactType,
    CreatedArtifact,
    SortOrder,
    is_uuid,
)
from luml.api._utils import find_by_value
from luml.api.resources._listed_resource import ListedResource
from luml.api.resources._validators import validate_collection
from luml.api.services.upload_service import AsyncUploadService, UploadService
from luml.api.utils.model_artifacts import ModelFileHandler
from luml.api.utils.s3_file_handler import S3FileHandler

if TYPE_CHECKING:
    from luml.api._client import AsyncLumlClient, LumlClient


class ArtifactResourceBase(ABC):
    """Abstract Resource for managing artifacts."""

    @abstractmethod
    def get(
        self, model_value: str | int, *, collection_id: str | None = None
    ) -> Artifact | None | Coroutine[Any, Any, Artifact | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_name(
        self, collection_id: str | None, name: str
    ) -> Artifact | None | Coroutine[Any, Any, Artifact | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_id(
        self, collection_id: str | None, artifact_value: str
    ) -> Artifact | None | Coroutine[Any, Any, Artifact | None]:
        raise NotImplementedError()

    @abstractmethod
    def list(
        self, *, collection_id: str | None = None
    ) -> list[Artifact] | Coroutine[Any, Any, list[Artifact]]:
        raise NotImplementedError()

    @abstractmethod
    def download_url(
        self, artifact_id: str, *, collection_id: str | None = None
    ) -> dict | Coroutine[Any, Any, dict]:
        raise NotImplementedError()

    @abstractmethod
    def delete_url(
        self, artifact_id: str, *, collection_id: str | None = None
    ) -> dict | Coroutine[Any, Any, dict]:
        raise NotImplementedError()

    @abstractmethod
    def upload(
        self,
        file_path: str,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: str | None = None,
    ) -> Artifact | Coroutine[Any, Any, Artifact]:
        raise NotImplementedError()

    @abstractmethod
    def download(
        self,
        artifact_id: str,
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
        extra_values: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        name: str,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> (
        dict[str, str | CreatedArtifact]
        | Coroutine[Any, Any, dict[str, str | CreatedArtifact]]
    ):
        raise NotImplementedError()

    @abstractmethod
    def update(
        self,
        artifact_id: str,
        file_name: str | None = None,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: ArtifactStatus | None = None,
        *,
        collection_id: str | None = None,
    ) -> Artifact | Coroutine[Any, Any, Artifact]:
        raise NotImplementedError()

    @abstractmethod
    def delete(
        self, artifact_id: str, *, collection_id: str | None = None
    ) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()


class ArtifactResource(ArtifactResourceBase, ListedResource):
    """Resource for managing artifacts."""

    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    @validate_collection
    def get(
        self, artifact_value: str, *, collection_id: str | None = None
    ) -> Artifact | None:
        """
        Get artifact by ID or name.

        Retrieves artifact details by its ID or name (name or file_name).
        Search by name is case-sensitive and matches exact model or file name.
        If collection_id is None, uses the default collection from client.

        Args:
            artifact_value: The ID or exact name of the artifact to retrieve.
            collection_id: ID of the collection to search in. If not provided,
                uses the default collection set in the client.

        Returns:
            Artifact object.

            Returns None if artifact with the specified ID or name is not found.

        Raises:
            MultipleResourcesFoundError: If there are several artifacts
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
        artifact_by_name = luml.artifacts.get("my_model")
        artifact_by_id = luml.artifacts.get(
            "0199c455-21ee-74c6-b747-19a82f1a1e67"
        )
        ```

        Example response:
        ```python
        Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
        if is_uuid(artifact_value):
            return self._get_by_id(collection_id, artifact_value)
        return self._get_by_name(collection_id, artifact_value)

    def _get_by_name(self, collection_id: str | None, name: str) -> Artifact | None:
        return find_by_value(
            self.list(collection_id=collection_id).items,
            name,
            condition=lambda m: m.name == name or m.file_name == name,
        )

    def _get_by_id(
        self, collection_id: str | None, artifact_value: str
    ) -> Artifact | None:
        for model in self.list(collection_id=collection_id).items:
            if model.id == artifact_value:
                return model
        return None

    @validate_collection
    def list_all(
        self,
        *,
        collection_id: str | None = None,
        limit: int | None = 100,
        sort_by: str | None = None,
        order: SortOrder = SortOrder.DESC,
        artifact_type: ArtifactType | None = None,
    ) -> Iterator[Artifact]:
        """
        List all collection artifacts with auto-paging.

        Args:
            collection_id: ID of the collection to list models from. If not provided,
                uses the default collection set in the client.
            limit: Page size (default: 100).
            sort_by: Field to sort by.
                Options: name, created_at, size, description, status
                and any metric key
            order: Sort order - "asc" or "desc" (default: "desc").
            artifact_type: Filter by artifact type: "model", "dataset", or "experiment".

        Returns:
            Artifact objects from all pages.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )

        # List all artifacts with default sorting
        for artifact in luml.artifacts.list_all(limit=50):
            print(artifact.id)

        # List all artifacts sorted by F1 metric
        for artifact in luml.artifacts.list_all(
            sort_by="F1",
            order="desc",
            limit=50
        ):
            print(f"{artifact.name}: F1={artifact.metrics.get('F1')}")

        # Filter by artifact type
        for artifact in luml.artifacts.list_all(artifact_type=ArtifactType.MODEL):
            print(artifact.name)
        ```
        """
        return self._auto_paginate(
            self.list,
            collection_id=collection_id,
            limit=limit,
            sort_by=sort_by,
            order=order,
            artifact_type=artifact_type,
        )

    @validate_collection
    def list(
        self,
        *,
        collection_id: str | None = None,
        start_after: str | None = None,
        limit: int | None = 100,
        sort_by: str | None = None,
        order: SortOrder = SortOrder.DESC,
        artifact_type: ArtifactType | None = None,
    ) -> ArtifactsList:
        """
        List all artifacts in the collection.

        If collection_id is None, uses the default collection from client.

        Args:
            collection_id: ID of the collection to list models from. If not provided,
                uses the default collection set in the client.
            start_after: ID of the artifact to start listing from.
            limit: Limit number of models per page (default: 100).
            sort_by: Field to sort by.
                Options: name, created_at, size, description, status
                and any metric key
            order: Sort order - "asc" or "desc" (default: "desc").
            artifact_type: Filter by artifact type: "model", "dataset", or "experiment".

        Returns:
            ArtifactList object.

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
        # Default: sorted by creation time, newest first
        artifacts = luml.artifacts.list()

        # Sort by size
        artifacts = luml.artifacts.list(
            sort_by="size",
            order="desc"
        )

        # Sort by a specific metric (e.g., F1 score)
        artifacts = luml.artifacts.list(
            sort_by="F1",
            order="desc"
        )

        # Filter by artifact type
        artifacts = luml.artifacts.list(artifact_type=ArtifactType.MODEL)
        ```

        Example response:
        ```python
        ArtifactsList(
            items=[
                Artifact(
                    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                    name="my_model",
                    file_name="model.fnnx",
                    description="Trained model",
                    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
                    manifest={
                        "variant": "pipeline",
                        "name": None,
                        "version": None,
                        "description": "",
                        "producer_name": "falcon.beastbyte.ai",
                        "producer_version": "0.8.0",
                        "producer_tags": [
                            "falcon.beastbyte.ai::tabular_regression:v1",
                            "dataforce.studio::tabular_regression:v1",
                        ],
                        "inputs": [
                            {
                                "name": "age",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                                "shape": ["batch", 1],
                            },
                        ],
                        "outputs": [
                            {
                                "name": "y_pred",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": None,
                                "shape": ["batch", 1],
                            }
                        ],
                        "dynamic_attributes": [],
                        "env_vars": [],
                    },
                    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
                    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
                    file_index = {
                        "env.json": (3584, 2),
                        "ops.json": (7168, 1869),
                        "meta.json": (239616, 3279),
                        "dtypes.json": (238592, 2),
                        "manifest.json": (512, 2353),
                        "variant_config.json": (4608, 372),
                        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
                    },
                    size=245760,
                    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
                    status='pending_upload',
                    type='model',
                    tags=["ml", "production"],
                    created_at='2025-01-15T10:30:00.123456Z',
                    updated_at=None
                )
            ],
            cursor="WyIwMTliNDYxZmNmZDk3NTNhYjMwODJlMDUxZDkzZjVkZiIsICIyMDI1LTEyLTIyVDEyOjU0OjA4LjYwMTI5OCswMDowMCIsICJjcmVhdGVkX2F0Il0="
        )
        ```
        """
        params = {
            "limit": limit,
            "order": order.value if isinstance(order, SortOrder) else order,
        }
        if start_after:
            params["cursor"] = start_after
        if sort_by:
            params["sort_by"] = sort_by
        if artifact_type:
            params["type"] = (
                artifact_type.value
                if isinstance(artifact_type, ArtifactType)
                else artifact_type
            )

        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts",
            params=params,
        )

        if response is None:
            return ArtifactsList(items=[])

        return ArtifactsList.model_validate(response)

    @validate_collection
    def download_url(
        self, artifact_id: str, *, collection_id: str | None = None
    ) -> dict:
        """Get download URL for artifact.

        Generates a secure download URL for the model file.
        If collection_id is None, uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to download.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            Dictionary containing the download URL.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        url_info = luml.artifacts.download_url(
            "0199c455-21ee-74c6-b747-19a82f1a1e67"
        )
        download_url = url_info["url"]
        ```
        """
        return self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts/{artifact_id}/download-url"
        )

    @validate_collection
    def delete_url(self, artifact_id: str, *, collection_id: str | None = None) -> dict:
        """Get delete URL for artifact.

        Generates a secure delete URL for the model file in storage.
        If collection_id is None, uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to delete from storage.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            Dictionary containing the delete URL.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        url_info = luml.artifacts.delete_url(
            "0199c455-21ee-74c6-b747-19a82f1a1e67"
        )
        ```
        """
        return self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts/{artifact_id}/delete-url"
        )

    @validate_collection
    def upload(
        self,
        file_path: str,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: str | None = None,
    ) -> Artifact:
        """Upload artifact file to the collection.

        Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
        If collection_id is None, uses the default collection from client.

        Args:
            file_path: Path to the local model file to upload.
            name: Name for the artifact. If not provided, uses the file name.
            description: Optional description of the model.
            tags: Optional list of tags for organizing models.
            collection_id: ID of the collection to upload to. If not provided,
                uses the default collection set in the client.

        Returns:
            Artifact: Uploaded artifact object with
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
        artifact = luml.artifacts.upload(
            file_path="/path/to/model.fnnx",
            name="Production Model",
            description="Trained on latest dataset",
            tags=["ml", "production"],
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        ```

        Response object:
        ```python
        Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
        artifact_details = ModelFileHandler(file_path).artifact_details()

        file_format = artifact_details.file_name.split(".")[1]
        if file_format not in ["fnnx", "pyfnx", "dfs", "luml"]:
            raise FileError("File format error")

        if name is None:
            name = artifact_details.file_name

        created_artifact_data = self.create(
            file_name=artifact_details.file_name,
            extra_values=artifact_details.extra_values,
            manifest=artifact_details.manifest,
            file_hash=artifact_details.file_hash,
            file_index=artifact_details.file_index,
            size=artifact_details.size,
            name=name,
            description=description,
            tags=tags,
            collection_id=collection_id,
        )
        artifact = created_artifact_data.artifact

        try:
            upload_service = UploadService(self._client.bucket_secrets)

            response = upload_service.upload_file(
                upload_details=created_artifact_data.upload_details,
                file_path=file_path,
                file_size=artifact.size,
                file_name=artifact.file_name,
            )

            status = (
                ArtifactStatus.UPLOADED
                if 200 <= response.status_code < 300
                else ArtifactStatus.UPLOAD_FAILED
            )
        except FileUploadError as error:
            self.update(
                artifact_id=artifact.id,
                status=ArtifactStatus.UPLOAD_FAILED,
                collection_id=collection_id,
            )
            raise error

        return self.update(
            artifact_id=artifact.id,
            status=status,
            collection_id=collection_id,
        )

    @validate_collection
    def download(
        self,
        artifact_id: str,
        file_path: str | None = None,
        *,
        collection_id: str | None = None,
    ) -> None:
        """Download artifact file from the collection.

        Downloads the model file to local storage with progress tracking.
        If collection_id is None, uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to download.
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
        luml.artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e67")

        # Download to specific path
        luml.artifacts.download(
            "0199c455-21ee-74c6-b747-19a82f1a1e67",
            file_path="/local/path/downloaded_model.fnnx",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        ```
        """
        if file_path is None:
            artifact = self._get_by_id(
                collection_id=collection_id, artifact_value=artifact_id
            )
            if artifact is None:
                raise ValueError(f"Artifact with id {artifact_id} not found")
            file_path = artifact.file_name

        download_info = self.download_url(
            artifact_id=artifact_id, collection_id=collection_id
        )
        download_url = download_info["url"]

        handler = S3FileHandler()
        handler.download_file_with_progress(
            url=download_url,
            file_path=file_path,
            file_name=f'model id="{artifact_id}"',
        )

    @validate_collection
    def create(
        self,
        collection_id: str | None,
        file_name: str,
        extra_values: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        name: str,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> CreatedArtifact:
        """Create new artifact record with upload URL.

        Creates a artifact record and returns an upload URL for file storage.
        If collection_id is None, uses the default collection from client.

        Args:
            collection_id: ID of the collection to create model in.
            file_name: Name of the model file.
            extra_values: Model extra values (e.g. performance metrics).
            manifest: Model manifest with metadata.
            file_hash: SHA hash of the model file.
            file_index: File index mapping for efficient access.
            size: Size of the model file in bytes.
            name: Optional name for the model.
            description: Optional description.
            tags: Optional list of tags.

        Returns:
            Dictionary containing upload URL and created Artifact object.

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
        result = luml.artifacts.create(
            file_name="model.fnnx",
            extra_values={"accuracy": 0.95},
            manifest={"version": "1.0"},
            file_hash="abc123",
            file_index={"layer1": (0, 1024)},
            size=1048576,
            name="Test Model"
        )
        upload_url = result.url
        artifact = result.artifact
        ```

        Response object:
        ```python
            CreatedArtifact(
                artifact=Artifact(
                    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                    name="my_model",
                    file_name="model.fnnx",
                    description="Trained model",
                    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
                    manifest={
                        "variant": "pipeline",
                        "name": None,
                        "version": None,
                        "description": "",
                        "producer_name": "falcon.beastbyte.ai",
                        "producer_version": "0.8.0",
                        "producer_tags": [
                            "falcon.beastbyte.ai::tabular_regression:v1",
                            "dataforce.studio::tabular_regression:v1",
                        ],
                        "inputs": [
                            {
                                "name": "age",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                                "shape": ["batch", 1],
                            },
                        ],
                        "outputs": [
                            {
                                "name": "y_pred",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": None,
                                "shape": ["batch", 1],
                            }
                        ],
                        "dynamic_attributes": [],
                        "env_vars": [],
                    },
                    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
                    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
                    file_index = {
                        "env.json": (3584, 2),
                        "ops.json": (7168, 1869),
                        "meta.json": (239616, 3279),
                        "dtypes.json": (238592, 2),
                        "manifest.json": (512, 2353),
                        "variant_config.json": (4608, 372),
                        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
                    },
                    size=245760,
                    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
                    status='pending_upload',
                    type='model',
                    tags=["ml", "production"],
                    created_at='2025-01-15T10:30:00.123456Z',
                    updated_at=None
                ),
                upload_details=UploadDetails(
                    url=" https://luml-models.s3.eu-north-1.amazonaws.com/my_llm_attachments.pyfnx",
                    multipart=False,
                    bucket_location="my_llm_attachments.pyfnx",
                    bucket_secret_id="0199c455-21ee-74c6-b747-19a82f1a1873"
                )
            )
        ```
        """
        response = self._client.post(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts",
            json={
                "file_name": file_name,
                "extra_values": extra_values,
                "manifest": manifest,
                "file_hash": file_hash,
                "file_index": file_index,
                "size": size,
                "name": name,
                "description": description,
                "tags": tags,
            },
        )
        return CreatedArtifact.model_validate(response)

    @validate_collection
    def update(
        self,
        artifact_id: str,
        file_name: str | None = None,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: ArtifactStatus | None = None,
        *,
        collection_id: str | None = None,
    ) -> Artifact:
        """
        Update artifact metadata.

        Updates the artifact's metadata. Only provided parameters will be
        updated, others remain unchanged. If collection_id is None,
            uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to update.
            file_name: New file name.
            name: New model name.
            description: New description.
            tags: New list of tags.
            status: "pending_upload" | "uploaded" | "upload_failed" | "deletion_failed"
            collection_id: ID of the collection containing the model. Optional.

        Returns:
            Artifact: Updated artifact object.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        artifact = luml.artifacts.update(
            "0199c455-21ee-74c6-b747-19a82f1a1e67",
            name="Updated Model",
            status="uploaded"
        )
        ```

        Example response:
        ```python
        Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        """
        return self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts/{artifact_id}",
            json=self._client.filter_none(
                {
                    "file_name": file_name,
                    "name": name,
                    "description": description,
                    "tags": tags,
                    "status": status.value if status else None,
                }
            ),
        )

    @validate_collection
    def delete(self, artifact_id: str, *, collection_id: str | None = None) -> None:
        """Delete artifact permanently.

        Permanently removes the artifact record and associated file from storage.
        This action cannot be undone. If collection_id is None,
            uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to delete.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            None: No return value on successful deletion.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If artifact with specified ID doesn't exist.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        luml.artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e67")
        ```

        Warning:
            This operation is irreversible. The model file and all metadata
            will be permanently lost from database, but you can still
                find model in your storage.
        """
        return self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts/{artifact_id}"
        )


class AsyncArtifactResource(ArtifactResourceBase, ListedResource):
    """Resource for managing artifacts for async client."""

    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    @validate_collection
    async def get(
        self, artifact_value: str, *, collection_id: str | None = None
    ) -> Artifact | None:
        """
        Get artifact by ID or name.

        Retrieves artifact details by its ID or name (name or file_name).
        Search by name is case-sensitive and matches exact model or file name.
        If collection_id is None, uses the default collection from client.

        Args:
            artifact_value: The ID or exact name of the artifact to retrieve.
            collection_id: ID of the collection to search in. If not provided,
                uses the default collection set in the client.

        Returns:
            Artifact object.

            Returns None if artifact with the specified ID or name is not found.

        Raises:
            MultipleResourcesFoundError: If there are several artifacts
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
            artifact_by_name = await luml.artifacts.get("my_model")
            artifact_by_id = await luml.artifacts.get(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )
        ```

        Example response:
        ```python
        Artifact(
            id="0199c455-21ee-74c6-b747-19a82f1a1e67",
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="my_model",
            file_name="model.fnnx",
            description="Trained model",
            metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
            manifest={
                "variant": "pipeline",
                "name": None,
                "version": None,
                "description": "",
                "producer_name": "falcon.beastbyte.ai",
                "producer_version": "0.8.0",
                "producer_tags": [
                    "falcon.beastbyte.ai::tabular_regression:v1",
                    "dataforce.studio::tabular_regression:v1",
                ],
                "inputs": [
                    {
                        "name": "age",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": ["falcon.beastbyte.ai::numeric:v1"],
                        "shape": ["batch", 1],
                    },
                ],
                "outputs": [
                    {
                        "name": "y_pred",
                        "content_type": "NDJSON",
                        "dtype": "Array[float32]",
                        "tags": None,
                        "shape": ["batch", 1],
                    }
                ],
                "dynamic_attributes": [],
                "env_vars": [],
            },
            bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
            file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
            file_index = {
                "env.json": (3584, 2),
                "ops.json": (7168, 1869),
                "meta.json": (239616, 3279),
                "dtypes.json": (238592, 2),
                "manifest.json": (512, 2353),
                "variant_config.json": (4608, 372),
                "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
            },
            size=245760,
            unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
            status='pending_upload',
            type='model',
            tags=["ml", "production"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
        if is_uuid(artifact_value):
            return await self._get_by_id(collection_id, artifact_value)
        return await self._get_by_name(collection_id, artifact_value)

    async def _get_by_name(
        self, collection_id: str | None, name: str
    ) -> Artifact | None:
        return find_by_value(
            (await self.list(collection_id=collection_id)).items,
            name,
            condition=lambda m: m.name == name or m.file_name == name,
        )

    async def _get_by_id(
        self, collection_id: str | None, artifact_value: str
    ) -> Artifact | None:
        for model in (await self.list(collection_id=collection_id)).items:
            if model.id == artifact_value:
                return model
        return None

    @validate_collection
    def list_all(
        self,
        *,
        collection_id: str | None = None,
        limit: int | None = 100,
        sort_by: str | None = None,
        order: SortOrder = SortOrder.DESC,
        artifact_type: ArtifactType | None = None,
    ) -> AsyncIterator[Artifact]:
        """
        List all collection artifacts with auto-paging.

        Args:
            collection_id: ID of the collection to list models from. If not provided,
                uses the default collection set in the client.
            limit: Page size (default: 100).
            sort_by: Field to sort by.
                Options: name, created_at, size, description, status
                and any metric key
            order: Sort order - "asc" or "desc" (default: "desc").
            artifact_type: Filter by artifact type: "model", "dataset", or "experiment".

        Returns:
            Artifact objects from all pages.

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

            # List all artifacts with default sorting
            async for artifact in luml.artifacts.list_all(limit=50):
                print(artifact.id)

            # List all artifacts sorted by F1 metric
            async for artifact in luml.artifacts.list_all(
                sort_by="F1",
                order="desc",
                limit=50
            ):
                print(f"{artifact.name}: F1={artifact.metrics.get('F1')}")

            # Filter by artifact type
            async for artifact in luml.artifacts.list_all(
                artifact_type=ArtifactType.MODEL
            ):
                print(artifact.name)
        ```
        """
        return self._auto_paginate_async(
            self.list,
            collection_id=collection_id,
            limit=limit,
            sort_by=sort_by,
            order=order,
            artifact_type=artifact_type,
        )

    @validate_collection
    async def list(
        self,
        *,
        collection_id: str | None = None,
        start_after: str | None = None,
        limit: int | None = 100,
        sort_by: str | None = None,
        order: SortOrder = SortOrder.DESC,
        artifact_type: ArtifactType | None = None,
    ) -> ArtifactsList:
        """
        List all artifacts in the collection.

        If collection_id is None, uses the default collection from client.

        Args:
            collection_id: ID of the collection to list models from. If not provided,
                uses the default collection set in the client.
            start_after: ID of the artifact to start listing from.
            limit: Limit number of models per page (default: 100).
            sort_by: Field to sort by.
                Options: name, created_at, size, description, status
                and any metric key
            order: Sort order - "asc" or "desc" (default: "desc").
            artifact_type: Filter by artifact type: "model", "dataset", or "experiment".

        Returns:
            ArtifactsList object.

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
            # Default: sorted by creation time, newest first
            artifacts = await luml.artifacts.list()

            # Sort by size
            artifacts = await luml.artifacts.list(
                sort_by="size",
                order="asc"
            )

            # Sort by a specific metric (e.g., F1 score)
            artifacts = await luml.artifacts.list(
                sort_by="F1",
                order="desc"
            )

            # Filter by artifact type
            artifacts = await luml.artifacts.list(artifact_type=ArtifactType.MODEL)
        ```

        Example response:
        ```python
        ArtifactsList(
            items=[
                Artifact(
                    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                    name="my_model",
                    file_name="model.fnnx",
                    description="Trained model",
                    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
                    manifest={
                        "variant": "pipeline",
                        "name": None,
                        "version": None,
                        "description": "",
                        "producer_name": "falcon.beastbyte.ai",
                        "producer_version": "0.8.0",
                        "producer_tags": [
                            "falcon.beastbyte.ai::tabular_regression:v1",
                            "dataforce.studio::tabular_regression:v1",
                        ],
                        "inputs": [
                            {
                                "name": "age",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                                "shape": ["batch", 1],
                            },
                        ],
                        "outputs": [
                            {
                                "name": "y_pred",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": None,
                                "shape": ["batch", 1],
                            }
                        ],
                        "dynamic_attributes": [],
                        "env_vars": [],
                    },
                    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
                    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
                    file_index = {
                        "env.json": (3584, 2),
                        "ops.json": (7168, 1869),
                        "meta.json": (239616, 3279),
                        "dtypes.json": (238592, 2),
                        "manifest.json": (512, 2353),
                        "variant_config.json": (4608, 372),
                        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
                    },
                    size=245760,
                    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
                    status='pending_upload',
                    type='model',
                    tags=["ml", "production"],
                    created_at='2025-01-15T10:30:00.123456Z',
                    updated_at=None
                )
            ],
            cursor="WyIwMTliNDYxZmNmZDk3NTNhYjMwODJlMDUxZDkzZjVkZiIsICIyMDI1LTEyLTIyVDEyOjU0OjA4LjYwMTI5OCswMDowMCIsICJjcmVhdGVkX2F0Il0="
        )
        ```
        """

        params = {"limit": limit, "order": order.value}
        if start_after:
            params["cursor"] = start_after
        if sort_by:
            params["sort_by"] = sort_by
        if artifact_type:
            params["type"] = (
                artifact_type.value
                if isinstance(artifact_type, ArtifactType)
                else artifact_type
            )

        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts",
            params=params,
        )
        if response is None:
            return ArtifactsList(items=[])

        return ArtifactsList.model_validate(response)

    @validate_collection
    async def download_url(
        self, artifact_id: str, *, collection_id: str | None = None
    ) -> dict:
        """
        Get download URL for artifact.

        Generates a secure download URL for the model file.
        If collection_id is None, uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to download.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            Dictionary containing the download URL.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If artifact with specified ID doesn't exist.

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
            url_info = await luml.artifacts.download_url(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )
        ```
        """
        return await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts/{artifact_id}/download-url"
        )

    @validate_collection
    async def delete_url(
        self, artifact_id: str, *, collection_id: str | None = None
    ) -> dict:
        """
        Get delete URL for artifact.

        Generates a secure delete URL for the model file in storage.
        If collection_id is None, uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to delete from storage.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client.

        Returns:
            Dictionary containing the delete URL.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If artifact with specified ID doesn't exist.

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
            url_info = await luml.artifacts.delete_url(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )
        ```
        """
        return await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts/{artifact_id}/delete-url"
        )

    @validate_collection
    async def create(
        self,
        collection_id: str | None,
        file_name: str,
        extra_values: dict,
        manifest: dict,
        file_hash: str,
        file_index: dict[str, tuple[int, int]],
        size: int,
        name: str,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> CreatedArtifact:
        """
        Create new artifact record with upload URL.

        Creates a artifact record and returns an upload URL for file storage.
        If collection_id is None, uses the default collection from client

        Args:
            collection_id: ID of the collection to create model in.
            file_name: Name of the model file.
            extra_values: Model extra values (e.g. performance metrics).
            manifest: Model manifest with metadata.
            file_hash: SHA hash of the model file.
            file_index: File index mapping for efficient access.
            size: Size of the model file in bytes.
            name: Optional name for the model.
            description: Optional description.
            tags: Optional list of tags.

        Returns:
            Dictionary containing upload URL and created Artifact object.

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

            result = await luml.artifacts.create(
                file_name="model.fnnx",
                extra_values={"accuracy": 0.95},
                manifest={"version": "1.0"},
                file_hash="abc123",
                file_index={"layer1": (0, 1024)},
                size=1048576,
                name="Test Model"
            )
        ```

        Response object:
        ```python
            CreatedArtifact(
                artifact=Artifact(
                    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                    name="my_model",
                    file_name="model.fnnx",
                    description="Trained model",
                    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
                    manifest={
                        "variant": "pipeline",
                        "name": None,
                        "version": None,
                        "description": "",
                        "producer_name": "falcon.beastbyte.ai",
                        "producer_version": "0.8.0",
                        "producer_tags": [
                            "falcon.beastbyte.ai::tabular_regression:v1",
                            "dataforce.studio::tabular_regression:v1",
                        ],
                        "inputs": [
                            {
                                "name": "age",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                                "shape": ["batch", 1],
                            },
                        ],
                        "outputs": [
                            {
                                "name": "y_pred",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": None,
                                "shape": ["batch", 1],
                            }
                        ],
                        "dynamic_attributes": [],
                        "env_vars": [],
                    },
                    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
                    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
                    file_index = {
                        "env.json": (3584, 2),
                        "ops.json": (7168, 1869),
                        "meta.json": (239616, 3279),
                        "dtypes.json": (238592, 2),
                        "manifest.json": (512, 2353),
                        "variant_config.json": (4608, 372),
                        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
                    },
                    size=245760,
                    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
                    status='pending_upload',
                    type='model',
                    tags=["ml", "production"],
                    created_at='2025-01-15T10:30:00.123456Z',
                    updated_at=None
                ),
                upload_details=UploadDetails(
                    url=" https://luml-models.s3.eu-north-1.amazonaws.com/my_llm_attachments.pyfnx",
                    multipart=False,
                    bucket_location="my_llm_attachments.pyfnx",
                    bucket_secret_id="0199c455-21ee-74c6-b747-19a82f1a1873"
                )
            )
        ```
        """
        response = await self._client.post(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts",
            json={
                "file_name": file_name,
                "extra_values": extra_values,
                "manifest": manifest,
                "file_hash": file_hash,
                "file_index": file_index,
                "size": size,
                "name": name,
                "description": description,
                "tags": tags,
            },
        )
        return CreatedArtifact.model_validate(response)

    @validate_collection
    async def upload(
        self,
        file_path: str,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: str | None = None,
    ) -> Artifact:
        """Upload artifact file to the collection.

        Uploads a model file (.fnnx, .pyfnx, or .dfs format) to the collection storage.
        Maximum file size is 5GB. If collection_id is None,
            uses the default collection from client.

        Args:
            file_path: Path to the local model file to upload.
            name: Name for the artifact. If not provided, uses the file name.
            description: Optional description of the model.
            tags: Optional list of tags for organizing models.
            collection_id: ID of the collection to upload to. If not provided,
                uses the default collection set in the client.

        Returns:
            Artifact: Uploaded model artifact object with
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
            artifact = await luml.artifacts.upload(
                file_path="/path/to/model.fnnx",
                name="Production Model",
                description="Trained on latest dataset",
                tags=["ml", "production"],
                collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
        ```

        Response object:
        ```python
            CreatedArtifact(
                artifact=Artifact(
                    id="0199c455-21ee-74c6-b747-19a82f1a1e67",
                    collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                    name="my_model",
                    file_name="model.fnnx",
                    description="Trained model",
                    metrics={'R2': 0.8449933416622079, 'MAE': 2753.903519270197},
                    manifest={
                        "variant": "pipeline",
                        "name": None,
                        "version": None,
                        "description": "",
                        "producer_name": "falcon.beastbyte.ai",
                        "producer_version": "0.8.0",
                        "producer_tags": [
                            "falcon.beastbyte.ai::tabular_regression:v1",
                            "dataforce.studio::tabular_regression:v1",
                        ],
                        "inputs": [
                            {
                                "name": "age",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": ["falcon.beastbyte.ai::numeric:v1"],
                                "shape": ["batch", 1],
                            },
                        ],
                        "outputs": [
                            {
                                "name": "y_pred",
                                "content_type": "NDJSON",
                                "dtype": "Array[float32]",
                                "tags": None,
                                "shape": ["batch", 1],
                            }
                        ],
                        "dynamic_attributes": [],
                        "env_vars": [],
                    },
                    bucket_location='orbit-0199c8cf-4d35-783b-9f81-cb3cec788074/collection-0199c455-21ee-74c6-b747-19a82f1a1e75/dc2b54d0d41d411da169e8e7d40f94c3-model.fnnx',
                    file_hash='ea1ea069ba4e7979c950b7143413c6b05b07d1c1f97e292d2d8ac909c89141b2',
                    file_index = {
                        "env.json": (3584, 2),
                        "ops.json": (7168, 1869),
                        "meta.json": (239616, 3279),
                        "dtypes.json": (238592, 2),
                        "manifest.json": (512, 2353),
                        "variant_config.json": (4608, 372),
                        "ops_artifacts/onnx_main/model.onnx": (10240, 227540),
                    },
                    size=245760,
                    unique_identifier='dc2b54d0d41d411da169e8e7d40f94c3',
                    status='pending_upload',
                    type='model',
                    tags=["ml", "production"],
                    created_at='2025-01-15T10:30:00.123456Z',
                    updated_at=None
                ),
                upload_details=UploadDetails(
                    url=" https://luml-models.s3.eu-north-1.amazonaws.com/my_llm_attachments.pyfnx",
                    multipart=False,
                    bucket_location="my_llm_attachments.pyfnx",
                    bucket_secret_id="0199c455-21ee-74c6-b747-19a82f1a1873"
                )
            )
        ```
        """
        artifact_details = ModelFileHandler(file_path).artifact_details()

        file_format = artifact_details.file_name.split(".")[1]
        if file_format not in ["fnnx", "pyfnx", "dfs", "luml"]:
            raise FileError("File format error")

        if name is None:
            name = artifact_details.file_name

        created_artifact_data = await self.create(
            file_name=artifact_details.file_name,
            extra_values=artifact_details.extra_values,
            manifest=artifact_details.manifest,
            file_hash=artifact_details.file_hash,
            file_index=artifact_details.file_index,
            size=artifact_details.size,
            name=name,
            description=description,
            tags=tags,
            collection_id=collection_id,
        )
        artifact = created_artifact_data.artifact

        try:
            upload_service = AsyncUploadService(self._client.bucket_secrets)

            response = await upload_service.upload_file(
                upload_details=created_artifact_data.upload_details,
                file_path=file_path,
                file_size=artifact.size,
                file_name=artifact.file_name,
            )

            status = (
                ArtifactStatus.UPLOADED
                if 200 <= response.status_code < 300
                else ArtifactStatus.UPLOAD_FAILED
            )
        except FileUploadError as error:
            await self.update(
                artifact.id,
                status=ArtifactStatus.UPLOAD_FAILED,
                collection_id=collection_id,
            )
            raise error

        return await self.update(
            artifact.id, status=status, collection_id=collection_id
        )

    @validate_collection
    async def download(
        self,
        artifact_id: str,
        file_path: str | None = None,
        *,
        collection_id: str | None = None,
    ) -> None:
        """
        Download artifact file from the collection.

        Downloads the model file to local storage with progress tracking.
        If collection_id is None, uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to download.
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
            await luml.artifacts.download(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )

            # Download to specific path
            await luml.artifacts.download(
                "0199c455-21ee-74c6-b747-19a82f1a1e67",
                file_path="/local/path/downloaded_model.fnnx",
                collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
        ```
        """
        if file_path is None:
            artifact = await self._get_by_id(
                collection_id=collection_id, artifact_value=artifact_id
            )
            if artifact is None:
                raise ValueError(f"Artifact with id {artifact_id} not found")
            file_path = artifact.file_name

        download_info = await self.download_url(
            artifact_id=artifact_id, collection_id=collection_id
        )
        download_url = download_info["url"]

        handler = S3FileHandler()
        handler.download_file_with_progress(
            url=download_url,
            file_path=file_path,
            file_name=f'artifact id="{artifact_id}"',
        )

    @validate_collection
    async def update(
        self,
        artifact_id: str,
        file_name: str | None = None,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        status: ArtifactStatus | None = None,
        *,
        collection_id: str | None = None,
    ) -> Artifact:
        """
        Update artifact metadata.

        Updates the artifact's metadata. Only provided parameters will be
        updated, others remain unchanged. If collection_id is None,
            uses the default collection from client.

        Args:
            artifact_id: ID of the artifact to update.
            file_name: New file name.
            name: New model name.
            description: New description.
            tags: New list of tags.
            status: "pending_upload" | "uploaded" | "upload_failed" | "deletion_failed"
            collection_id: ID of the collection containing the model. Optional.

        Returns:
            Artifact: Updated artifact object.

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If artifact with specified ID doesn't exist.

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
            artifact = await luml.artifacts.update(
                "0199c455-21ee-74c6-b747-19a82f1a1e67",
                name="Updated Model",
                status="uploaded"
            )
        ```
        """
        return await self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts/{artifact_id}",
            json=self._client.filter_none(
                {
                    "file_name": file_name,
                    "name": name,
                    "description": description,
                    "tags": tags,
                    "status": status.value if status else None,
                }
            ),
        )

    @validate_collection
    async def delete(
        self, artifact_id: str, *, collection_id: str | None = None
    ) -> None:
        """
        Delete artifact permanently.

        Permanently removes the artifact record and associated file from storage.
        This action cannot be undone. If collection_id is None,
            uses the default collection from client

        Args:
            artifact_id: ID of the artifact to delete.
            collection_id: ID of the collection containing the model. If not provided,
                uses the default collection set in the client

        Returns:
            None: No return value on successful deletion

        Raises:
            ConfigurationError: If collection_id not provided and
                no default collection set.
            NotFoundError: If artifact with specified ID doesn't exist

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
            await luml.artifacts.delete(
                "0199c455-21ee-74c6-b747-19a82f1a1e67"
            )
        ```

        Warning:
            This operation is irreversible. The model file and all metadata
            will be permanently lost from database, but you can still
            find model in your storage.
        """
        return await self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}/artifacts/{artifact_id}"
        )
