import re
import sys
import types
from unittest.mock import MagicMock, patch

NAME_PATTERN = re.compile(r"^[a-z]+-[a-z]+-\d{3}$")


def _ensure_sdk_stubs() -> None:
    """Stub out the sdk.* namespace so tracker.py can be imported.

    tracker.py uses ``from sdk.luml.<x>`` imports that resolve only when the
    package is installed as an editable "sdk" namespace.  In the test venv the
    package is installed as "luml", so we create thin shims that re-export the
    real modules.
    """
    if "sdk" in sys.modules:
        return

    import luml  # real, installed package

    sdk_pkg = types.ModuleType("sdk")
    sdk_pkg.__path__ = []  # type: ignore[attr-defined]
    sys.modules["sdk"] = sdk_pkg
    sys.modules["sdk.luml"] = luml

    # Walk every already-imported luml.* sub-module and mirror it under sdk.luml.*
    for name, mod in list(sys.modules.items()):
        if name.startswith("luml.") and mod is not None:
            sys.modules[f"sdk.{name}"] = mod


_ensure_sdk_stubs()

from luml.experiments.tracker import ExperimentTracker  # noqa: E402


def _make_tracker(tmp_path: object) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path}/experiments")


def test_unnamed_experiment_gets_generated_name(tmp_path: object) -> None:
    tracker = _make_tracker(tmp_path)
    exp_id = tracker.start_experiment()
    experiment = tracker.get_experiment(exp_id)
    assert experiment.metadata.name is not None
    assert NAME_PATTERN.match(experiment.metadata.name)


def test_named_experiment_keeps_explicit_name(tmp_path: object) -> None:
    tracker = _make_tracker(tmp_path)
    exp_id = tracker.start_experiment(name="my_experiment")
    experiment = tracker.get_experiment(exp_id)
    assert experiment.metadata.name == "my_experiment"


def test_unnamed_experiment_does_not_use_uuid(tmp_path: object) -> None:
    tracker = _make_tracker(tmp_path)
    exp_id = tracker.start_experiment()
    experiment = tracker.get_experiment(exp_id)
    assert experiment.metadata.name != exp_id


@patch("luml.experiments.tracker.generate_random_name", return_value="bold-falcon-042")
def test_start_experiment_calls_generator_when_no_name(
    mock_gen: MagicMock, tmp_path: object
) -> None:
    tracker = _make_tracker(tmp_path)
    exp_id = tracker.start_experiment()
    experiment = tracker.get_experiment(exp_id)
    assert experiment.metadata.name == "bold-falcon-042"
    mock_gen.assert_called_once()


@patch("luml.experiments.tracker.generate_random_name")
def test_start_experiment_skips_generator_when_name_provided(
    mock_gen: MagicMock, tmp_path: object
) -> None:
    tracker = _make_tracker(tmp_path)
    tracker.start_experiment(name="explicit")
    mock_gen.assert_not_called()
