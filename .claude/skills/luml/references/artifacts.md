# Flow SDK — artifacts: datasets, experiment snapshots, cards

All of these produce a `.tar` on disk wrapped in a reference object
(`DatasetReference`, `ExperimentReference`, `ModelReference`). The reference is
what you hand to `tracker.log_model(...)` or upload with `luml_api`
(see `core-api.md`).

## Tabular datasets

```python
from luml import save_tabular_dataset, load_dataset

ref = save_tabular_dataset(
    data,
    file_format="parquet",   # or "csv"
    chunk_size=None,         # rows per file; splits large frames into chunks
    name=None, description=None, version=None,
    output_path=None,        # defaults to a temp .tar
)
```

Needs `pip install "luml_sdk[datasets]"` (pandas + pyarrow; polars frames are
also accepted, with `[datasets-polars]`).

`data` is accepted in three shapes and normalized:

```python
df                                              # -> subset "default", split "train"
"/path/to/data.parquet"                         # a file path, same shape
{"train": df_tr, "test": df_te}                 # splits of subset "default"
{"en": {"train": ...}, "de": {"train": ...}}    # subsets of splits
```

Mixing dict and non-dict values in one dict raises `ValueError`.

## HuggingFace datasets

```python
from luml import save_hf_dataset

ref = save_hf_dataset(dataset, name=None, description=None,
                      version=None, output_path=None)
```

Needs `pip install "luml_sdk[datasets-hf]"`. Accepts a `Dataset`, a
`DatasetDict`, or a dict of named configs of either.

## Reading a dataset back

```python
ds = load_dataset(ref, cache_dir=None)   # extracts the tar into a content-hashed cache

ds.variant                 # "tabular" | "hf"
ds.subsets                 # list[str]
ds.splits(subset="default")
ds.to_pandas(subset="default", split="train")
ds.to_polars(subset="default", split="train")
ds.to_hf() / ds.to_hf_config(config="default") / ds.to_hf_split(subset, split)   # hf variant only
ds.info()                  # the raw manifest
```

`to_pandas` works for both variants; the `to_hf*` methods raise
`NotImplementedError` on a tabular dataset.

## Experiment snapshots

```python
ref = tracker.export("experiment_data.tar", experiment_id=exp_id)
# or
from luml import save_experiment
ref = save_experiment(tracker, experiment_id, output_path=None)
```

Packs the experiment's database rows and all attachments into one artifact —
this is what gets uploaded to the platform so a run's history travels with its
model.

## Cards

`CardBuilder` (exported as both `luml.CardBuilder` and `luml.ModelCardBuilder`,
the same class) builds a self-contained HTML card:

```python
from luml import ModelCardBuilder

card = ModelCardBuilder(title="Churn model", custom_css=None)
card.write_heading("Performance", level=2)
card.write_markdown("Trained on **90 days** of events.")
card.write(metrics_df)          # dispatches on type
card.write(matplotlib_figure)   # embedded as an image
card.write(plotly_figure)
card.write(pil_image)
card.write_divider()
html = card.build()
```

`write()` accepts text, a pandas DataFrame, a matplotlib or plotly figure, a PIL
image, raw image bytes, or a `Path` to an image — everything is inlined, so the
card is one portable HTML file. `write_html()` inserts raw HTML; every other
text path escapes. All writers return `self`, so calls chain.

Attach a card to an artifact:

```python
model_ref.add_model_card(card)       # or an HTML string
dataset_ref.add_dataset_card(card)
tracker.get_model_card(model_id)     # -> bytes (the zip), for models already logged
```

## Reference profiles (monitoring)

```python
model_ref.add_reference_profile(reference_data, horizons=None)
```

Embeds the training-data profile that deployment monitoring compares live
traffic against — without it, drift panels have no baseline.

Constraints, all enforced with `ValueError`: **sklearn artifacts only**, the
bundled estimator must implement `predict()`, and LLM artifacts are rejected.
The task type is inferred — `classification` when the estimator is a classifier,
otherwise `regression`; passing `horizons` makes it `forecasting`.

Source of truth: `sdk/python/sdk/luml/artifacts/`, `sdk/python/sdk/luml/card/`,
examples in `sdk/python/sdk/examples/`.
