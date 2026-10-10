import secrets
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from lumlflow.api.annotations import annotations_router
from lumlflow.api.auth import auth_router
from lumlflow.api.experiment_groups import experiment_groups_router
from lumlflow.api.experiments import experiments_router
from lumlflow.api.experiments_evals import (
    experiments_evals_router,
    experiments_general_evals_router,
)
from lumlflow.api.experiments_traces import (
    experiments_general_traces_router,
    experiments_traces_router,
)
from lumlflow.api.luml import luml_router
from lumlflow.api.models import models_router
from lumlflow.infra.exceptions import ApplicationError


class AppService(FastAPI):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)

        self.state.session_token = secrets.token_urlsafe(32)

        @self.middleware("http")
        async def require_session(request: Request, call_next):
            if request.url.path.startswith("/api/") and request.method != "OPTIONS":
                authorization = request.headers.get("Authorization", "")
                expected = f"Bearer {self.state.session_token}"
                if not secrets.compare_digest(
                    authorization.encode(), expected.encode()
                ):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or missing Flow session token"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            return await call_next(request)

        self.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

        self.include_router(router=auth_router)
        self.include_router(router=luml_router)
        self.include_router(router=experiment_groups_router)
        self.include_router(router=experiments_router)
        self.include_router(router=experiments_evals_router)
        self.include_router(router=experiments_general_evals_router)
        self.include_router(router=experiments_traces_router)
        self.include_router(router=experiments_general_traces_router)
        self.include_router(router=models_router)
        self.include_router(router=annotations_router)
        self.include_error_handlers()
        self.custom_openapi()

    def include_error_handlers(self) -> None:
        @self.exception_handler(ApplicationError)
        async def service_error_handler(
            request: Request,
            exc: ApplicationError,
        ) -> JSONResponse:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.message},
            )

    def custom_openapi(self) -> dict[str, Any]:
        if self.openapi_schema:
            return self.openapi_schema

        openapi_schema = get_openapi(
            title="Lumlflow",
            description="Local ML experiment tracking",
            version="0.1.0",
            routes=self.routes,
        )
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {"type": "http", "scheme": "bearer"}
        }
        openapi_schema["security"] = [{"BearerAuth": []}]
        self.openapi_schema = openapi_schema
        return self.openapi_schema
