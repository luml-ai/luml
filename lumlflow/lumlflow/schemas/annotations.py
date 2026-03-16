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
    name: str
    annotation_kind: AnnotationKind
    value_type: AnnotationValueType
    value: int | bool | str
    user: str | None = None
    rationale: str | None = None


class UpdateAnnotation(BaseModel):
    value: int | bool | str | None = None
    rationale: str | None = None


class Annotation(BaseModel, BaseOrmConfig):
    id: str
    name: str
    annotation_kind: AnnotationKind
    value_type: AnnotationValueType
    value: int | bool | str
    user: str
    created_at: datetime
    rationale: str | None = None


class FeedbackSummaryItem(BaseModel, BaseOrmConfig):
    name: str
    total: int
    counts: dict[str, int]


class ExpectationSummaryItem(BaseModel, BaseOrmConfig):
    name: str
    total: int
    positive: int = 0
    negative: int = 0
    value: str | None = None


class AnnotationSummary(BaseModel, BaseOrmConfig):
    feedback: list[FeedbackSummaryItem]
    expectations: list[ExpectationSummaryItem]
