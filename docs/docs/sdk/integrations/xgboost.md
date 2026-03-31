<a id="luml.integrations.xgboost.packaging"></a>

# luml.integrations.xgboost.packaging

<a id="luml.integrations.xgboost.packaging.save_xgboost"></a>

#### save\_xgboost

```python
def save_xgboost(
    estimator: "Union[Booster, xgb.XGBModel]",
    inputs: Any | None = None,
    path: str | None = None,
    dependencies: Literal["default"] | Literal["all"] | list[str] = "default",
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None
) -> ModelReference
```

Save an XGBoost Booster model as a Luml model.

**Arguments**:

- `estimator` - The XGBoost Booster or XGBModel to save.
- `inputs` - Example input data for the model.
- `path` - Path where the model will be saved. Auto-generated if None.
- `dependencies` - Dependency management strategy ("default", "all", or list).
- `extra_dependencies` - Additional pip dependencies to include.
- `extra_code_modules` - Local code modules to package ("auto" or list).
- `manifest_model_name` - Optional name for the model in manifest.
- `manifest_model_version` - Optional version for the model in manifest.
- `manifest_model_description` - Optional description for the model.
- `manifest_extra_producer_tags` - Additional producer tags for model lineage.
  

**Returns**:

- `ModelReference` - Reference to the saved model.

