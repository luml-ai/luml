"""Single seam for MLflow → fnnx model conversion.

Delegates to ``fnnx.extras.mlflow.package_mlflow_model`` (the FNNX converter).
Keeping the call behind this seam means the artifact repository depends on a
single, narrow function rather than the converter's full surface.
"""

from pathlib import Path

from fnnx.extras.mlflow import package_mlflow_model


def convert_mlflow_model_to_fnnx(
    model_dir: Path, output_path: Path, *, name: str | None = None
) -> Path:
    """Convert an MLflow model directory to a single ``.fnnx`` file.

    Args:
        model_dir: Path to an MLflow model directory (one containing an
            ``MLmodel`` descriptor).
        output_path: Destination path for the resulting ``.fnnx`` file. Parent
            directory must already exist.
        name: Optional model name recorded in the package manifest/provenance.

    Returns:
        The ``output_path`` for convenience.
    """
    package_mlflow_model(str(model_dir), str(output_path), name=name)
    return output_path


__all__ = ["convert_mlflow_model_to_fnnx"]
