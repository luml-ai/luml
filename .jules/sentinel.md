## 2024-05-20 - Insecure Direct Object Reference in Bucket Secrets
**Vulnerability:** The `get_bucket_multipart_urls` endpoint in `backend/luml/api/bucket_secret_urls.py` allowed any authenticated user to generate multipart upload URLs for any bucket secret by providing its UUID, without checking if the user had permission to access that specific secret or organization.
**Learning:** Handlers that accept an object ID directly from the request body (rather than path parameters) can easily be overlooked for permission checks, especially if the method signature doesn't require user context.
**Prevention:** Always ensure that every handler method that accesses a resource takes `user_id` and `organization_id` as arguments and performs an explicit `check_permissions` call before accessing the data. Review all endpoints to ensure they pass user context to the business logic layer.
## 2025-02-14 - Password Policy Improvement
**Vulnerability:** Weak Password Policy (Length Limit)
**Learning:** The application restricted passwords to a maximum of 36 characters. This prevents users from using strong passphrases or generated passwords, which is contrary to NIST SP 800-63B guidelines.
**Prevention:** Always allow long passwords (e.g., up to 128 or more characters) to encourage the use of passphrases. Ensure the hashing algorithm (like Argon2 or Bcrypt) handles long inputs correctly without truncation or DoS risk.
## 2024-05-22 - [Broken Access Control in Invite Acceptance]
**Vulnerability:** Found that `accept_invite` and `reject_invite` did not verify if the current user was the intended recipient of the invitation. Any user could accept or reject any invite if they knew the invite ID.
**Learning:** Checking for "authentication" is not enough. You must always verify "authorization" (permission to act on a specific resource). Just because `request.user` exists doesn't mean they own the invite.
**Prevention:** Always verify ownership of resources before performing actions. Pass the authenticated user's identity (ID, email) to the service layer and validate it against the resource being accessed.

## 2025-02-14 - Critical Endpoint Without Auth Check
**Vulnerability:** The `DELETE /auth/users/me` endpoint was missing the `Depends(is_user_authenticated)` dependency. While authentication middleware populated `request.user`, accessing `request.user.email` for unauthenticated users caused a server crash (500 Internal Server Error) instead of a 401 Unauthorized response. This created a Denial of Service (DoS) risk and relied on "crash safety" rather than explicit security checks.
**Learning:** Middleware population of user objects does not replace the need for explicit endpoint security dependencies in FastAPI. Always enforce authentication via dependencies to fail fast and securely.
**Prevention:** Ensure all sensitive endpoints, especially those modifying state (DELETE/POST/PATCH), explicitly include the authentication dependency `Annotated[None, Depends(is_user_authenticated)]`.
# Sentinel's Journal

## 2025-02-18 - Unprotected Public Statistics Endpoint
**Vulnerability:** The `/stats/email-send` endpoint is publicly accessible and allows unauthenticated creation of records.
**Learning:** Endpoints intended for internal tracking or webhooks might be left unprotected. Frontend uses `skipInterceptors: true` to call it, bypassing auth.
**Prevention:** Always verify authentication requirements for "stats" or "logging" endpoints. Ensure public endpoints have rate limiting and strict input validation.
