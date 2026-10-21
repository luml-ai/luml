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

## Authentication rate limits

Sign-in, sign-up, forgot-password, reset-password, and the platform-admin password
grant allow 20 requests per client IP and 5 requests per email per endpoint in each
one-minute window. Reset-password uses the email from a verified reset token;
invalid tokens count against the IP limit. Requests over either limit receive
HTTP 429 with a `Retry-After` header in seconds. Counters are shared through
PostgreSQL across API workers; apply migration 043 before deploying the backend.
Expired counters are removed on subsequent authentication requests.

The application uses the request client address, so configure Uvicorn's trusted
proxy addresses for your ingress and restrict direct access to the API when
running behind a proxy. Untrusted forwarding headers must not set the client IP.
