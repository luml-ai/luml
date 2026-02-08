import tempfile
from pathlib import Path
from typing import Any


def create_sample_data() -> tuple[Any, Any]:  # noqa: ANN401
    """Create sample data for demonstrations."""
    import pandas as pd

    train_data = pd.DataFrame(
        {
            "feature_1": [1.2, 2.3, 3.4, 4.5, 5.6, 6.7, 7.8, 8.9],
            "feature_2": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            "label": [0, 1, 0, 1, 0, 1, 0, 1],
        }
    )

    test_data = pd.DataFrame(
        {
            "feature_1": [9.1, 10.2],
            "feature_2": [0.9, 1.0],
            "label": [1, 0],
        }
    )

    return train_data, test_data


def example_basic_pandas_dataset() -> None:
    """Example 1: Basic pandas dataset packaging."""
    try:
        import pandas as pd
    except ImportError as e:
        print(f"Skipping pandas example: {e}")
        return

    from luml.artifacts.dataset import load_dataset, save_tabular_dataset

    print("\n" + "=" * 60)
    print("Example 1: Basic pandas DataFrame packaging")
    print("=" * 60)

    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "value": [10.5, 20.3, 30.1, 40.8, 50.2],
            "category": ["A", "B", "A", "C", "B"],
        }
    )

    print(f"Original DataFrame:\n{df}")

    with tempfile.TemporaryDirectory(delete=True) as tmpdir:
        output_path = Path(tmpdir) / "basic_dataset.tar"

        ref = save_tabular_dataset(
            df,
            name="basic-demo",
            description="Simple pandas DataFrame example",
            output_path=str(output_path),
        )

        print(f"\nDataset saved to: {ref.path}")
        print(f"Manifest: {ref.get_manifest().model_dump_json(indent=2)}")

        mat = load_dataset(ref)
        print(f"\nDataset variant: {mat.variant}")
        print(f"Available subsets: {mat.subsets}")
        print(f"Available splits: {mat.splits()}")

        loaded_df = mat.to_pandas()
        print(f"\nLoaded DataFrame:\n{loaded_df}")
        print(f"Data matches: {df.equals(loaded_df)}")


def example_polars_dataset() -> None:
    """Example 2: Polars dataset packaging."""
    try:
        import polars as pl
    except ImportError as e:
        print(f"Skipping polars example: {e}")
        return

    from luml.artifacts.dataset import load_dataset, save_tabular_dataset

    print("\n" + "=" * 60)
    print("Example 2: Polars DataFrame packaging")
    print("=" * 60)

    df = pl.DataFrame(
        {
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "metric": [100.5, 200.3, 150.8],
        }
    )

    print(f"Original Polars DataFrame:\n{df}")

    with tempfile.TemporaryDirectory(delete=True) as tmpdir:
        output_path = Path(tmpdir) / "polars_dataset.tar"

        ref = save_tabular_dataset(
            df,
            file_format="csv",
            name="polars-demo",
            output_path=str(output_path),
        )

        print(f"\nDataset saved to: {ref.path}")

        mat = load_dataset(ref)
        loaded_df = mat.to_polars()
        print(f"\nLoaded Polars DataFrame:\n{loaded_df}")


def example_chunked_dataset() -> None:
    """Example 3: Chunking large datasets."""
    try:
        import pandas as pd
    except ImportError as e:
        print(f"Skipping chunking example: {e}")
        return

    from luml.artifacts.dataset import load_dataset, save_tabular_dataset

    print("\n" + "=" * 60)
    print("Example 3: Dataset chunking")
    print("=" * 60)

    large_df = pd.DataFrame(
        {
            "id": range(1000),
            "value": [i * 0.5 for i in range(1000)],
        }
    )

    print(f"Large DataFrame: {len(large_df)} rows")

    with tempfile.TemporaryDirectory(delete=True) as tmpdir:
        output_path = Path(tmpdir) / "chunked_dataset.tar"

        ref = save_tabular_dataset(
            large_df,
            chunk_size=300,
            name="chunked-demo",
            output_path=str(output_path),
        )

        manifest = ref.get_manifest()
        split_info = manifest.payload.subsets["default"].splits["train"]  # type: ignore
        print(f"\nDataset chunked into {split_info.num_chunks} chunks")
        print(f"Chunk files: {split_info.chunk_files}")

        mat = load_dataset(ref)
        loaded_df = mat.to_pandas()
        print(f"\nLoaded DataFrame: {len(loaded_df)} rows")
        print(f"Data integrity: {large_df.equals(loaded_df)}")


