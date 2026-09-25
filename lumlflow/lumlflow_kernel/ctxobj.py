"""`ctx` — everything a cell may reach for that is not one of its inputs.

Two of these handles change what the runtime may claim about a run, so reading
them is recorded as a fact rather than trusted to a declaration: a cell that
reads `branch` or `step` is identity-dependent and never claims a cross-branch
memo hit, and a cell that reaches into the workspace or the flow directory is
`external` and never memoizes at all.
"""

from __future__ import annotations

import random
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumlflow_kernel.tracker import Tracker

IDENTITY = "identity"
EXTERNAL = "external"

Observe = Callable[[str, str], None]


class Ctx:
    def __init__(
        self,
        *,
        branch: str,
        step: int,
        workspace_dir: Path,
        flow_dir: Path,
        params: dict[str, Any],
        scratch: Path,
        observe: Observe,
        tracker: Tracker | None = None,
    ) -> None:
        self._branch = branch
        self._step = step
        self._workspace_dir = workspace_dir
        self._flow_dir = flow_dir
        self._params = params
        self._scratch = scratch
        self._observe = observe
        self._tracker = tracker

    @property
    def branch(self) -> str:
        self._observe(IDENTITY, "the cell read `ctx.branch`")
        return self._branch

    @property
    def step(self) -> int:
        self._observe(IDENTITY, "the cell read `ctx.step`")
        return self._step

    @property
    def workspace_dir(self) -> Path:
        self._observe(EXTERNAL, "the cell read `ctx.workspace_dir`")
        return self._workspace_dir

    @property
    def flow_dir(self) -> Path:
        self._observe(EXTERNAL, "the cell read `ctx.flow_dir`")
        return self._flow_dir

    @property
    def tracker(self) -> Tracker:
        """This run's recorder. Reading it observes nothing: it reaches no
        branch, no file outside the flow, and no network."""
        if self._tracker is None:
            raise RuntimeError(
                "`ctx.tracker` requires this cell to declare an `experiment` output"
            )
        return self._tracker

    def seed(self) -> None:
        """Apply the cell's declared seed to every generator already loaded.

        Loaded, not imported: importing numpy or torch to seed them would make
        a cell that uses neither pay for both.
        """
        seed = self._params.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError(
                "`ctx.seed()` needs a whole-number `seed` in this cell's `params`"
            )
        random.seed(seed)
        numpy = sys.modules.get("numpy")
        if numpy is not None:
            numpy.random.seed(seed % 2**32)
        torch = sys.modules.get("torch")
        if torch is not None:
            torch.manual_seed(seed)

    def tempdir(self) -> Path:
        """A directory that lives as long as the run does."""
        return Path(tempfile.mkdtemp(dir=self._scratch))
