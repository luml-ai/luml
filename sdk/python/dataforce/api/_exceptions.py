from typing import Literal

import httpx


class DataForceAPIError(Exception):
    def __init__(
        self,
        message: str = "DataForce Studio API error.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class ConfigurationError(DataForceAPIError):
    def __init__(
        self,
        resource_type: str,
        message: str | None = None,
        all_values: list | None = None,
    ) -> None:
        self.message = message if message else ""
        self.message += """
        dfs = DataForceClient(
            api_key="dfs_api_key",
            organization=1,
            orbit=1215,
            collection=15
        )
        """
        if all_values:
            if len(all_values) > 0:
                formatted_resources = "\n      ".join(
                    f'{resource_type}(id={e.id}, name="{e.name}")' for e in all_values
                )
                self.message += (
                    f"\nAvailable {resource_type}s for configuration:"
                    f"\n      {formatted_resources}"
                )
            else:
                self.message += f"\nYou do not have available {resource_type}s yet."

        super().__init__(self.message)


class MultipleResourcesFoundError(DataForceAPIError):
    pass


class ResourceNotFoundError(Exception):
    def __init__(
        self,
        resource_type: str,
        value: int | str,
        all_values: list | None = None,
        message: str | None = None,
    ) -> None:
        if message:
            self.message = message
        else:
            value_reference = "id" if isinstance(value, int) else "name"
            self.message = (
                f"{resource_type} with {value_reference} '{value}'"
                f" not found. Try to set with another id or name."
            )
        if all_values:
            if len(all_values) > 0:
                formatted_resources = "\n      ".join(
                    f'{resource_type}(id={e.id}, name="{e.name}")' for e in all_values
                )
                self.message += (
                    f"\nAvailable {resource_type}s for configuration:"
                    f"\n      {formatted_resources}"
                )
            else:
                self.message += f"\nYou do not have available {resource_type}s yet."

        super().__init__(self.message)


class OrbitResourceNotFoundError(ResourceNotFoundError):
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__("Orbit", value, all_values, message)


class OrganizationResourceNotFoundError(ResourceNotFoundError):
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__("Organization", value, all_values, message)


class CollectionResourceNotFoundError(ResourceNotFoundError):
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__("Collection", value, all_values, message)


class APIError(DataForceAPIError):
    message: str
    request: httpx.Request
    body: object | None

    def __init__(
        self, message: str, request: httpx.Request, *, body: object | None
    ) -> None:
        super().__init__(message)
        self.request = request
        self.message = message
        self.body = body


class APIResponseValidationError(APIError):
    response: httpx.Response
    status_code: int

    def __init__(
        self,
        response: httpx.Response,
        body: object | None,
        *,
        message: str | None = None,
    ) -> None:
        super().__init__(
            message or "Data returned by API invalid for expected schema.",
            response.request,
            body=body,
        )
        self.response = response
        self.status_code = response.status_code


class APIStatusError(APIError):
    response: httpx.Response
    status_code: int

    def __init__(
        self, message: str, *, response: httpx.Response, body: object | None
    ) -> None:
        super().__init__(message, response.request, body=body)
        self.response = response
        self.status_code = response.status_code


class BadRequestError(APIStatusError):
    status_code: Literal[400] = 400


class AuthenticationError(APIStatusError):
    status_code: Literal[401] = 401


class PermissionDeniedError(APIStatusError):
    status_code: Literal[403] = 403


class NotFoundError(APIStatusError):
    status_code: Literal[404] = 404


class ConflictError(APIStatusError):
    status_code: Literal[409] = 409


class UnprocessableEntityError(APIStatusError):
    status_code: Literal[422] = 422


class InternalServerError(APIStatusError):
    pass


class FileError(Exception):
    pass


class FileUploadError(FileError):
    def __init__(self, message: str = "") -> None:
        super().__init__("Error uploading file to bucket." + message)


class FileDownloadError(FileError):
    def __init__(self, message: str = "") -> None:
        super().__init__("Error downloading file from bucket." + message)
