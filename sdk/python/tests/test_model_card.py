"""Tests for the model card builder."""

import tempfile
from pathlib import Path

import pytest

from luml.artifacts.model import ModelReference
from luml.model_card import ModelCardBuilder


def test_basic_builder() -> None:
    builder = ModelCardBuilder(title="Test Card")
    builder.write("# Heading")
    builder.write_paragraph("This is a paragraph")

    html = builder.build()
    assert "<title>Test Card</title>" in html
    assert "<h1>Heading</h1>" in html
    assert "This is a paragraph" in html


def test_method_chaining() -> None:
    builder = ModelCardBuilder()
    result = (
        builder.write("test")
        .write_heading("heading")
        .write_paragraph("paragraph")
        .write_divider()
    )
    assert result is builder


def test_markdown_conversion() -> None:
    builder = ModelCardBuilder()
    builder.write_markdown("**bold** and *italic*")

    html = builder.build()
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html


def test_html_escaping() -> None:
    builder = ModelCardBuilder(title="<script>alert('xss')</script>")
    builder.write_paragraph("<div>test</div>")

    html = builder.build()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;div&gt;test&lt;/div&gt;" in html


def test_custom_css() -> None:
    custom_css = ".custom { color: red; }"
    builder = ModelCardBuilder(custom_css=custom_css)

    html = builder.build()
    assert custom_css in html


def test_divider() -> None:
    builder = ModelCardBuilder()
    builder.write_divider()

    html = builder.build()
    assert "<hr>" in html


def test_raw_html() -> None:
    builder = ModelCardBuilder()
    raw_html = '<div class="custom">Test</div>'
    builder.write_html(raw_html)

    html = builder.build()
    assert raw_html in html


def test_string_content() -> None:
    builder = ModelCardBuilder()
    builder.write("Plain text")

    html = builder.build()
    assert "Plain text" in html


def test_headings() -> None:
    builder = ModelCardBuilder()
    for level in range(1, 7):
        builder.write_heading(f"Heading {level}", level=level)

    html = builder.build()
    for level in range(1, 7):
        assert f"<h{level}>Heading {level}</h{level}>" in html


def test_heading_level_clamping() -> None:
    builder = ModelCardBuilder()
    builder.write_heading("Test", level=0)  # Should become h1
    builder.write_heading("Test2", level=10)  # Should become h6

    html = builder.build()
    assert "<h1>Test</h1>" in html
    assert "<h6>Test2</h6>" in html


def test_matplotlib_integration() -> None:
    pytest.importorskip("matplotlib")

    import matplotlib.pyplot as plt

    builder = ModelCardBuilder()

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 4, 9])

    builder.write(fig)
    html = builder.build()

    assert "data:image/png;base64," in html
    assert "plot-container" in html
    plt.close(fig)


def test_plotly_integration() -> None:
    pytest.importorskip("plotly")

    import plotly.graph_objects as go

    builder = ModelCardBuilder()

    fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[1, 4, 9]))
    builder.write(fig)

    html = builder.build()
    assert "plot-container" in html
    # Plotly should be included
    assert "plotly" in html.lower()


def test_pandas_integration() -> None:
    pytest.importorskip("pandas")

    import pandas as pd

    builder = ModelCardBuilder()

    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    builder.write(df)

    html = builder.build()
    assert "dataframe-table" in html
    assert "table-container" in html


def test_pil_image_integration() -> None:
    """Test PIL Image embedding."""
    pytest.importorskip("PIL")

    from PIL import Image

    builder = ModelCardBuilder()

    img = Image.new("RGB", (100, 100), color="red")
    builder.write(img)

    html = builder.build()
    assert "data:image/png;base64," in html
    assert "image-container" in html


def test_image_from_bytes() -> None:
    png_header = b"\x89PNG\r\n\x1a\n"
    builder = ModelCardBuilder()
    builder.write(png_header + b"...")

    html = builder.build()
    assert "data:image/png;base64," in html


def test_model_reference_integration() -> None:
    import io
    import tarfile

    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
        tar_path = Path(f.name)

    try:
        with tarfile.open(tar_path, "w") as tar:
            model_data = b"dummy model"
            info = tarfile.TarInfo(name="model.pkl")
            info.size = len(model_data)
            tar.addfile(info, fileobj=io.BytesIO(model_data))

        builder = ModelCardBuilder(title="Test Model")
        builder.write("# Test Content")
        model_ref = ModelReference(str(tar_path))
        model_ref.add_model_card(builder)

        with tarfile.open(tar_path, "r") as tar:
            names = tar.getnames()
            assert any("model_card.zip" in name for name in names)

    finally:
        tar_path.unlink()


