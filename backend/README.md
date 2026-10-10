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
headers and bodies, log messages and arguments, exception messages and
stacktraces, baggage and unknown attributes. Exported log entries are labelled
`application log`; use their logger, location and trace to identify the event.
This deliberately limits diagnostic detail so arbitrary secrets and personal
data in free-form values cannot be sent. The SDK's default exporter, console
output and metrics are disabled so they cannot bypass this filter. Legacy
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
