import uvicorn

from luml.infra.db import engine
from luml.infra.observability import configure_observability
from luml.service import AppService
from luml.settings import config

app = AppService()
configure_observability(app, engine, config)


if __name__ == "__main__":
    uvicorn.run("server:app")
