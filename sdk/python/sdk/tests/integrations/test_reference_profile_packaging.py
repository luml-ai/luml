import json
import pathlib
import subprocess
import sys
import tarfile
import textwrap
from typing import Any

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from luml.artifacts.model import ModelReference
from luml.integrations.sklearn import save_sklearn
from luml.utils.packaging import REFERENCE_PROFILE_FILENAME, REFERENCE_PROFILE_TAG

NUMERIC = ["age", "bmi"]
CATEGORICAL = ["sex", "region"]
REGIONS = ["northeast", "northwest", "southeast", "southwest"]


def _frame(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "age": rng.integers(18, 65, size=n),
            "bmi": rng.normal(30.0, 6.0, size=n),
            "sex": rng.choice(["female", "male"], size=n),
            "region": rng.choice(REGIONS, size=n),
        }
    )


def _pipeline(
    estimator: Any,  # noqa: ANN401
    frame: pd.DataFrame,
    target: np.ndarray,
) -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", "passthrough", NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ]
    )
    pipe = Pipeline([("pre", pre), ("est", estimator)])
    pipe.fit(frame, target)
    return pipe


def _producer_tags(path: str) -> list[str]:
    with tarfile.open(path, "r:*") as tar:
        extracted = tar.extractfile("manifest.json")
        assert extracted is not None
        raw = extracted.read()
    return json.loads(raw)["producer_tags"]


def _profile_bytes(path: str) -> bytes | None:
    with tarfile.open(path, "r:*") as tar:
        for member in tar.getmembers():
            if member.name.endswith(REFERENCE_PROFILE_FILENAME):
                extracted = tar.extractfile(member)
                assert extracted is not None
                return extracted.read()
    return None


def _read_profile(path: str) -> dict[str, Any] | None:
    raw = _profile_bytes(path)
    return None if raw is None else json.loads(raw)


@pytest.fixture(scope="module")
def regression_artifact(tmp_path_factory: pytest.TempPathFactory) -> str:
    frame = _frame()
    target = (frame["age"] * 10 + frame["bmi"] * 5).to_numpy()
    model = _pipeline(LinearRegression(), frame, target)
    path = str(tmp_path_factory.mktemp("sk") / "reg.luml")
    save_sklearn(model, frame, path=path, reference_data=frame)
    return path


@pytest.fixture(scope="module")
def classification_artifact(tmp_path_factory: pytest.TempPathFactory) -> str:
    frame = _frame()
    target = (frame["age"] > 40).astype(int).to_numpy()
    model = _pipeline(LogisticRegression(max_iter=500), frame, target)
    path = str(tmp_path_factory.mktemp("sk") / "clf.luml")
    save_sklearn(model, frame, path=path, reference_data=frame)
    return path


@pytest.fixture(scope="module")
def no_reference_artifact(tmp_path_factory: pytest.TempPathFactory) -> str:
    frame = _frame()
    target = (frame["age"] * 10).to_numpy()
    model = _pipeline(LinearRegression(), frame, target)
    path = str(tmp_path_factory.mktemp("sk") / "none.luml")
    save_sklearn(model, frame, path=path)
    return path


def _member_names(path: str) -> list[str]:
    with tarfile.open(path, "r:*") as tar:
        return tar.getnames()


def test_profile_sits_at_the_archive_root_next_to_the_manifest(
    regression_artifact: str,
) -> None:
    """The model server reads ``<artifact>/reference_profile.json``; a profile nested
    under ``variant_artifacts/extra_files/`` (where the builder's file API puts it) is
    never found, and the deployment ends up monitored without a baseline."""
    names = _member_names(regression_artifact)

    assert REFERENCE_PROFILE_FILENAME in names
    assert "manifest.json" in names
    assert not [
        name
        for name in names
        if name.endswith(REFERENCE_PROFILE_FILENAME)
        and name != REFERENCE_PROFILE_FILENAME
    ]


def test_embedded_profile_declares_task_type_and_monitored_output(
    regression_artifact: str,
) -> None:
    profile = _read_profile(regression_artifact)
    assert profile is not None

    assert profile["task_type"] == "regression"
    assert profile["profile_status"] == "ready"
    assert profile["output_summary"]["type"] == "numerical"
    reference = profile["pca_profile"]["reference_distribution"]
    assert len(reference["mean"]) == reference["n_components"]
    assert profile["pca_profile"]["reference_projection"]


