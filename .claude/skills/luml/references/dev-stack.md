# Dev stack: running the platform locally and the traps in it

`dev/docker-compose.yml` runs Postgres, MinIO, the backend (`:8000`, Swagger at
`/docs`), a seed job, and — in theory — the frontend (`:5173`). Everything below
was learned the hard way while testing against it; read it before starting the
stack for an API or UI check.

## Start

```bash
cd <repo root>
printf 'UID=%s\nGID=%s\n' "$(id -u)" "$(id -g)" > dev/.env
docker compose -f dev/docker-compose.yml up -d postgres minio minio-init backend-migrate backend seed
```

Login: `admin@example.com` / `admin12345`. The seed creates that user, "Dev's
organization", a `Sample Orbit` and a bucket secret pointing at MinIO.

`scripts/dev_api.sh` sets up curl helpers for all of this — `source` it and use
`a` / `A` / `psql` / `login` (see "Helpers" below).

## Trap 1 — alembic version drift between branches

The Postgres volume keeps `alembic_version` across branch switches. If another
branch added a migration (e.g. `039_…`) and the current branch does not have the
file, `backend-migrate` exits 255 with `Can't locate revision identified by '039'`
and the backend never starts.

Find where the revision came from, then decide:

```bash
git log --all --oneline -- 'backend/migrations/versions/*039*'
git show <branch>:backend/migrations/versions/039_….py | sed -n '/def downgrade/,$p'
```

- Data-only or constraint-only migration → apply its `downgrade()` by hand in
  psql and `UPDATE alembic_version SET version_num='038'`.
- Schema migration you can't undo safely → `docker compose … down -v` and reseed
  (loses all local data).

## Trap 2 — frontend does not run inside docker on macOS

`frontend`, `extras-attachments` and `extras-experiments` mount the host
`node_modules` into a Linux container; rollup's native binary is the macOS one
and the container dies with `MODULE_NOT_FOUND … rollup/dist/native.js`.

Run Vite on the host instead. The `vite` binary lives in the workspace root:

```bash
cd frontend
printf 'VITE_API_URL=http://localhost:8000\nVITE_DOCS_URL=http://localhost:5173\n' > .env.development.local
../node_modules/.bin/vite --host 127.0.0.1 --port 5173
```

Open it as `http://localhost:5173`, never `127.0.0.1:5173` — see trap 4.

## Trap 3 — port 5000 is taken on macOS

`lumlflow ui` defaults to `:5000`, which macOS Control Center (AirPlay receiver)
already listens on. Always pass a port, and point at a throwaway store rather
than the user's real one (the default store comes from the user's config):

```bash
lumlflow ui --no-browser --port 5050 --path "sqlite:///abs/path/to/store"
```

`--path` wants `sqlite://` + an absolute directory. The store is a directory
(`meta.db` + one folder per experiment), created on first write by
`ExperimentTracker("sqlite:///abs/path")`. Use the SDK's own venv
(`sdk/python/sdk/.venv/bin/python`) to seed it — it has sklearn and the optional
deps; `lumlflow/.venv` does not.

## Trap 4 — cookies are Secure + SameSite=lax

The backend sets `access_token` / `refresh_token` with `secure=True` and
`AUTH_COOKIE_SAMESITE=lax` (`dev/backend.env`).

- **curl**: a cookie jar will not send a Secure cookie back over plain http. Pull
  the token from `Set-Cookie` and use `Authorization: Bearer`. The helpers do
  this.
- **Browser**: `127.0.0.1:5173` → `localhost:8000` is cross-site, so the Lax
  cookie is never sent and sign-in bounces back to login. Use `localhost:5173`.
- `POST /v1/auth/logout` reads the cookies, not the bearer header. To test it
  from curl send `Cookie: access_token=…; refresh_token=…`.

## Trap 5 — two sign-ins in the same second return the same JWT

Tokens carry no `jti`; payload is `sub` + `exp` + `type`, so two logins within
one second are byte-identical. Blacklisting one (logout) kills the other and
every later request with it returns 401 — or 500 if it was blacklisted twice.
When a test needs two independent sessions, `sleep 1` between logins.

## Trap 6 — SendGrid is broken in dev, and that leaks into the API

`SENDGRID_API_KEY` in `dev/backend.env` is invalid, so:

- `POST /v1/auth/signup` → 503 (and leaves an orphan organization).
- `POST …/invitations` → 201 with an error-shaped body, invite stored.
- `POST …/orbits/{id}/members` → 500 after the member row is committed.

You cannot create a second user through the API. Create one in psql by copying
the admin's password hash (password is then `admin12345`):

```sql
INSERT INTO users (id,email,full_name,disabled,email_verified,auth_method,hashed_password)
SELECT gen_random_uuid(), 'user2@example.com', 'User Two', false, true, 'EMAIL',
       (SELECT hashed_password FROM users WHERE email='admin@example.com');
```

Organization limits live on `organizations` as `members_limit`,
`orbits_limit`, `satellites_limit`, `artifacts_limit`; raise them there when a
test hits "Organization reached maximum number of …" (409).

## Backend logs

```bash
docker compose -f dev/docker-compose.yml logs --no-log-prefix --since 5m backend
```

Tracebacks are multi-line; grep for `/app/luml` frames and the final
`sqlalchemy.exc.…` / `asyncpg.exceptions.…` line. Source IPs in the access log
are the docker proxy, not real clients.

## Helpers

`scripts/dev_api.sh`:

```bash
source ~/.claude/skills/luml/scripts/dev_api.sh   # logs in, sets API/TOKEN/ORG/ORBIT
a  "$API/v1/organizations/$ORG/orbits"            # curl -s with bearer
A  -X POST "$API/…" -d '{…}'                      # curl -i -s with bearer
psql -c "SELECT email FROM users"                  # psql inside the postgres container
T2=$(login user2@example.com admin12345)           # token for another user
```
