# Dataset artifacts

A dataset artifact is one `.luml` file with the data and its manifest. Upload it
like any other artifact, and name it in a model's lineage
([upload.md](upload.md)).

## Tabular data

Install `luml_sdk[datasets]` (pandas and pyarrow). Polars frames need
`luml_sdk[datasets-polars]`.

```python
from luml import save_tabular_dataset

dataset_ref = save_tabular_dataset(
    {"train": train_frame, "test": test_frame},
    file_format="parquet",      # or "csv"
    name="churn-events",
    description="90 days of account events",
    version="2026-11",
    output_path="churn-events.luml",
)
```

`data` can be:

- one frame or one file path: subset `default`, split `train`;
- a dict of splits: `{"train": ..., "test": ...}`;
- a dict of subsets of splits: `{"en": {"train": ...}, "de": {"train": ...}}`.

`chunk_size` splits large frames into several files.

## Hugging Face datasets

Install `luml_sdk[datasets-hf]`.

```python
from luml import save_hf_dataset

dataset_ref = save_hf_dataset(dataset_dict, name="support-tickets", output_path="tickets.luml")
```

It takes a `Dataset`, a `DatasetDict`, or a dict of named configs.

## Reading a dataset

```python
from luml import load_dataset

dataset = load_dataset(dataset_ref)
dataset.subsets                              # ["default"]
dataset.splits("default")                    # ["train", "test"]
train = dataset.to_pandas(subset="default", split="train")
```

`to_polars` works the same way. `to_hf()`, `to_hf_config()` and
`to_hf_split()` work only for Hugging Face datasets.

## Dataset cards

```python
from luml import CardBuilder

dataset_ref.add_dataset_card(CardBuilder(title="Churn events").write_markdown("..."))
```