def test_model_reference_with_html_string() -> None:
    import io
    import tarfile

    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
        tar_path = Path(f.name)

    try:
        with tarfile.open(tar_path, "w") as tar:
            model_data = b"dummy model"
            info = tarfile.TarInfo(name="model.pkl")
            info.size = len(model_data)
            tar.addfile(info, fileobj=io.BytesIO(model_data))

        html = "<html><body>Test</body></html>"
        model_ref = ModelReference(str(tar_path))
        model_ref.add_model_card(html)

        with tarfile.open(tar_path, "r") as tar:
            names = tar.getnames()
            assert any("model_card.zip" in name for name in names)

    finally:
        tar_path.unlink()


def test_model_reference_type_error() -> None:
    import io
    import tarfile

    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
        tar_path = Path(f.name)

    try:
        with tarfile.open(tar_path, "w") as tar:
            model_data = b"dummy model"
            info = tarfile.TarInfo(name="model.pkl")
            info.size = len(model_data)
            tar.addfile(info, fileobj=io.BytesIO(model_data))

        model_ref = ModelReference(str(tar_path))

        with pytest.raises(TypeError, match="must be a string or ModelCardBuilder"):
            model_ref.add_model_card(12345)  # Invalid type # type: ignore

    finally:
        tar_path.unlink()


def test_markdown_lists() -> None:
    builder = ModelCardBuilder()
    builder.write_markdown(
        """
        - Item 1
        - Item 2
        - Item 3
        """
    )

    html = builder.build()
    assert "<ul>" in html
    assert "<li>Item 1</li>" in html
    assert "<li>Item 2</li>" in html
    assert "</ul>" in html


def test_markdown_code_blocks() -> None:
    builder = ModelCardBuilder()
    builder.write_markdown(
        """
        ```python
        def hello():
            print("world")
        ```
        """
    )

    html = builder.build()
    assert "<pre><code>" in html
    assert "def hello():" in html
    assert "</code></pre>" in html


def test_markdown_inline_code() -> None:
    builder = ModelCardBuilder()
    builder.write_markdown("Use `print()` function")

    html = builder.build()
    assert "<code>print()</code>" in html


def test_markdown_links() -> None:
    builder = ModelCardBuilder()
    builder.write_markdown("[Click here](https://example.com)")

    html = builder.build()
    assert '<a href="https://example.com">Click here</a>' in html


def test_image_format_detection() -> None:
    builder = ModelCardBuilder()

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    assert builder._detect_image_format(png_bytes) == "png"

    jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 100
    assert builder._detect_image_format(jpeg_bytes) == "jpeg"

    gif_bytes = b"GIF89a" + b"\x00" * 100
    assert builder._detect_image_format(gif_bytes) == "gif"

    # unknown (defaults to png)
    unknown_bytes = b"\x00\x00\x00\x00"
    assert builder._detect_image_format(unknown_bytes) == "png"


def test_plotly_script_only_when_needed() -> None:
    builder = ModelCardBuilder()
    builder.write("# Test")
    builder.write_paragraph("No interactive plots here")
    html = builder.build()

    assert "plotly-" not in html

    try:
        import plotly.graph_objects as go

        builder_with_plotly = ModelCardBuilder()
        builder_with_plotly.write("# With Plotly")
        fig = go.Figure(data=go.Scatter(x=[1, 2], y=[3, 4]))
        builder_with_plotly.write(fig)
        html_with_plotly = builder_with_plotly.build()

        assert "plotly-" in html_with_plotly
    except ImportError:
        pass


def test_markdown_heading_levels() -> None:
    builder = ModelCardBuilder()
    builder.write_markdown(
        """
        # H1
        ## H2
        ### H3
        #### H4
        ##### H5
        ###### H6
        """
    )

    html = builder.build()
    assert "<h1>H1</h1>" in html
    assert "<h2>H2</h2>" in html
    assert "<h3>H3</h3>" in html
    assert "<h4>H4</h4>" in html
    assert "<h5>H5</h5>" in html
    assert "<h6>H6</h6>" in html
