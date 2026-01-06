"""
Example: Building a comprehensive model card with various visualizations.

This example demonstrates how to use the ModelCardBuilder to create rich HTML
model cards with embedded plots, tables, and images.

The examples are structured to separate object creation from writing to the card,
making it clear what artifacts are being created and how they're added to the card.
"""

import tempfile

from luml.model_card import ModelCardBuilder


def create_metrics_dataframe():  # type: ignore[no-untyped-def]
    """Create a DataFrame with performance metrics."""
    import pandas as pd

    return pd.DataFrame(
        {
            "Metric": ["Accuracy", "Precision", "Recall", "F1-Score", "AUC"],
            "Train": [0.98, 0.97, 0.98, 0.97, 0.99],
            "Validation": [0.95, 0.94, 0.96, 0.95, 0.96],
            "Test": [0.93, 0.92, 0.94, 0.93, 0.94],
        }
    )


def create_training_history_plot():  # type: ignore[no-untyped-def]
    """Create a matplotlib plot showing training history."""
    import matplotlib.pyplot as plt
    import numpy as np

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    epochs = np.arange(1, 21)
    train_loss = 0.5 * np.exp(-epochs / 5) + 0.1
    val_loss = 0.6 * np.exp(-epochs / 6) + 0.15

    ax1.plot(epochs, train_loss, label="Train Loss", linewidth=2, marker="o")
    ax1.plot(epochs, val_loss, label="Val Loss", linewidth=2, marker="s")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_title("Loss Over Time")

    train_acc = 1 - train_loss * 0.5
    val_acc = 1 - val_loss * 0.5

    ax2.plot(epochs, train_acc, label="Train Acc", linewidth=2, marker="o")
    ax2.plot(epochs, val_acc, label="Val Acc", linewidth=2, marker="s")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Accuracy")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_title("Accuracy Over Time")

    plt.tight_layout()
    return fig


def create_feature_importance_plot():  # type: ignore[no-untyped-def]
    """Create a matplotlib bar chart showing feature importance."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 3))
    features = ["Feature A", "Feature B", "Feature C", "Feature D", "Feature E"]
    importance = [0.28, 0.22, 0.19, 0.18, 0.13]
    colors = ["#3498db", "#2ecc71", "#f39c12", "#e74c3c", "#9b59b6"]

    ax.barh(features, importance, color=colors)
    ax.set_xlabel("Importance Score")
    ax.set_title("Top 5 Most Important Features")
    ax.grid(True, alpha=0.3, axis="x")

    return fig


def create_confusion_matrix_plot():  # type: ignore[no-untyped-def]
    """Create an interactive plotly confusion matrix heatmap."""
    import plotly.graph_objects as go

    confusion_matrix = [[85, 10, 5], [8, 82, 10], [3, 7, 90]]
    classes = ["Class A", "Class B", "Class C"]

    fig = go.Figure(
        data=go.Heatmap(
            z=confusion_matrix,
            x=classes,
            y=classes,
            colorscale="Blues",
            showscale=True,
            text=confusion_matrix,
            texttemplate="%{text}",
            textfont={"size": 16},
        )
    )

    fig.update_layout(
        title="Confusion Matrix",
        xaxis_title="Predicted Class",
        yaxis_title="True Class",
        width=600,
        height=500,
    )

    return fig


def example_comprehensive_card() -> None:
    """Example: Comprehensive card with all content types."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        print(f"Skipping comprehensive example due to missing dependency: {e}")  # noqa: T201
        return

    print("Example: Comprehensive model card with all content types")  # noqa: T201

    builder = ModelCardBuilder(title="Complete Model Card Demo")

    # Text and markdown
    builder.write("# Model Card Demo")
    builder.write(
        """
        This example demonstrates **all content types** supported by the
        ModelCardBuilder. You can mix and match different content types
        in a single card.
        """
    )

    # Heading and paragraph
    builder.write_heading("Model Information", level=2)
    builder.write_paragraph(
        "This is a random forest classifier trained on synthetic data."
    )

    # List using markdown
    builder.write_markdown(
        """
        ### Key Features
        - High accuracy classification
        - Fast inference time
        - Low memory footprint
        - Production ready
        """
    )

    builder.write_divider()

    # DataFrame table - create then write
    builder.write_heading("Performance Metrics", level=2)
    metrics_df = create_metrics_dataframe()
    builder.write(metrics_df)

    # Matplotlib plots - create then write
    builder.write_heading("Training History", level=2)
    training_fig = create_training_history_plot()
    builder.write(training_fig)
    plt.close(training_fig)

    builder.write_heading("Feature Importance", level=2)
    importance_fig = create_feature_importance_plot()
    builder.write(importance_fig)
    plt.close(importance_fig)

    # Plotly interactive chart - create then write
    builder.write_heading("Confusion Matrix (Interactive)", level=2)
    confusion_fig = create_confusion_matrix_plot()
    builder.write(confusion_fig)

    # Code block
    builder.write_divider()
    builder.write_heading("Usage Example", level=2)
    builder.write_markdown(
        """
        ```python
        import pickle
        import numpy as np

        # Load the model
        with open('model.pkl', 'rb') as f:
            model = pickle.load(f)

        # Make predictions
        X_new = np.array([[1.2, 3.4, 5.6, 7.8, 9.0]])
        predictions = model.predict(X_new)
        probabilities = model.predict_proba(X_new)

        print(f"Prediction: {predictions[0]}")
        print(f"Confidence: {probabilities[0].max():.2%}")
        ```
        """
    )

    # Raw HTML for custom content
    builder.write_heading("Model Details", level=2)
    builder.write_html(
        """
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background: #f6f8fa;">
                <td style="padding: 8px; font-weight: bold;">Framework</td>
                <td style="padding: 8px;">scikit-learn 1.3.2</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Model Type</td>
                <td style="padding: 8px;">RandomForestClassifier</td>
            </tr>
            <tr style="background: #f6f8fa;">
                <td style="padding: 8px; font-weight: bold;">Training Date</td>
                <td style="padding: 8px;">2024-12-14</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Model Size</td>
                <td style="padding: 8px;">2.4 MB</td>
            </tr>
        </table>
        """
    )

    # Final notes
    builder.write_divider()
    builder.write_heading("Notes & Limitations", level=2)
    builder.write_markdown(
        """
        **Important Considerations:**

        - Model performs best on data similar to the training distribution
        - Input features should be normalized using the same scaler used during training
        - Not suitable for real-time applications requiring <10ms latency
        - Regular retraining recommended every 3 months

        For questions or issues, contact the ML team at `ml-team@example.com`.
        """
    )

    # Save the card
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(builder.build())
        print(f"Comprehensive card saved to: {f.name}")  # noqa: T201
        print(f"Open in browser: file://{f.name}")  # noqa: T201


if __name__ == "__main__":
    print("=" * 60)  # noqa: T201
    print("Model Card Builder Example")  # noqa: T201
    print("=" * 60)  # noqa: T201

    example_comprehensive_card()
    print()  # noqa: T201

    print("=" * 60)  # noqa: T201
    print("Example completed!")  # noqa: T201
    print("=" * 60)  # noqa: T201
