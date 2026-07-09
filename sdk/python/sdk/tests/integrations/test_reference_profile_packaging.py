import json
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
