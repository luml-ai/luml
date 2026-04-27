from luml.experiments.backends._base import Backend
from luml.experiments.backends.sqlite_backend._sqlite_annotations import (
    SQLiteAnnotationMixin,
)
from luml.experiments.backends.sqlite_backend._sqlite_attachments import (
    SQLiteAttachmentMixin,
)
from luml.experiments.backends.sqlite_backend._sqlite_evals import SQLiteEvalMixin
from luml.experiments.backends.sqlite_backend._sqlite_experiments import (
    SQLiteExperimentMixin,
)
from luml.experiments.backends.sqlite_backend._sqlite_models import SQLiteModelMixin
from luml.experiments.backends.sqlite_backend._sqlite_pagination_mixin import (
    SQLitePaginationMixin,
)
from luml.experiments.backends.sqlite_backend._sqlite_traces import SQLiteTraceMixin


class SQLiteBackend(
    SQLiteExperimentMixin,
    SQLiteTraceMixin,
    SQLiteEvalMixin,
    SQLiteAnnotationMixin,
    SQLiteModelMixin,
    SQLiteAttachmentMixin,
    SQLitePaginationMixin,
    Backend,
):
    pass
