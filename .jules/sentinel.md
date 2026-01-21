## 2025-02-14 - Critical Endpoint Without Auth Check
**Vulnerability:** The `DELETE /auth/users/me` endpoint was missing the `Depends(is_user_authenticated)` dependency. While authentication middleware populated `request.user`, accessing `request.user.email` for unauthenticated users caused a server crash (500 Internal Server Error) instead of a 401 Unauthorized response. This created a Denial of Service (DoS) risk and relied on "crash safety" rather than explicit security checks.
**Learning:** Middleware population of user objects does not replace the need for explicit endpoint security dependencies in FastAPI. Always enforce authentication via dependencies to fail fast and securely.
**Prevention:** Ensure all sensitive endpoints, especially those modifying state (DELETE/POST/PATCH), explicitly include the authentication dependency `Annotated[None, Depends(is_user_authenticated)]`.
# Sentinel's Journal

## 2025-02-18 - Unprotected Public Statistics Endpoint
**Vulnerability:** The `/stats/email-send` endpoint is publicly accessible and allows unauthenticated creation of records.
**Learning:** Endpoints intended for internal tracking or webhooks might be left unprotected. Frontend uses `skipInterceptors: true` to call it, bypassing auth.
**Prevention:** Always verify authentication requirements for "stats" or "logging" endpoints. Ensure public endpoints have rate limiting and strict input validation.
