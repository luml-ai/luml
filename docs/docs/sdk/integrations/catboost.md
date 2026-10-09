<a id="luml.integrations.catboost.packaging"></a>

# luml.integrations.catboost.packaging

<a id="luml.integrations.catboost.packaging.save_catboost"></a>

#### save_catboost

```python
def save_catboost(
        estimator:
    "Union[CatBoost, ctb.CatBoostClassifier, ctb.CatBoostRegressor]",
        inputs: Any,
        path: str | None = None,
        input_format: Literal["unified", "native"] = "unified",
        dependencies: Literal["default"] | Literal["all"]
    | list[str] = "default",
        extra_dependencies: list[str] | None = None,
        extra_code_modules: list[str] | Literal["auto"] | None = None,
        manifest_model_name: str | None = None,
        manifest_model_version: str | None = None,
        manifest_model_description: str | None = None,
        manifest_extra_producer_tags: list[str] | None = None
) -> ModelReference
```

Save a CatBoost model as a Luml model.

**Arguments**:

- `estimator` - The CatBoost model to save (CatBoost, CatBoostClassifier, or CatBoostRegressor).
- `inputs` - Example input data for the model.
- `path` - Path where the model will be saved. Auto-generated if None.
- `input_format` - Input format for inference:
  - "unified": per-feature NDJSON inputs (default).
  - "native": single JSON payload with pool structure and optional
  predict config; supports both dense row data and CSR sparse matrices.
- `dependencies` - Dependency management strategy ("default", "all", or list).
- `extra_dependencies` - Additional pip dependencies to include.
- `extra_code_modules` - Local code modules to package ("auto" or list).
- `manifest_model_name` - Optional name for the model in manifest.
- `manifest_model_version` - Optional version for the model in manifest.
- `manifest_model_description` - Optional description for the model.
- `manifest_extra_producer_tags` - Additional producer tags for model lineage.
  

**Returns**:

- `ModelReference` - Reference to the saved model.

