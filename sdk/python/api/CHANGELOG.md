# Changelog

## Unreleased

The API client now uses `httpx2`. Catch `luml_api.APIStatusError` for API error
responses and `luml_api.APIConnectionError` for network errors and timeouts.

When `httpx` is installed, escaping HTTP errors also inherit from the matching
`httpx` exception. Existing `except httpx.HTTPError`, `except httpx.ConnectError`,
and `except httpx.HTTPStatusError` handlers continue to work. This compatibility
layer will be removed in the next major release. The client does not require
`httpx` and does not change its imports or classes in the user's process.

Responses use `httpx2.Response`. Their attributes, including `status_code`,
`headers`, and `json()`, remain available, but
`isinstance(error.response, httpx.Response)` is no longer supported.
