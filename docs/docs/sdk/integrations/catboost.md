<a id="luml.integrations.catboost.packaging"></a>

# luml.integrations.catboost.packaging

<a id="luml.integrations.catboost.packaging.save_catboost"></a>

#### save\_catboost

```python
def save_catboost(
    estimator: "Union[CatBoost, ctb.CatBoostClassifier, ctb.CatBoostRegressor]",
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

Save a CatBoost model as a Luml model.

**Arguments**:

- `estimator` - The CatBoost model to save (CatBoost, CatBoostClassifier,
  or CatBoostRegressor).
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

