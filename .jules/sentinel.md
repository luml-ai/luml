## 2024-05-22 - [FastAPI Authentication Dependency]
**Vulnerability:** Missing `Depends(is_user_authenticated)` on sensitive endpoint `delete_account` allowed unauthenticated access, resulting in 500 Server Error due to `request.user.email` access on `UnauthenticatedUser`.
**Learning:** `AuthenticationMiddleware` populates `request.user` with `UnauthenticatedUser` if no token is present. Endpoints must explicitly enforce authentication using `Depends(is_user_authenticated)` to block access and ensure `request.user` is a valid user object.
**Prevention:** Always include `Depends(is_user_authenticated)` (or equivalent) on protected endpoints. Do not assume `request.user` has attributes like `email` without this check.
