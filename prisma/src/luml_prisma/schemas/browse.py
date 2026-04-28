from pydantic import BaseModel


class BrowseEntryOut(BaseModel):
    name: str
    path: str
    is_git: bool


class BrowseResultOut(BaseModel):
    current: str
    parent: str | None
    dirs: list[BrowseEntryOut]
    is_git: bool


class BranchListOut(BaseModel):
    branches: list[str]
