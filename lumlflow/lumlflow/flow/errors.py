class FlowError(Exception):
    pass


class FlowNotFound(FlowError):
    pass


class FlowAlreadyExists(FlowError):
    pass


class FlowAmbiguous(FlowError):
    pass


class ServerError(FlowError):
    pass


class KernelError(FlowError):
    pass


class EnvError(FlowError):
    pass


class JournalCorruption(FlowError):
    pass


class BranchNotFound(FlowError):
    pass


class BranchAlreadyExists(FlowError):
    pass


class CellNotFound(FlowError):
    pass


class InputUnavailable(FlowError):
    pass


class ValueNotStored(FlowError):
    pass


class RewindTargetNotFound(FlowError):
    pass


class LaneMoved(FlowError):
    def __init__(self, message: str, *, branch: str, to_step: int, by: str) -> None:
        super().__init__(message)
        self.branch = branch
        self.to_step = to_step
        self.by = by


class CellClaimed(FlowError):
    def __init__(self, message: str, *, slug: str, holder: str, label: str) -> None:
        super().__init__(message)
        self.slug = slug
        self.holder = holder
        self.label = label


class EditConflict(FlowError):
    def __init__(
        self,
        message: str,
        *,
        slug: str,
        branch: str,
        base: str,
        head: str,
        head_author: str,
    ) -> None:
        super().__init__(message)
        self.slug = slug
        self.branch = branch
        self.base = base
        self.head = head
        self.head_author = head_author


class AdoptConflict(FlowError):
    def __init__(
        self,
        message: str,
        *,
        slug: str,
        from_branch: str,
        to_branch: str,
        definition: bool = False,
        namespace: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.slug = slug
        self.from_branch = from_branch
        self.to_branch = to_branch
        self.definition = definition
        self.namespace = namespace