def example_subsets_and_splits() -> None:
    """Example 4: Organizing data with subsets and splits."""
    try:
        import pandas  # noqa: F401
    except ImportError as e:
        print(f"Skipping subsets/splits example: {e}")
        return

    from luml.artifacts.dataset import load_dataset, save_tabular_dataset

    print("\n" + "=" * 60)
    print("Example 4: Subsets and splits")
    print("=" * 60)

    train_df, test_df = create_sample_data()

    dataset_structure = {
        "modeling": {
            "train": train_df,
            "test": test_df,
        },
        "evaluation": {
            "holdout": test_df,
        },
    }

    with tempfile.TemporaryDirectory(delete=True) as tmpdir:
        output_path = Path(tmpdir) / "structured_dataset.tar"

        ref = save_tabular_dataset(
            dataset_structure,
            name="structured-demo",
            output_path=str(output_path),
            file_format="csv",
        )

        print("Dataset structure saved")

        mat = load_dataset(ref)
        print(f"\nSubsets: {mat.subsets}")
        for subset in mat.subsets:
            print(f"  {subset}: {mat.splits(subset)}")

        train_data = mat.to_pandas(subset="modeling", split="train")
        test_data = mat.to_pandas(subset="modeling", split="test")
        holdout_data = mat.to_pandas(subset="evaluation", split="holdout")

        print(f"\nTrain shape: {train_data.shape}")
        print(f"Test shape: {test_data.shape}")
        print(f"Holdout shape: {holdout_data.shape}")


def example_huggingface_dataset() -> None:
    """Example 5: HuggingFace dataset packaging."""
    try:
        import datasets
    except ImportError as e:
        print(f"Skipping HuggingFace example: {e}")
        return

    from luml.artifacts.dataset import load_dataset, save_hf_dataset

    print("\n" + "=" * 60)
    print("Example 5: HuggingFace dataset packaging")
    print("=" * 60)

    dataset_dict = datasets.DatasetDict(
        {
            "train": datasets.Dataset.from_dict(
                {
                    "text": ["Hello world", "Machine learning", "Python code"],
                    "label": [0, 1, 0],
                }
            ),
            "test": datasets.Dataset.from_dict(
                {
                    "text": ["Test sample"],
                    "label": [1],
                }
            ),
        }
    )

    print(f"Original HuggingFace DatasetDict:\n{dataset_dict}")

    with tempfile.TemporaryDirectory(delete=True) as tmpdir:
        output_path = Path(tmpdir) / "hf_dataset.tar"

        ref = save_hf_dataset(
            dataset_dict,
            name="hf-demo",
            output_path=str(output_path),
        )

        print(f"\nDataset saved to: {ref.path}")

        mat = load_dataset(ref)
        print(f"Dataset variant: {mat.variant}")

        loaded_dict = mat.to_hf()
        print(f"\nLoaded DatasetDict:\n{loaded_dict}")

        train_dataset = mat.to_hf_split(split="train")
        print(f"\nTrain split: {len(train_dataset)} samples")


