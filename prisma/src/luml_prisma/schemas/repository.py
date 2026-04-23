from pydantic import BaseModel, ConfigDict


class RepositoryCreateIn(BaseModel):
    name: str
    path: str


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    path: str
