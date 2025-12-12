import uvicorn

from luml.service import AppService

app = AppService()


if __name__ == "__main__":
    uvicorn.run("server:app")