def example_huggingface_with_configs() -> None:
    """Example 5b: HuggingFace datasets with multiple configs."""
    try:
        import datasets
    except ImportError as e:
        print(f"Skipping HuggingFace configs example: {e}")
        return

    from luml.artifacts.dataset import load_dataset, save_hf_dataset

    print("\n" + "=" * 60)
    print("Example 5b: HuggingFace dataset configs (multi-config)")
    print("=" * 60)

    cola_dataset = datasets.DatasetDict(
        {
            "train": datasets.Dataset.from_dict(
                {
                    "sentence": [
                        "The book was written by John.",
                        "Was the book written by John?",
                    ],
                    "label": [1, 1],
                }
            ),
            "validation": datasets.Dataset.from_dict(
                {
                    "sentence": ["Book the was John by written."],
                    "label": [0],
                }
            ),
        }
    )

    sst2_dataset = datasets.DatasetDict(
        {
            "train": datasets.Dataset.from_dict(
                {
                    "sentence": [
                        "This movie is great!",
                        "I hated every minute.",
                    ],
                    "label": [1, 0],
                }
            ),
            "validation": datasets.Dataset.from_dict(
                {
                    "sentence": ["It was okay."],
                    "label": [1],
                }
            ),
        }
    )

    print("Config 1: CoLA (Corpus of Linguistic Acceptability)")
    print(f"{cola_dataset}\n")

    print("Config 2: SST-2 (Sentiment Analysis)")
    print(f"{sst2_dataset}\n")

    with tempfile.TemporaryDirectory(delete=True) as tmpdir:
        print(
            "Packaging multiple configs in a SINGLE archive..."
        )

        ref = save_hf_dataset(
            {"cola": cola_dataset, "sst2": sst2_dataset},
            name="glue-multi",
            description="GLUE dataset with multiple configs",
            output_path=str(Path(tmpdir) / "glue.tar"),
        )

        print(f"\nDataset saved to: {ref.path}")

        manifest = ref.get_manifest()
        print(f"\nConfigs in archive: {list(manifest.payload.subsets.keys())}")

        mat = load_dataset(ref)
        print(f"\nAvailable configs: {mat.subsets}")
        print(f"CoLA splits: {mat.splits('cola')}")
        print(f"SST-2 splits: {mat.splits('sst2')}")

        print("\nLoading specific config:")
        cola_loaded = mat.to_hf_config("cola")
        print(f"CoLA config: {cola_loaded}")

        print("\nLoading specific split from specific config:")
        sst2_train = mat.to_hf_split(subset="sst2", split="train")
        print(f"SST-2 train: {len(sst2_train)} samples")

        print(
            "\n✓ Multiple HF configs packaged in a single archive!"
        )
        print(
            "✓ Each config preserves its splits (train/validation/test)"
        )


def example_format_conversion() -> None:
    """Example 6: Converting between formats."""
    try:
        import pandas as pd
    except ImportError as e:
        print(f"Skipping format conversion example: {e}")
        return

    from luml.artifacts.dataset import load_dataset, save_tabular_dataset

    print("\n" + "=" * 60)
    print("Example 6: Format conversion")
    print("=" * 60)

    original_df = pd.DataFrame(
        {
            "x": [1, 2, 3, 4],
            "y": [10, 20, 30, 40],
        }
    )

    print(f"Original pandas DataFrame:\n{original_df}\n")

    with tempfile.TemporaryDirectory(delete=True) as tmpdir:
        output_path = Path(tmpdir) / "conversion_dataset.tar"

        ref = save_tabular_dataset(original_df, output_path=str(output_path))
        mat = load_dataset(ref)

        print("Converting to different formats:")

        pandas_df = mat.to_pandas()
        print(f"\n✓ Pandas DataFrame:\n{pandas_df}")

        try:
            import polars  # noqa: F401

            polars_df = mat.to_polars()
            print(f"\n✓ Polars DataFrame:\n{polars_df}")
        except ImportError:
            print("\n✗ Polars not available")


def example_from_file_path() -> None:
    """Example 7: Packaging datasets from file paths."""
    try:
        import pandas as pd
    except ImportError as e:
        print(f"Skipping file path example: {e}")
        return

    from luml.artifacts.dataset import save_tabular_dataset

    print("\n" + "=" * 60)
    print("Example 7: Packaging from file paths")
    print("=" * 60)

    with tempfile.TemporaryDirectory(delete=False) as tmpdir:
        csv_path = Path(tmpdir) / "source.csv"
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        df.to_csv(csv_path, index=False)
        print(f"Created CSV file: {csv_path}")

        output_path = Path(tmpdir) / "file_dataset.tar"
        ref = save_tabular_dataset(
            csv_path,
            file_format="csv",
            name="from-file",
            output_path=str(output_path),
        )

        print(f"Dataset packaged from file: {ref.path}")
        print(f"Validation: {ref.validate()}")


def main() -> None:
    """Run all examples."""
    print("=" * 60)
    print("Dataset Packaging Examples")
    print("=" * 60)

    # example_basic_pandas_dataset()
    # example_polars_dataset()
    # example_chunked_dataset()
    # example_subsets_and_splits()
    # example_huggingface_dataset()
    # example_huggingface_with_configs()
    # example_format_conversion()
    example_from_file_path()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
