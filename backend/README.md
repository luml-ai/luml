## Local Dev

1.  Go to backend folder 
```bash
cd backend
```

2. Create and activate venv 
```bash
uv venv
source .venv/bin/activate
```

3. Install dependencies
```bash
uv sync
```

4. Mark Backend folder as *Sources Root* 
	1. If you are using PyCharm - right-click on backend folder -> Mark Directory as -> Sources Root -> Restart PyCharm
	2. with command
```bash
export PYTHONPATH=./
```

5. Create .env from .env.example (copy variables from .env.example) and fill missing values 

6. Open .env and replace *POSTGRESQL_DSN* with 
```python
POSTGRESQL_DSN=postgresql+asyncpg://user:password@localhost:5432/df_studio
```

7. Start local DB
```bash
docker compose up -d
```

8. Apply migrations
```bash
alembic upgrade head
```

9. Check your db structure
```bash
docker exec -it df-studio-postgres psql -U user -d df_studio
\dt
```

10. Run the app
```bash
uvicorn luml.server:app --reload
```

# 


Please note, that it is crucial to use ruff (https://docs.astral.sh/ruff/)


> Before push and especially PR lint your code with ruff because branches with lint error could not be merged 

```
ruff check .              # Lint files in the current directory.
ruff check . --fix        # Lint and fix any fixable errors.
ruff check path/to/code/  # Lint files in `path/to/code`.
```

## Microsoft OAuth

Microsoft sign-in uses the ID token's `email` claim after validating its signature,
audience, issuer, tenant, and lifetime. Microsoft Graph `mail`, `otherMails`, and
`userPrincipalName` are not proof of email ownership and are not used to sign in.

Configure the Microsoft app registration to include the `email` and `xms_edov`
optional claims in ID tokens. `xms_edov` must be the boolean `true`; a signed
`email_verified` claim with the boolean `true` is also accepted. Sign-in fails
with HTTP 403 when neither verification claim is present and true, including for
previously registered Microsoft accounts. Configure these claims before deploying
this change; there is no fallback to an unverified email address.

Microsoft documents `xms_edov` and its domain-verification rules in the
[optional claims reference](https://learn.microsoft.com/en-us/entra/identity-platform/optional-claims-reference).

## Cookie session requests

State-changing requests authenticated by `access_token` or `refresh_token` cookies
must send an `Origin` header matching the API origin or an explicit origin in
`CORS_ORIGINS`. This includes token refresh and logout. Missing, `null`, and
untrusted origins return 403. Browsers send this header automatically; configure
`CORS_ORIGINS` for the frontend origin in cross-origin deployments, including when
`AUTH_COOKIE_SAMESITE=none`.

Bearer JWT, API key, and satellite key requests use the `Authorization` header and
do not require this check. Refresh and logout always use cookies and remain
protected even if an `Authorization` header is supplied.

Request a single artifact deletion URL with
`POST /v1/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}/delete-url`.
GET on that path is deprecated and kept only for clients that authenticate with
an `Authorization` header (API keys, older SDK releases); cookie sessions get 405
from GET and the artifact status does not change.
## Optional backend observability

The API enables Logfire only when `LOGFIRE_TOKEN` is nonempty. Without a token,
startup, tests and migration jobs do not configure instrumentation or send
telemetry. Existing local logging continues to work.

Provide configuration through environment variables or the backend `.env`:

| Variable | Purpose | Default |
| --- | --- | --- |
| `LOGFIRE_TOKEN` | Project write token; store as an App Platform `SECRET` scoped to the API at runtime | Unset (disabled) |
| `LOGFIRE_ENVIRONMENT` | `dev`, `staging` or `prod` | `dev` |
| `LOGFIRE_SERVICE_VERSION` | Release identifier, preferably the deployed commit SHA | `0.1.0` |
| `LOGFIRE_BASE_URL` | `https://logfire-us.pydantic.dev` or `https://logfire-eu.pydantic.dev`; must match the token's project region | US |

The service name is `luml-backend`. Use separate project tokens per environment,
or filter a shared project by its environment metadata. Keep tokens out of source
control, frontend configuration and build arguments. The `PRE_DEPLOY` migration
job needs no Logfire configuration.

When enabled, Logfire records FastAPI requests, SQLAlchemy operations, outgoing
HTTPX requests and standard application logging. Only SQLAlchemy is instrumented;
asyncpg is left uninstrumented to avoid duplicate database spans. Requests to
`/health` and its subpaths are excluded. Application `luml` logs are captured at
INFO and above, including the platform admin logger.

Before OTLP export, an allowlist retains timings, trace context, HTTP methods,
route templates, status codes, database system, exception types, log levels and
source locations. It removes SQL text and parameters, URL paths and queries,
headers and bodies, log arguments, baggage and unknown attributes. Log messages,
exception messages and stacktraces are exported after scrubbing: Logfire's
default patterns (password, secret, auth, api key, session, cookie, jwt and
others) are extended with `token`, `dsn`, `bearer`, email addresses and URL
credentials. A matching message or stacktrace line is replaced by `[Scrubbed]`
as a whole; stacktrace location lines (`File "…", line N, in …`) are always
kept. Pattern scrubbing cannot recognise a secret whose value and surrounding
text look harmless, so review logs for leaks after enabling the integration and
extend `SCRUBBING_PATTERNS` in `luml/infra/observability.py` when needed. The
SDK's default exporter, console output and metrics are disabled so they cannot
bypass this filter. Legacy
`OTEL_*_EXPORTER` selectors are set to `none` when enabling this integration,
preventing old OTLP endpoint variables from creating additional exporters.

Provider setup and export filtering live in `luml/infra/observability.py`; business
code continues using standard logging. A future provider change can be made at
this boundary without editing handlers or routes.

This is code preparation only. Deployment changes, Datadog forwarding and
credential cleanup, frontend hosting monitoring, production alerts and live
Logfire verification are deferred. Customer inference telemetry in satellites,
model servers and the SDK is unchanged. No App Platform specs are tracked here.

References: [Logfire API](https://pydantic.dev/docs/logfire/api/logfire/),
[OTLP connection settings](https://pydantic.dev/docs/logfire/guides/alternative-clients/).

## Authentication rate limits

Sign-in, sign-up, forgot-password, reset-password, and the platform-admin password
grant allow 20 requests per client IP and 5 requests per email per endpoint within
a one-minute window that starts at the first request. Reset-password uses the
email from a verified reset token; invalid tokens count against the IP limit.
Requests over either limit receive HTTP 429 with a `Retry-After` header in
seconds. Denied requests also count towards the limit.

Counters live in Redis (`REDIS_URL`) and are shared across API workers; keys are
HMAC digests of the endpoint and the scope, so Redis never stores addresses or
emails in clear text, and they expire with the window. When Redis is unreachable
the limiter logs the failure and lets the request through, so a Redis outage
degrades to the previous unthrottled behaviour instead of blocking sign-in.

`REDIS_URL` is optional for now: when it is not set the backend starts, logs a
warning and applies no authentication rate limits. This is a transition step
so existing deployments keep working until Redis is provisioned for every
environment; a follow-up change makes the setting mandatory.

The application uses the request client address, so configure Uvicorn's trusted
proxy addresses for your ingress and restrict direct access to the API when
running behind a proxy. Untrusted forwarding headers must not set the client IP.
