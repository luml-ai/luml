"""Facade lookup is safe for detached screens and panels."""

import asyncio
from unittest.mock import Mock

import pytest
from lumlflow.tui.data import DataFacade
from lumlflow.tui.run_manager import RunSpec
from lumlflow.tui.screens.cloud_publish import CloudPublishScreen
from lumlflow.tui.screens.comparison import ComparisonScreen
from lumlflow.tui.screens.eval_detail import EvalDetailScreen
from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen
from lumlflow.tui.screens.experiments import ExperimentsScreen
from lumlflow.tui.screens.groups import GroupsScreen
from lumlflow.tui.screens.run_attach import RunAttachScreen
from lumlflow.tui.screens.trace_detail import TraceDetailScreen
from lumlflow.tui.widgets.attachments_panel import AttachmentsPanel
from lumlflow.tui.widgets.evals_panel import EvalsPanel
from lumlflow.tui.widgets.traces_panel import TracesPanel


@pytest.mark.parametrize(
    ("screen_type", "kwargs"),
    [
        (GroupsScreen, {}),
        (ExperimentsScreen, {"all_experiments": True}),
        (ExperimentDetailScreen, {"experiment_id": "exp"}),
        (
            EvalDetailScreen,
            {"experiment_id": "exp", "dataset_id": "data", "eval_id": "eval"},
        ),
        (TraceDetailScreen, {"experiment_id": "exp", "trace_id": "trace"}),
        (CloudPublishScreen, {}),
        (
            ComparisonScreen,
            {"experiments": [Mock(dynamic_params={}), Mock(dynamic_params={})]},
        ),
        (
            RunAttachScreen,
            {"spec": RunSpec(script="run.py"), "store_uri": "sqlite://store"},
        ),
        (AttachmentsPanel, {"experiment_id": "exp"}),
        (EvalsPanel, {"experiment_id": "exp"}),
        (TracesPanel, {"experiment_id": "exp"}),
    ],
)
@pytest.mark.parametrize("explicit_facade", [False, True])
async def test_detached_facade_lookup(
    screen_type, kwargs, explicit_facade: bool
) -> None:
    facade = Mock(spec=DataFacade) if explicit_facade else None
    screen = screen_type(facade=facade, **kwargs)
    assert await asyncio.to_thread(lambda: screen.facade) is facade
