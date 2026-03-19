from typing import Literal

import httpx


def _format_resources(
    resource_type: str,
    all_values: list | None,
    has_more: bool = False,
) -> str:
    if not all_values:
        return ""

    if len(all_values) == 0:
        return f"\nYou do not have available {resource_type}s yet."

    result = f"\nAvailable {resource_type}s for configuration:"

    for item in all_values:
        result += f'\n      {resource_type}(id={item.id}, name="{item.name}")'

    if has_more:
        result += "..."

    return result


class LumlAPIError(Exception):
    def __init__(
        self,
        message: str = "LUML Studio API error.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class ConfigurationError(LumlAPIError):
    def __init__(
        self,
        resource_type: str,
        message: str | None = None,
        all_values: list | None = None,
        has_more: bool = False,
    ) -> None:
        self.message = message if message else ""
        self.message += """
        luml = LumlClient(
            api_key="luml_api_key",
            organization=1,
            orbit=1215,
            collection=15
        )
        """
        self.message += _format_resources(resource_type, all_values, has_more)

        super().__init__(self.message)


class MultipleResourcesFoundError(LumlAPIError):
    pass


class ResourceNotFoundError(Exception):
    def __init__(
        self,
        resource_type: str,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
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
        self.message += _format_resources(resource_type, all_values, has_more)

        super().__init__(self.message)


class OrbitResourceNotFoundError(ResourceNotFoundError):
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Orbit", value, all_values, has_more, message)


class OrganizationResourceNotFoundError(ResourceNotFoundError):
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Organization", value, all_values, has_more, message)


class CollectionResourceNotFoundError(ResourceNotFoundError):
    def __init__(
        self,
        value: int | str,
        all_values: list | None = None,
        has_more: bool = False,
        message: str | None = None,
    ) -> None:
        super().__init__("Collection", value, all_values, has_more, message)


class APIError(LumlAPIError):
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
