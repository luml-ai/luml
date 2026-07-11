from handlers.model_handler import ModelHandler
from services.base_service import UvicornBaseService

app = UvicornBaseService()
model_handler = ModelHandler()


@app.get(
    "/healthz",
    summary="Health Check",
    description="Returns the health status of the service",
    tags=["model"],
)
async def healthz() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=6005)
