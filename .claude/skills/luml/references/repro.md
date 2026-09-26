# Reproducing LUML API behaviour

Everything here lives in `scripts/` next to this file:
`luml_trace.py` (see every HTTP request) and `repro_template.py` (a runnable
repro scaffold). Copy the template next to the bug, edit one function, run it.

## Why a script and not terminal calls

`luml_api` builds its `httpx.Client` internally and exposes no hook, so nothing
prints the wire traffic by default. Two more things are invisible from the
outside: the `LumlClient` constructor makes its own calls when defaults are
given by name (organizations → orbits → collections), and uploads/downloads go
to presigned bucket URLs through separate `httpx` calls, not through the API
host. `luml_trace` patches `httpx.Client.send` / `httpx.AsyncClient.send`, so
all three show up in one log.

## Writing a repro

```bash
cp .claude/skills/luml/scripts/repro_template.py repro_bug_1234.py
# edit the REPRO section: setup, the call that misbehaves, what was expected
export LUML_API_KEY=luml_...
python repro_bug_1234.py                          # dev stack by default
python repro_bug_1234.py --base-url https://api.luml.ai
python repro_bug_1234.py --keep                   # leave created resources for inspection
```

The harness gives you: tracing on for the whole run (console + `repro_bug_1234.jsonl`),
target and defaults from flags or `LUML_BASE_URL` / `LUML_ORGANIZATION` /
`LUML_ORBIT` / `LUML_COLLECTION`, a `RUN_ID` to tag created resources, cleanup
via `on_cleanup(...)` that still runs when the repro raises, and exit code 1
when the failure reproduced. The script plus its `.jsonl` is the whole bug report.

Rules for a repro script:

- **No keys in the file** — it gets pasted into issues. `LUML_API_KEY` only.
- **Register cleanup at the moment of creation**, `on_cleanup(lambda: ...delete(id))`,
  so a failing run does not leave junk in a shared orbit.
- **Name created resources with `RUN_ID`** so leftovers are identifiable.
- **Assert the expectation** rather than printing and eyeballing — that is what
  makes the exit code mean something.

## Tracing anything else

The tracer is independent of the template — use it in any script, test, or notebook:

```python
import sys; sys.path.insert(0, ".claude/skills/luml/scripts")
from luml_trace import trace

with trace("requests.jsonl"):          # or luml_trace.start() for the whole process
    luml = LumlClient()                # constructor calls are captured too
    luml.artifacts.upload(file_path="model.fnnx", name="m")
```

Each line of the JSONL is one request: `seq`, `method`, `url`,
`request_headers`, `request_body`, `status`, `response_body`, `elapsed_ms`,
`error`. Bearer tokens and presigned-URL signature parameters are redacted, so
the log is safe to attach. Bodies are truncated at 2000 chars
(`trace(max_body=...)`); streamed uploads and downloads are recorded as
`<streamed>` and are not consumed, so tracing never breaks a transfer.

## Reading the failure

`_process_response` already raises with method, URL, status and the server's
`detail`, and the typed exception carries the rest:

```python
except LumlAPIError as exc:
    exc.response      # httpx.Response
    exc.body          # parsed JSON body, or text
```

Match the status to the exception before guessing: `AuthenticationError` (bad or
missing key), `PermissionDeniedError`, `NotFoundError`, `ConflictError` (a stage
already occupied, a lineage edge that exists), `UnprocessableEntityError`
(payload rejected), `SatelliteOutOfSyncError` and
`CapabilityNotSupportedError` (deployment/monitoring against a Satellite that is
behind). A `pydantic.ValidationError` out of a resource method is a
**client/server contract mismatch**, not a user error — the response parsed as
JSON but did not match the SDK's model; the trace log holds the offending body.

## Against the dev stack

`dev/docker-compose.yml` runs the whole platform locally — backend on
`http://localhost:8000` (docs at `/docs`), frontend on `:5173`, MinIO on
`:9001`, Postgres on `:5432`. `dev/README.md` has the setup; the seed is
idempotent and creates the admin user, an organization, a `Sample Orbit` and a
bucket secret pointing at the local MinIO:

```bash
docker compose -f dev/docker-compose.yml up
docker compose -f dev/docker-compose.yml run --rm seed
```

Log in as `admin@example.com` / `admin12345` and create an API key in the UI, or
`POST /v1/users/me/api-keys` with the session JWT. Then
`export LUML_BASE_URL=http://localhost:8000`.

Prefer the dev stack: repro scripts create and delete resources, and the backend
logs sit next to the client trace for the same request.

## Turning a repro into a test

Once the behaviour is pinned down, the captured request belongs in
`sdk/python/api/tests/unit/` — those tests drive the client against `respx`
mocks, with fixtures in `sdk/python/api/tests/conftest.py`
(`TEST_BASE_URL = "http://127.0.0.1:8000"`, `mock_sync_client` /
`mock_async_client`). The URL, request body and response body in the JSONL are
exactly what the mock needs.

## Flow SDK repros

`ExperimentTracker` is a local SQLite store, so a repro only needs a clean
path — `ExperimentTracker("sqlite:///tmp/repro-experiments")`, deleted between
runs. No tracing needed; nothing leaves the machine unless the artifact is
uploaded with `luml_api`.
