# Packaging models

A model artifact must run anywhere from its own contents. Use a built-in
`save_*` function when one fits. For anything else, write a custom `PyFunc`.
Either way, check the result in a fresh environment
([verify-artifact.md](verify-artifact.md)).

## Built-in save functions

| Framework | Function | Notes |
| --- | --- | --- |
| scikit-learn | `luml.integrations.sklearn.save_sklearn(estimator, inputs, ...)` | `inputs` required. Also takes `reference_data` and `horizons` ([monitoring.md](monitoring.md)). |
| XGBoost | `luml.integrations.xgboost.save_xgboost(estimator, inputs, ...)` | sklearn-API estimators go through `save_sklearn`. |
| LightGBM | `luml.integrations.lightgbm.save_lightgbm(estimator, inputs, ...)` | Same. |
| CatBoost | `luml.integrations.catboost.save_catboost(estimator, inputs, ...)` | |
| LangGraph | `luml.integrations.langgraph.save_langgraph(graph, ...)` | `env_vars=["OPENAI_API_KEY"]` declares secrets the deployment must supply. |

`tracker.log_model(model, inputs=...)` picks the function by the model's module
and passes the arguments below through.

- `inputs`: a sample of the training features. A DataFrame gives each column its
  name and type, and each column becomes one input of the model. Prefer a
  DataFrame with the real column names.
- `input_format` (XGBoost, LightGBM, CatBoost): keep the default `"unified"`, one
  input per feature. `"native"` takes one JSON payload; monitoring cannot read
  features from it.
- `path`: where to write the file. Default: a generated name in the working
  directory.
- `manifest_model_name`, `manifest_model_version`, `manifest_model_description`:
  the model's name, version and description in its manifest.

## Dependencies and local code

- `dependencies="default"`: the framework and its core packages, pinned to the
  installed versions.
- `extra_dependencies=["pandas==2.2.3"]`: add packages the model imports at load
  or predict time. Prefer this over replacing the defaults.
- `dependencies="all"`: every package the environment imports. Use it when you
  cannot list them.
- `extra_code_modules=["features"]`: bundle a local module or package that the
  model needs, such as a custom transformer class. `"auto"` finds local modules
  by itself. A local class that is not bundled is the most common reason an
  artifact fails elsewhere.

## Custom models (PyFunc)

Use a custom `PyFunc` for any model without a `save_*` function: PyTorch, a
statistical model, an ensemble, an LLM chain, a rules engine.

How it works:

- `PyfuncBuilder(pyfunc=YourClass)` copies **the whole source file** that defines
  the class into the artifact. Keep the class in its own small module. Every
  import in that file must be available in the artifact's environment.
- The class implements `warmup()` (load once), `compute()` and `compute_async()`.
  All three are abstract; leaving one out fails at load time.
- Files are added with `add_file(path, name)` and read back with
  `self.fnnx_context.get_filepath(name)`. Small settings go through
  `set_extra_values({...})` and `self.fnnx_context.get_value(key)`.
- Every package the model imports at runtime is declared with
  `add_runtime_dependency("package==version")`, including numpy, which array
  inputs need. `add_fnnx_runtime_dependency()` adds fnnx itself.
- Conda packages the environment needs before pip runs (system libraries,
  compilers, CUDA) go in `add_build_dependency("package")`.
- Local helper modules go in `add_module("path/to/module")`.

### Tabular model

`tabular_pyfunc.py`, the file that is copied into the artifact:

```python
from fnnx.variants.pyfunc import PyFunc


class TabularModel(PyFunc):
    def warmup(self) -> None:
        import cloudpickle
        import numpy as np

        self.np = np
        with open(self.fnnx_context.get_filepath("model.pkl"), "rb") as file:
            self.model = cloudpickle.load(file)
        self.features = self.fnnx_context.get_value("features")

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        rows = self.np.column_stack([inputs[name] for name in self.features])
        return {"y": self.model.predict(rows)}

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        return self.compute(inputs, dynamic_attributes)
```

The build script:

