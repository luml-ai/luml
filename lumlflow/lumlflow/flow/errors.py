"""Flow-runtime error surface.

User-facing wording is the CLI's concern; these carry the failure kind so the
surfaces can phrase it. Messages here speak paths and slugs, never uids,
content hashes, or memo keys.
"""


class FlowError(Exception):
    """Base for every flow-runtime failure."""


class FlowNotFound(FlowError):
    pass


class FlowAlreadyExists(FlowError):
    pass


class FlowAmbiguous(FlowError):
    """More than one flow answers to that name. The message names them."""


class ServerError(FlowError):
    """The workspace server could not be reached, started, or would not answer.

    Named for what the user is told, not for what runs: the process is
    plumbing, and the word for it never reaches a surface.
    """


class KernelError(FlowError):
    """The kernel could not be started, or died while a cell was running."""


class EnvError(FlowError):
    """The workspace environment could not be prepared."""


class JournalCorruption(FlowError):
    """A journal line failed to parse and is not a recoverable torn tail."""


class BranchNotFound(FlowError):
    pass


class BranchAlreadyExists(FlowError):
    pass


class CellNotFound(FlowError):
    """No cell of that name in the branch's namespace."""


class InputUnavailable(FlowError):
    """A cell was asked to run against an input nothing on the branch produces."""


class ValueNotStored(FlowError):
    """The output exists as a fact, but its bytes are not in the store to read.

    Either nothing has run it yet, or it is declared `persist: False` and the
    value was never kept. A distinct kind because the answer differs: the first
    is "run it", the second is "materialize and download" — and neither is a
    broken button.
    """


class RewindTargetNotFound(FlowError):
    """No transaction to rewind to, or none this branch existed at."""


class EditConflict(FlowError):
    """A daemon-originated edit started from a version the head has moved past.

    Carries what the overwrite / fork-my-edit menu renders. Nothing is written
    until the caller picks a side.
    """

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
    """Adopt has a side to pick. Carries what the menu renders, resolved by force.

    `definition` is the three-way case — both branches edited the cell since
    they forked. `namespace` names inputs whose reference points at a different
    cell on the target branch, which would silently rewire the adopted version.
    """

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
