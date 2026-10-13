"""Type-checking stubs for cell authors. Nothing here runs.

Cell files import nothing at runtime — a cell is read by parsing it, and the
source a run executes is the class node alone. These names exist so a scaffold's
conformance footer and an author's editor have something to check against, which
is why this is a distribution of its own: it can be installed into the workspace
venv as a dev dependency without putting lumlflow code there.

The protocol's members are read-only on purpose. `materialize` takes a named
parameter per declared input, so no fixed signature describes it — what can be
checked is that it exists and returns the outputs by name. `produces` is read as
data, and a read-only member is what lets a cell's plain `{"model": "asset"}`
satisfy it without anyone annotating a literal type.
"""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

__all__ = ["AssetType", "CellProtocol", "Ctx", "ExperimentRef", "Tracker"]

AssetType = Literal["model", "dataset", "experiment", "asset"]


class ExperimentRef(Protocol):
    experiment_id: str
    group: str
    store: Path
    snapshot: Mapping[str, Mapping[str, Any]]


class Tracker(Protocol):
    def log_param(self, name: str, value: Any) -> None: ...

    def log_params(self, values: Mapping[str, Any]) -> None: ...

    def log_metric(self, name: str, value: float, step: int | None = None) -> None: ...

    def log_metrics(
        self, values: Mapping[str, float], step: int | None = None
    ) -> None: ...

    @property
    def record(self) -> ExperimentRef: ...


class Ctx(Protocol):
    """What a cell is handed. Reading `branch` or `step` marks the run
    identity-dependent; reading either path marks it `external`."""

    branch: str
    step: int
    workspace_dir: Path
    flow_dir: Path
    tracker: Tracker

    def seed(self) -> None:
        """Apply `params["seed"]` to the random sources this process holds."""
        ...

    def tempdir(self) -> Path:
        """A scratch directory that lives as long as the run does."""
        ...


@runtime_checkable
class CellProtocol(Protocol):
    """The shape acceptance looks for: declarations, and a `materialize`.

    `consumes`, `params` and `volatility` are optional — a source cell declares
    only what it produces.
    """

    # Deliberately `Any` per output: a plain `{"model": "asset"}` reads as
    # `dict[str, str]`, and the four-word vocabulary is checked at acceptance —
    # in words, with a flag — rather than by refusing to describe the cell.
    @property
    def produces(self) -> Mapping[str, Any]: ...

    @property
    def materialize(self) -> Callable[..., Mapping[str, Any]]: ...
