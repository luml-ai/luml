# Dev stack

Local Docker Compose stack for the whole platform (FE, BE, extras packages)
with hot-reload, a local S3 (MinIO), and an idempotent seed.

## Run

From the repo root:

```bash
docker compose -f dev/docker-compose.yml up
```

First run builds two images and runs `npm install` — subsequent runs are fast.

## What you get

| URL | What |
|---|---|
| http://localhost:5173 | Frontend (Vite, hot-reload) |
| http://localhost:8000 | Backend (uvicorn `--reload`) |
| http://localhost:8000/docs | API docs |
| http://localhost:9001 | MinIO console (`minioadmin` / `minioadmin`) |
| localhost:5432 | Postgres (`user` / `password` / `df_studio`) |

App login: `admin@example.com` / `admin12345`.

The seed creates the user, an org, a `Sample Orbit`, and a bucket secret
pointing at the local MinIO. It's idempotent — re-runs only fill in what's
missing:

```bash
docker compose -f dev/docker-compose.yml run --rm seed
```

## Layout

- `docker-compose.yml` — services
- `backend.Dockerfile`, `node.Dockerfile` — dev images
- `backend.env` — backend env vars (DSN, CORS, seed config)
- `seed.py` — idempotent seed (admin / org / orbit / bucket secret)

The `extras-attachments` and `extras-experiments` services run
`vite build --watch`, regenerating each package's `dist/` on every change;
the frontend's Vite picks them up via npm workspace symlinks.
