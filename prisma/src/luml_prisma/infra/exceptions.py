class ApplicationError(Exception):
    status_code: int = 400
    message: str = "Application error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.message
        super().__init__(self.message)


class NotFoundError(ApplicationError):
    status_code = 404
    message = "Not found"


class RepositoryNotFoundError(NotFoundError):
    message = "Repository not found"


class TaskNotFoundError(NotFoundError):
    message = "Task not found"


class RunNotFoundError(NotFoundError):
    message = "Run not found"


class NodeNotFoundError(NotFoundError):
    message = "Node not found"


class InvalidOperationError(ApplicationError):
    message = "Invalid operation"


class MergeConflictError(ApplicationError):
    status_code = 409
    message = "Merge conflicts detected"

    def __init__(self, conflicting_files: list[str]) -> None:
        super().__init__(self.message)
        self.conflicting_files = conflicting_files
