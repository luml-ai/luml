<a id="luml.integrations.sklearn.packaging"></a>

# luml.integrations.sklearn.packaging

<a id="luml.integrations.sklearn.packaging.save_sklearn"></a>

#### save_sklearn

```python
def save_sklearn(
        estimator: "BaseEstimator",
        inputs: Any,
        path: str | None = None,
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

Save scikit-learn model to LUML format for deployment.

Packages a trained sklearn estimator with its dependencies and input/output
schema for production deployment or model registry.

**Arguments**:

- `estimator` - Trained scikit-learn estimator (must implement .predict()).
- `inputs` - Example input data for schema inference. Can be numpy array or pandas DataFrame.
- `path` - Output file path. Auto-generated if not provided.
- `dependencies` - Dependency management strategy:
  - "default": Include scikit-learn, numpy, scipy, cloudpickle
  - "all": Auto-detect all dependencies
  - list: Custom dependency list
- `extra_dependencies` - Additional pip packages to include.
- `extra_code_modules` - Local code modules to bundle.
  - None: Don't include local modules
  - "auto": Auto-detect local dependencies
  - list: Specific modules to include
- `manifest_model_name` - Model name for metadata.
- `manifest_model_version` - Model version for metadata.
- `manifest_model_description` - Model description for metadata.
- `manifest_extra_producer_tags` - Additional tags for model metadata.
  

**Returns**:

- `ModelReference` - Reference to the saved model package.
  

**Example**:

```python
from sklearn.ensemble import RandomForestClassifier
from luml.integrations.sklearn import save_sklearn
import numpy as np

# Train model
model = RandomForestClassifier()
X_train = np.random.rand(100, 4)
y_train = np.random.randint(0, 2, 100)
model.fit(X_train, y_train)

# Save model
model_ref = save_sklearn(
    model,
    X_train,
    path="my_model.luml",
    manifest_model_name="iris_classifier",
    manifest_model_version="1.0.0"
)
```

