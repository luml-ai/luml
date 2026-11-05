from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumlflow_kernel.tracker import SdkTrackerClient, Tracker


class _FakeSdk:
    """The shape of `luml.experiments.tracker.ExperimentTracker` methods."""

    current_experiment_id = "someone-else"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def log_model(
        self, model: Any, *, name: str | None = None, experiment_id: str | None = None
    ) -> str:
        self.calls.append(
            ("log_model", (model,), {"name": name, "experiment_id": experiment_id})
        )
        return "stored"

    def get_experiment(self, experiment_id: str) -> str:
        self.calls.append(("get_experiment", (), {"experiment_id": experiment_id}))
        return experiment_id

    def list_groups(self) -> list[str]:
        self.calls.append(("list_groups", (), {}))
        return ["churn"]

    def end_experiment(self, experiment_id: str | None = None) -> None:
        self.calls.append(("end_experiment", (), {"experiment_id": experiment_id}))


def _tracker(client: Any) -> Tracker:
    return Tracker(
        client,
        experiment_id="exp-1",
        group="churn",
        store=Path("/store"),
        params={},
    )


def test_an_sdk_method_reaches_the_run_experiment() -> None:
    sdk = _FakeSdk()

    assert _tracker(sdk).log_model("model", name="rf") == "stored"

    assert sdk.calls == [
        ("log_model", ("model",), {"name": "rf", "experiment_id": "exp-1"})
    ]


def test_a_required_experiment_id_is_filled_with_the_run_experiment() -> None:
    assert _tracker(_FakeSdk()).get_experiment() == "exp-1"


def test_an_explicit_experiment_id_is_kept() -> None:
    tracker = _tracker(_FakeSdk())

    assert tracker.get_experiment("exp-2") == "exp-2"
    assert tracker.get_experiment(experiment_id="exp-3") == "exp-3"


def test_a_method_without_an_experiment_id_passes_through() -> None:
    assert _tracker(_FakeSdk()).list_groups() == ["churn"]


def test_a_plain_attribute_passes_through() -> None:
    assert _tracker(_FakeSdk()).current_experiment_id == "someone-else"


def test_binding_reaches_through_the_retrying_sdk_client() -> None:
    sdk = _FakeSdk()
    client = SdkTrackerClient(sdk, store=Path("/store"), sdk_version="1.0")

    _tracker(client).log_model("model")

    assert sdk.calls[-1][2]["experiment_id"] == "exp-1"


@pytest.mark.parametrize(
    ("name", "hint"),
    [
        ("end_experiment", "kernel completes"),
        ("log_static", "`log_param`"),
        ("log_dynamic", "`log_metric`"),
        ("set_experiment_metadata", "`update_experiment_metadata`"),
    ],
)
def test_a_kernel_owned_method_is_refused_with_its_reason(name: str, hint: str) -> None:
    sdk = _FakeSdk()

    with pytest.raises(AttributeError, match=hint):
        getattr(_tracker(sdk), name)
    assert sdk.calls == []


def test_an_unknown_method_is_an_attribute_error() -> None:
    with pytest.raises(AttributeError):
        _ = _tracker(_FakeSdk()).log_nothing


def test_private_names_never_reach_the_sdk() -> None:
    with pytest.raises(AttributeError):
        _ = _tracker(_FakeSdk())._internal
