<a id="luml.artifacts.model"></a>

# luml.artifacts.model

<a id="luml.artifacts.model.ModelReference"></a>

## ModelReference Objects

```python
class ModelReference(DiskReference)
```

<a id="luml.artifacts.model.ModelReference.add_reference_profile"></a>

#### add_reference_profile

```python
def add_reference_profile(
        reference_data: Any,
        *,
        horizons: list[str] | None = None
) -> dict[str, Any]
```

Build and embed a monitoring profile in a local sklearn artifact.

