# Sentinel's Journal

## 2025-02-18 - Unprotected Public Statistics Endpoint
**Vulnerability:** The `/stats/email-send` endpoint is publicly accessible and allows unauthenticated creation of records.
**Learning:** Endpoints intended for internal tracking or webhooks might be left unprotected. Frontend uses `skipInterceptors: true` to call it, bypassing auth.
**Prevention:** Always verify authentication requirements for "stats" or "logging" endpoints. Ensure public endpoints have rate limiting and strict input validation.
