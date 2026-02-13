from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from lumlflow.api.experiment_groups import experiment_groups_router
from lumlflow.api.general import general_router
from lumlflow.infra.exceptions import ApplicationError


class AppService(FastAPI):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)

        self.include_router(router=general_router)
        self.include_router(router=experiment_groups_router)
        self.include_error_handlers()
        self.custom_openapi()

        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
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
            title="Lumlflow",
            description="Local ML experiment tracking",
            version="0.1.0",
            routes=self.routes,
        )
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
        openapi_schema["security"] = [{"BearerAuth": []}]
        self.openapi_schema = openapi_schema
        return self.openapi_schema
