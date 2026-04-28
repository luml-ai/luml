from typing import Any

from pydantic import BaseModel


class ReorderItem(BaseModel):
    id: str
    position: int


class ReorderIn(BaseModel):
    items: list[ReorderItem]


class NodeActionIn(BaseModel):
    action: str
    payload: dict[str, Any] = {}


class NodeInputIn(BaseModel):
    text: str
