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
