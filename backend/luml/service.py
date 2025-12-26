from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.middleware.authentication import AuthenticationMiddleware

from luml.api.auth import auth_router
from luml.api.bucket_secret_urls import bucket_secret_urls_router
from luml.api.email_routes import email_routers
from luml.api.organization.organization import organization_router
from luml.api.organization_routes import organization_all_routers
from luml.api.satellites import satellite_worker_router
from luml.api.user_routes import users_routers
from luml.infra.exceptions import ApplicationError
from luml.infra.security import JWTAuthenticationBackend
from luml.settings import config


class AppService(FastAPI):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)

        self.include_router(router=auth_router, tags=["auth"])
        self.include_router(router=email_routers)
        self.include_router(router=users_routers)
        self.include_router(router=organization_router)
        self.include_router(router=organization_all_routers)
        self.include_router(router=bucket_secret_urls_router)
        self.include_router(router=satellite_worker_router)
        self.include_authentication()
        self.include_error_handlers()
        self.custom_openapi()

        allowed_origins = config.CORS_ORIGINS.split(",")
        self.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def include_authentication(self) -> None:
        self.add_middleware(
            AuthenticationMiddleware,
            backend=JWTAuthenticationBackend(),
        )

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
            title="LUML AI API",
            version="1.0.0",
            description="API docs for LUML AI",
            routes=self.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
        openapi_schema["security"] = [{"BearerAuth": []}]
        self.openapi_schema = openapi_schema
        return self.openapi_schema