def test_regression_artifact_has_profile_and_tag(regression_artifact: str) -> None:
    assert REFERENCE_PROFILE_TAG in _producer_tags(regression_artifact)

    profile = _read_profile(regression_artifact)
    assert profile is not None

    features = profile["feature_summaries"]
    assert set(features["numerical_features"]) == {"age", "bmi"}
    assert set(features["categorical_features"]) == {"sex", "region"}
    assert "numerical_outputs" in profile["output_summaries"]

    reference = profile["pca_profile"]["reference_distribution"]
    n_components = reference["n_components"]
    assert len(reference["mean"]) == n_components
    assert len(reference["covariance"]) == n_components
    assert all(len(row) == n_components for row in reference["covariance"])


def test_classification_output_is_categorical_with_score(
    classification_artifact: str,
) -> None:
    assert REFERENCE_PROFILE_TAG in _producer_tags(classification_artifact)

    profile = _read_profile(classification_artifact)
    assert profile is not None

    outputs = profile["output_summaries"]
    assert "categorical_outputs" in outputs
    predicted = next(iter(outputs["categorical_outputs"].values()))
    assert abs(sum(predicted["probabilities"].values()) - 1.0) < 1e-6

    # LogisticRegression exposes predict_proba, so a numerical score is summarized too.
    assert "y_score" in outputs["numerical_outputs"]


def test_no_reference_data_means_no_profile_no_tag(no_reference_artifact: str) -> None:
    assert REFERENCE_PROFILE_TAG not in _producer_tags(no_reference_artifact)
    assert _read_profile(no_reference_artifact) is None
    assert ModelReference(no_reference_artifact).validate()


def test_presence_detected_by_tag_alone(
    regression_artifact: str,
    no_reference_artifact: str,
) -> None:
    assert REFERENCE_PROFILE_TAG in _producer_tags(regression_artifact)
    assert REFERENCE_PROFILE_TAG not in _producer_tags(no_reference_artifact)


def test_embedded_profile_parses_as_plain_json(classification_artifact: str) -> None:
    raw = _profile_bytes(classification_artifact)
    assert raw is not None

    profile = json.loads(raw)  # no custom decoder
    pca = profile["pca_profile"]
    assert all(isinstance(v, float) for v in pca["scaler"]["mean_"])
    assert all(isinstance(v, float) for row in pca["pca"]["components"] for v in row)
    assert all(
        isinstance(v, float)
        for row in pca["reference_distribution"]["covariance"]
        for v in row
    )


