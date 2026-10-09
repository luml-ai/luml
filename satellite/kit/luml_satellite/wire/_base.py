from pydantic import BaseModel, ConfigDict


class PlatformModel(BaseModel):
    model_config = ConfigDict(extra="allow")
