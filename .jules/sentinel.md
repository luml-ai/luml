## 2025-05-15 - Missing Authentication on Sensitive Endpoint
**Vulnerability:** The `delete_account` endpoint in `backend/luml/api/auth.py` was missing the `is_user_authenticated` dependency, allowing unauthenticated users to trigger the endpoint (though it would crash due to missing user object).
**Learning:** FastAPI endpoints do not inherit authentication from the router or app automatically unless specified. Explicit `Depends` is required.
**Prevention:** Always verify that sensitive endpoints have the `is_user_authenticated` dependency or equivalent access control. Use linters or tests to enforce this if possible.
