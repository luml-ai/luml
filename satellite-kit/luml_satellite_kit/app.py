from fastapi import APIRouter, FastAPI


def create_satellite_app(extra_routers: list[APIRouter] | None = None) -> FastAPI:
    app = FastAPI()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "healthy"}

    for router in extra_routers or []:
        app.include_router(router)

    return app