```python
import tempfile
from importlib.metadata import version

import cloudpickle
from fnnx.extras.builder import PyfuncBuilder
from fnnx.extras.pydantic_models.manifest import NDJSON

from luml import PRODUCER_NAME
from luml.artifacts.model import ModelReference
from tabular_pyfunc import TabularModel

features = list(X_train.columns)

builder = PyfuncBuilder(pyfunc=TabularModel, model_name="churn-ranker")
builder.set_producer_info(
    name=PRODUCER_NAME,
    version=version("luml_sdk"),
    tags=[f"{PRODUCER_NAME}::kind_tabular:v1"],
)
for name in features:
    builder.add_input(
        NDJSON(name=name, content_type="NDJSON", dtype="Array[float]", shape=["batch"])
    )
builder.add_output(
    NDJSON(name="y", content_type="NDJSON", dtype="Array[float]", shape=["batch"])
)
builder.set_extra_values({"features": features})

with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as file:
    cloudpickle.dump(model, file)
builder.add_file(file.name, "model.pkl")

builder.add_fnnx_runtime_dependency()
for package in ["numpy", "cloudpickle", "scikit-learn"]:
    builder.add_runtime_dependency(f"{package}=={version(package)}")

builder.save("churn-ranker.luml")
model_ref = ModelReference("churn-ranker.luml")
```

- One input per feature, named like the training columns. Monitoring matches
  live requests to the profile by these names.
- The kind tag (`kind_tabular` or `kind_llm`) tells the platform what kind of
  model this is.
- A class defined in a local module is pickled by reference: the artifact then
  needs that module. Either bundle it with `add_module`, or call
  `cloudpickle.register_pickle_by_value(module)` before `cloudpickle.dump` so the
  class travels inside the pickle.

### LLM chain

An LLM chain takes and returns JSON. The API key is declared as a runtime secret,
so the deployment asks for it and the artifact never contains it.

`chain_pyfunc.py`:

```python
from fnnx.variants.pyfunc import PyFunc


class SupportAnswer(PyFunc):
    def warmup(self) -> None:
        from openai import OpenAI

        self.client = OpenAI()
        self.model = self.fnnx_context.get_value("model")
        self.system_prompt = self.fnnx_context.get_value("system_prompt")

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        question = inputs["payload"]["question"]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question},
            ],
        )
        return {"answer": {"text": response.choices[0].message.content}}

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        return self.compute(inputs, dynamic_attributes)
```

The build script:

```python
from importlib.metadata import version

from fnnx.extras.builder import PyfuncBuilder
from fnnx.extras.pydantic_models.manifest import JSON, Var
from pydantic import BaseModel

from luml import PRODUCER_NAME
from chain_pyfunc import SupportAnswer


class Question(BaseModel):
    question: str


class Answer(BaseModel):
    text: str


builder = PyfuncBuilder(pyfunc=SupportAnswer, model_name="support-answer")
builder.set_producer_info(
    name=PRODUCER_NAME,
    version=version("luml_sdk"),
    tags=[f"{PRODUCER_NAME}::kind_llm:v1"],
)
builder.define_dtype("ext::question", Question)
builder.define_dtype("ext::answer", Answer)
builder.add_input(JSON(name="payload", content_type="JSON", dtype="ext::question"))
builder.add_output(JSON(name="answer", content_type="JSON", dtype="ext::answer"))
builder.add_env_var(
    Var(
        name="OPENAI_API_KEY",
        description="OpenAI API key",
        tags=["dataforce.studio::runtime_secret:v1"],
    )
)
builder.set_extra_values({"model": "gpt-4.1-mini", "system_prompt": SYSTEM_PROMPT})
builder.add_fnnx_runtime_dependency()
builder.add_runtime_dependency(f"openai=={version('openai')}")
builder.save("support-answer.luml")
```

Put the prompts and the model name in the artifact (`set_extra_values` or
`add_file`), not in code that reads them from the project at runtime.

## Model cards

A card is an HTML page stored in the artifact and shown in the registry.

```python
from luml import CardBuilder

card = CardBuilder(title="Churn ranker")
card.write_heading("Performance", level=2)
card.write_markdown("Trained on **90 days** of events.")
card.write(metrics_frame)   # DataFrame, matplotlib or plotly figure, PIL image, bytes, Path
model_ref.add_model_card(card)
```

`write()` inlines images and tables, so the card is one portable page. Add the
card to a model you saved yourself, before logging or uploading it. The
`ModelReference` that `log_model` returns points into the store; do not modify
it.
