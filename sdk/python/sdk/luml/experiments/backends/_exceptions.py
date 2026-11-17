class LumlExperimentsError(Exception):
    def __init__(
        self,
        message: str = "Luml Experiments error",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class LumlFilterError(LumlExperimentsError, ValueError):
    def __init__(
        self,
        message: str = "Invalid filter string",
    ) -> None:
        super().__init__(message)


class ExperimentSchemaError(LumlExperimentsError):
    """The experiment database needs a newer luml-sdk than this one."""

    def __init__(
        self, experiment_id: str, revision: int, required: int, role: str, verb: str
    ) -> None:
        self.experiment_id = experiment_id
        self.revision = revision
        self.required = required
        super().__init__(
            f"Experiment '{experiment_id}' uses schema revision {revision}, which "
            f"needs a newer {role} (revision {required} or later). "
            f"Upgrade luml-sdk to {verb} it."
        )


class ExperimentReaderTooOldError(ExperimentSchemaError):
    def __init__(self, experiment_id: str, revision: int, required: int) -> None:
        super().__init__(experiment_id, revision, required, "reader", "read")


class ExperimentWriterTooOldError(ExperimentSchemaError):
    def __init__(self, experiment_id: str, revision: int, required: int) -> None:
        super().__init__(experiment_id, revision, required, "writer", "write to")


class TooManyBucketsError(LumlExperimentsError, ValueError):
    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(
            f"The request would return more than {limit} metric buckets; "
            "narrow the step range or choose a coarser level."
        )


class InvalidBucketLevelError(LumlExperimentsError, ValueError):
    def __init__(self, level: object, max_level: int) -> None:
        self.level = level
        super().__init__(
            f"The bucket level must be an integer from 0 to {max_level}, got {level!r}."
        )


class LegacyMetricRowsError(LumlExperimentsError, ValueError):
    """Metric rows of an older schema that schema revision 3 cannot store."""

    def __init__(self, count: int, example: str) -> None:
        self.count = count
        self.example = example
        super().__init__(
            f"{count} metric rows have a step that is not an integer or a key that "
            f"is not text (first: {example}). The experiment stays at schema "
            "revision 2: it can still be read and written to, but this luml-sdk "
            "cannot log metrics to it."
        )


class SQLiteVersionError(LumlExperimentsError, RuntimeError):
    def __init__(self, version: str, required: str) -> None:
        super().__init__(
            f"luml-sdk needs SQLite {required} or newer, but this Python uses SQLite "
            f"{version}. Use a Python build linked against a newer SQLite."
        )


class ExportSpaceError(LumlExperimentsError, OSError):
    def __init__(self, experiment_id: str, directory: str, needed_bytes: int) -> None:
        self.experiment_id = experiment_id
        self.directory = directory
        super().__init__(
            f"Not enough disk space to export experiment '{experiment_id}': the "
            f"export writes up to about {needed_bytes / 1e6:.0f} MB of temporary "
            f"files in {directory}. Free some space and export again."
        )
