from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from lumlflow.schemas.base import BaseOrmConfig


class AnnotationKind(StrEnum):
    FEEDBACK = "feedback"
    EXPECTATION = "expectation"


class AnnotationValueType(StrEnum):
    INT = "int"
    BOOL = "bool"
    STRING = "string"


class CreateAnnotation(BaseModel):
    annotation_kind: AnnotationKind
    value_type: AnnotationValueType
    value: int | bool | str
    user: str


class Annotation(BaseModel, BaseOrmConfig):
    id: str
    annotation_kind: AnnotationKind
    value_type: AnnotationValueType
    value: int | bool | str
    user: str
    created_at: datetime
