import json
from typing import Any

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from luml.utils.reference_profile import (
    build_reference_profile,
    compute_feature_summaries,
    compute_output_summaries,
    compute_pca_profile,
)

NUMERIC = ["age", "bmi"]
CATEGORICAL = ["sex", "region"]
REGIONS = ["northeast", "northwest", "southeast", "southwest"]


def _mixed_frame(n: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "age": rng.integers(18, 65, size=n),
            "bmi": rng.normal(30.0, 6.0, size=n),
            "sex": rng.choice(["female", "male"], size=n),
            "region": rng.choice(REGIONS, size=n),
        }
    )


def _fit_pipeline(
    frame: pd.DataFrame,
    target: np.ndarray,
    estimator: Any,  # noqa: ANN401
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


def _assert_json_native(obj: Any) -> None:  # noqa: ANN401
    """Recursively assert the object is built only from native JSON types.

    ``json.dumps`` alone would still accept ``np.float64`` (a ``float`` subclass), so
    this guards against numpy scalars leaking into the profile as well.
    """
    if obj is None or isinstance(obj, str | bool):
        return
    if isinstance(obj, int | float):
        assert type(obj) in (int, float), f"non-native number {type(obj)!r}"
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert isinstance(key, str), f"non-string key {type(key)!r}"
            _assert_json_native(value)
        return
    if isinstance(obj, list):
        for value in obj:
            _assert_json_native(value)
        return
    raise AssertionError(f"non-JSON type {type(obj)!r}")


def test_mixed_columns_land_in_correct_group() -> None:
    summaries = compute_feature_summaries(_mixed_frame())

    assert set(summaries["numerical_features"]) == {"age", "bmi"}
    assert set(summaries["categorical_features"]) == {"sex", "region"}


def test_positions_are_1_indexed_over_full_input_order() -> None:
    summaries = compute_feature_summaries(_mixed_frame())

    positions = {
        **{n: s["position"] for n, s in summaries["numerical_features"].items()},
        **{n: s["position"] for n, s in summaries["categorical_features"].items()},
    }
    assert positions == {"age": 1, "bmi": 2, "sex": 3, "region": 4}


def test_categorical_override_moves_numeric_column() -> None:
    frame = pd.DataFrame({"children": [0, 1, 2, 2, 3, 0]})

    summaries = compute_feature_summaries(
        frame, categorical_features={"children": ["0", "1", "2", "3"]}
    )

    assert "children" not in summaries["numerical_features"]
    children = summaries["categorical_features"]["children"]
    assert children["categories"] == ["0", "1", "2", "3"]
    assert children["frequencies"] == [2, 1, 2, 1]


def test_numerical_summary_histogram_is_aligned_and_normalized() -> None:
    summaries = compute_feature_summaries(_mixed_frame(), bins=10)
    bmi = summaries["numerical_features"]["bmi"]

    n_bins = len(bmi["frequencies"])
    assert len(bmi["bin_edges"]) == n_bins + 1
    assert len(bmi["bin_centres"]) == n_bins
    assert len(bmi["probabilities"]) == n_bins
    assert sum(bmi["frequencies"]) == bmi["count"]
    assert sum(bmi["probabilities"]) == pytest.approx(1.0)
    assert set(bmi["quantiles"]) == {"q05", "q25", "q50", "q75", "q95"}


def test_categorical_summary_probabilities_sum_to_one() -> None:
    summaries = compute_feature_summaries(_mixed_frame())
    region = summaries["categorical_features"]["region"]

    assert region["categories"] == REGIONS
    assert region["n_unique"] == 4
    assert len(region["frequencies"]) == len(region["categories"])
    assert all(isinstance(key, str) for key in region["probabilities"])
    assert sum(region["probabilities"].values()) == pytest.approx(1.0)
    assert sum(region["frequencies"]) == region["count"]


def test_missing_values_are_counted() -> None:
    frame = pd.DataFrame(
        {
            "num": [1.0, 2.0, np.nan, 4.0],
            "cat": ["a", None, "b", "a"],
        }
    )

    summaries = compute_feature_summaries(frame)

    num = summaries["numerical_features"]["num"]
    assert num["count"] == 3
    assert num["missing"] == 1

    cat = summaries["categorical_features"]["cat"]
    assert cat["count"] == 3
    assert cat["missing"] == 1


def test_regression_output_summary_under_numerical_outputs() -> None:
    predictions = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

    summaries = compute_output_summaries(predictions, "regression")

    assert "categorical_outputs" not in summaries
    y_pred = summaries["numerical_outputs"]["y_pred"]
    assert y_pred["position"] == 1
    assert y_pred["count"] == 5
    assert y_pred["min"] == pytest.approx(10.0)
    assert y_pred["max"] == pytest.approx(50.0)


def test_classification_output_summary_under_categorical_outputs() -> None:
    predictions = np.array(["cat", "dog", "cat", "cat", "dog"])

    summaries = compute_output_summaries(predictions, "classification")

    assert "numerical_outputs" not in summaries
    y_pred = summaries["categorical_outputs"]["y_pred"]
    assert y_pred["categories"] == ["cat", "dog"]
    assert y_pred["probabilities"]["cat"] == pytest.approx(0.6)
    assert y_pred["probabilities"]["dog"] == pytest.approx(0.4)


def test_classification_scores_summarized_numerically() -> None:
    predictions = np.array([0, 1, 1, 0])
    scores = {"y_score": np.array([0.9, 0.8, 0.7, 0.95])}

    summaries = compute_output_summaries(predictions, "classification", scores=scores)

    assert "categorical_outputs" in summaries
    assert "y_score" in summaries["numerical_outputs"]
    assert summaries["numerical_outputs"]["y_score"]["count"] == 4


def test_unknown_task_type_raises() -> None:
    with pytest.raises(ValueError, match="task type"):
        compute_output_summaries(np.array([1.0, 2.0]), "clustering")  # type: ignore[arg-type]


def test_build_regression_profile_end_to_end() -> None:
    frame = _mixed_frame()
    target = 200.0 * frame["age"] + 300.0 * frame["bmi"]
    pipe = _fit_pipeline(frame, target.to_numpy(), LinearRegression())

    profile = build_reference_profile(frame, "regression", pipe.predict)

    assert {"feature_summaries", "output_summaries"} <= set(profile)
    features = profile["feature_summaries"]
    assert set(features["numerical_features"]) == {"age", "bmi"}
    assert set(features["categorical_features"]) == {"sex", "region"}
    assert "y_pred" in profile["output_summaries"]["numerical_outputs"]
    assert "categorical_outputs" not in profile["output_summaries"]


def test_build_classification_profile_with_scores() -> None:
    frame = _mixed_frame()
    target = (frame["age"] > 40).astype(int).to_numpy()
    pipe = _fit_pipeline(frame, target, LogisticRegression(max_iter=1000))

    profile = build_reference_profile(
        frame, "classification", pipe.predict, predict_proba=pipe.predict_proba
    )

    outputs = profile["output_summaries"]
    y_pred = outputs["categorical_outputs"]["y_pred"]
    assert sum(y_pred["probabilities"].values()) == pytest.approx(1.0)
    assert "y_score" in outputs["numerical_outputs"]


def test_profile_is_json_only() -> None:
    frame = _mixed_frame()
    target = 200.0 * frame["age"] + 300.0 * frame["bmi"]
    pipe = _fit_pipeline(frame, target.to_numpy(), LinearRegression())

    profile = build_reference_profile(frame, "regression", pipe.predict)

    encoded = json.dumps(profile)
    assert json.loads(encoded) == profile
    _assert_json_native(profile)


def test_numpy_array_features_without_column_names() -> None:
    features = np.arange(12.0).reshape(6, 2)

    summaries = compute_feature_summaries(features)

    assert set(summaries["numerical_features"]) == {"x0", "x1"}
    assert summaries["categorical_features"] == {}


def test_pca_profile_covers_numerical_features_in_order() -> None:
    profile = compute_pca_profile(_mixed_frame())

    assert profile["pca"]["feature_names"] == ["age", "bmi"]
    assert profile["pca"]["n_features"] == 2
    assert profile["scaler"]["n_features"] == 2
    for key in ("mean_", "scale_", "var_"):
        assert len(profile["scaler"][key]) == 2


def test_pca_component_matrix_shape_matches_components_by_features() -> None:
    profile = compute_pca_profile(_mixed_frame())
    pca = profile["pca"]

    components = pca["components"]
    assert len(components) == pca["n_components"]
    assert all(len(row) == pca["n_features"] for row in components)
    assert len(pca["mean_"]) == pca["n_features"]


def test_reference_distribution_has_mean_vector_and_square_covariance() -> None:
    frame = _mixed_frame()

    ref = compute_pca_profile(frame)["reference_distribution"]

    n_components = ref["n_components"]
    assert len(ref["mean"]) == n_components
    assert len(ref["covariance"]) == n_components
    assert all(len(row) == n_components for row in ref["covariance"])
    assert ref["n_samples"] == len(frame)


def test_pca_excludes_categorical_columns() -> None:
    frame = _mixed_frame()

    assert set(compute_pca_profile(frame)["pca"]["feature_names"]) == {"age", "bmi"}

    overridden = compute_pca_profile(frame, categorical_features={"age": ["18", "19"]})
    assert overridden["pca"]["feature_names"] == ["bmi"]


def test_pca_profile_empty_without_numerical_features() -> None:
    frame = pd.DataFrame({"sex": ["m", "f", "m"], "region": ["a", "b", "a"]})

    assert compute_pca_profile(frame) == {}


def test_single_numerical_feature_gives_1x1_covariance() -> None:
    frame = pd.DataFrame({"x": np.linspace(0.0, 10.0, 50), "cat": ["a", "b"] * 25})

    profile = compute_pca_profile(frame)

    assert profile["pca"]["feature_names"] == ["x"]
    ref = profile["reference_distribution"]
    assert ref["n_components"] == 1
    assert len(ref["covariance"]) == 1
    assert len(ref["covariance"][0]) == 1


def test_pca_profile_drops_rows_with_missing_numerical_values() -> None:
    frame = pd.DataFrame(
        {
            "a": [1.0, 2.0, np.nan, 4.0, 5.0],
            "b": [5.0, 4.0, 3.0, 2.0, 1.0],
        }
    )

    ref = compute_pca_profile(frame)["reference_distribution"]

    assert ref["n_samples"] == 4


def test_pca_profile_is_json_only() -> None:
    profile = compute_pca_profile(_mixed_frame())

    assert json.loads(json.dumps(profile)) == profile
    _assert_json_native(profile)


def test_pca_profile_is_deterministic() -> None:
    frame = _mixed_frame()

    assert compute_pca_profile(frame) == compute_pca_profile(frame)


def test_build_profile_includes_pca_over_numerical_features() -> None:
    frame = _mixed_frame()
    target = 200.0 * frame["age"] + 300.0 * frame["bmi"]
    pipe = _fit_pipeline(frame, target.to_numpy(), LinearRegression())

    profile = build_reference_profile(frame, "regression", pipe.predict)

    assert {"feature_summaries", "output_summaries", "pca_profile"} <= set(profile)
    assert profile["pca_profile"]["pca"]["feature_names"] == ["age", "bmi"]