def test_sklearn_integration_stays_pandas_optional() -> None:
    """Reference-profile support must not make the sklearn integration hard-require
    pandas: importing it and packaging numpy inputs without ``reference_data`` must
    work with pandas absent. The pandas-dependent canonical profile module is imported
    lazily, only when ``reference_data`` is provided. Runs in a subprocess so pandas
    can be blocked before ``luml`` is first imported.
    """
    script = textwrap.dedent(
        """
        import os
        import sys
        import tempfile

        class _BlockPandas:
            def find_spec(self, name, path=None, target=None):
                if name == "pandas" or name.startswith("pandas."):
                    raise ModuleNotFoundError("No module named 'pandas'")
                return None

        sys.meta_path.insert(0, _BlockPandas())

        import numpy as np
        from sklearn.linear_model import LinearRegression

        from luml.integrations.sklearn import save_sklearn

        model = LinearRegression().fit(np.random.rand(30, 3), np.random.rand(30))
        path = os.path.join(tempfile.mkdtemp(), "m.luml")
        save_sklearn(model, np.random.rand(30, 3), path=path)
        assert os.path.exists(path)
        assert "pandas" not in sys.modules
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_pipeline_artifact_loads_and_predicts(tmp_path: pathlib.Path) -> None:
    """A Pipeline exposes ``feature_names_in_`` as a read-only property forwarded from its
    first step, and the template deletes that attribute so the estimator accepts the
    positional array the pyfunc builds. Deleting it raised AttributeError, and every
    pipeline-backed deployment died on warmup."""
    from fnnx.runtime import Runtime
    from sklearn.preprocessing import StandardScaler

    frame = _frame(n=60)[NUMERIC]
    model = Pipeline([("scale", StandardScaler()), ("est", LinearRegression())]).fit(
        frame, (frame["age"] * 10.0).to_numpy()
    )
    assert hasattr(model, "feature_names_in_")  # what used to break warmup

    path = str(tmp_path / "pipeline.luml")
    save_sklearn(model, frame, path=path, reference_data=frame)

    extracted = tmp_path / "unpacked"
    with tarfile.open(path) as archive:
        archive.extractall(extracted)

    result = Runtime(str(extracted)).compute(
        {name: frame[name].tolist() for name in frame.columns}, {}
    )

    assert len(result["y"]) == len(frame)


def _runtime_dependencies(env: dict) -> list[str]:
    packages = []
    for spec in env.values():
        packages += [dep["package"] for dep in spec.get("dependencies", [])]
    return packages


def _runtime_predict(path: str, tmp_path: pathlib.Path, frame: pd.DataFrame) -> Any:  # noqa: ANN401
    from fnnx.runtime import Runtime

    extracted = tmp_path / f"unpacked-{pathlib.Path(path).stem}"
    with tarfile.open(path) as archive:
        archive.extractall(extracted)
    return Runtime(str(extracted)).compute(
        {name: frame[name].tolist() for name in frame.columns}, {}
    )


def test_mixed_dtype_frame_survives_the_round_trip(tmp_path: pathlib.Path) -> None:
    """Numbers and strings in one frame used to be stacked into a single array, which
    upcast everything to strings; a ColumnTransformer selecting columns by name then died
    with "Specifying the columns using strings is only supported for dataframes"."""
    frame = _frame(n=120)
    target = (frame["age"] * 10.0 + frame["bmi"]).to_numpy()
    model = _pipeline(LinearRegression(), frame, target)

    path = str(tmp_path / "mixed.luml")
    save_sklearn(model, frame, path=path)

    result = _runtime_predict(path, tmp_path, frame)

    assert np.allclose(np.asarray(result["y"]), model.predict(frame))


def test_frame_inputs_declare_their_dtypes_and_bring_pandas(tmp_path: pathlib.Path) -> None:
    frame = _frame(n=60)
    model = _pipeline(LinearRegression(), frame, (frame["age"] * 10.0).to_numpy())

    path = str(tmp_path / "typed.luml")
    save_sklearn(model, frame, path=path)

    extracted = tmp_path / "unpacked-typed"
    with tarfile.open(path) as archive:
        archive.extractall(extracted)
    variant = json.loads((extracted / "variant_config.json").read_text())
    dtypes = variant["extra_values"]["input_dtypes"]

    assert dtypes["age"] == "int"
    assert dtypes["bmi"] == "float"
    assert dtypes["sex"] == "str"
    # the runtime rebuilds the frame, so it needs pandas wherever it runs
    dependencies = _runtime_dependencies(json.loads((extracted / "env.json").read_text()))
    assert any(dep.startswith("pandas==") for dep in dependencies)


def test_array_inputs_keep_the_positional_path(tmp_path: pathlib.Path) -> None:
    """A model fitted on a plain array has no column names to restore, and must not be
    handed a frame — nor drag pandas into its runtime."""
    rng = np.random.default_rng(3)
    x = rng.normal(size=(80, 3))
    model = LinearRegression().fit(x, x[:, 0] * 2.0)

    path = str(tmp_path / "array.luml")
    save_sklearn(model, x, path=path)

    extracted = tmp_path / "unpacked-array"
    with tarfile.open(path) as archive:
        archive.extractall(extracted)
    variant = json.loads((extracted / "variant_config.json").read_text())
    assert "input_dtypes" not in variant["extra_values"]
    dependencies = _runtime_dependencies(json.loads((extracted / "env.json").read_text()))
    assert not any(dep.startswith("pandas==") for dep in dependencies)

    from fnnx.runtime import Runtime

    result = Runtime(str(extracted)).compute(
        {f"x{i}": x[:, i].tolist() for i in range(x.shape[1])}, {}
    )
    assert np.allclose(np.asarray(result["y"]), model.predict(x))
