import base64
import io
import re
from pathlib import Path
from typing import Any

from luml.model_card.templates import (
    get_default_css,
    get_html_template,
    image_container,
    plot_container,
    plotly_container,
    table_container,
)


class ModelCardBuilder:
    def __init__(
        self, title: str = "Model Card", custom_css: str | None = None
    ) -> None:
        self.title = title
        self.custom_css = custom_css
        self._sections: list[str] = []
        self._has_plotly = False

    def write(self, content: Any) -> "ModelCardBuilder":  # noqa: ANN401
        """Write content to the model card. Automatically detects content type."""
        if isinstance(content, str):
            self._write_text(content)
        elif self._is_matplotlib_figure(content):
            self._write_matplotlib(content)
        elif self._is_plotly_figure(content):
            self._write_plotly(content)
        elif self._is_dataframe(content):
            self._write_dataframe(content)
        elif self._is_pil_image(content):
            self._write_pil_image(content)
        elif isinstance(content, Path | bytes):
            self._write_image(content)
        else:
            self._write_text(str(content))
        return self

    def write_heading(self, text: str, level: int = 1) -> "ModelCardBuilder":
        level = max(1, min(6, level))
        self._sections.append(f"<h{level}>{self._escape_html(text)}</h{level}>")
        return self

    def write_paragraph(self, text: str) -> "ModelCardBuilder":
        self._sections.append(f"<p>{self._escape_html(text)}</p>")
        return self

    def write_markdown(self, markdown: str) -> "ModelCardBuilder":
        html = self._markdown_to_html(markdown)
        self._sections.append(html)
        return self

    def write_html(self, html: str) -> "ModelCardBuilder":
        self._sections.append(html)
        return self

    def write_divider(self) -> "ModelCardBuilder":
        self._sections.append("<hr>")
        return self

    def build(self) -> str:
        plotly_script = ""
        if self._has_plotly:
            cdn_url = getattr(
                self, "_plotly_cdn_url", "https://cdn.plot.ly/plotly-2.27.0.min.js"
            )
            plotly_script = f'    <script src="{cdn_url}"></script>\n'

        css = get_default_css()
        if self.custom_css:
            css += f"\n{self.custom_css}"

        return get_html_template(
            title=self._escape_html(self.title),
            plotly_script=plotly_script,
            css=css,
            body="".join(self._sections),
        )

    def _write_text(self, text: str) -> None:
        if any(
            text.strip().startswith(marker) for marker in ["#", "-", "*", ">", "```"]
        ):
            self.write_markdown(text)
        else:
            self._sections.append(f"<div>{self._escape_html(text)}</div>")

    def _write_matplotlib(self, fig: Any) -> None:  # noqa: ANN401
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        self._sections.append(plot_container(img_base64))
        buf.close()

    def _write_plotly(self, fig: Any) -> None:  # noqa: ANN401
        try:
            import plotly.io as pio  # type: ignore[import-untyped]
        except ImportError as e:
            msg = "plotly is required for plotly figures. Install with: pip install plotly"  # noqa: E501
            raise ImportError(msg) from e

        self._has_plotly = True
        if not hasattr(self, "_plotly_cdn_url"):
            try:
                from plotly.offline import get_plotlyjs_version

                self._plotly_cdn_url = (
                    f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"
                )
            except Exception:
                self._plotly_cdn_url = "https://cdn.plot.ly/plotly-2.27.0.min.js"

        html = pio.to_html(fig, include_plotlyjs=False, div_id=None, full_html=False)
        self._sections.append(plotly_container(html))

    def _write_dataframe(self, df: Any) -> None:  # noqa: ANN401
        html = df.to_html(
            classes="dataframe-table",
            border=0,
            index=True,
            escape=True,
            max_rows=100,
            max_cols=20,
        )
        self._sections.append(table_container(html))

    def _write_pil_image(self, img: Any) -> None:  # noqa: ANN401
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        self._sections.append(image_container(img_base64, "png"))
        buf.close()

    def _write_image(self, content: Path | bytes) -> None:
        if isinstance(content, Path):
            with open(content, "rb") as f:
                img_bytes = f.read()
        else:
            img_bytes = content

        img_format = self._detect_image_format(img_bytes)
        img_base64 = base64.b64encode(img_bytes).decode("utf-8")
        self._sections.append(image_container(img_base64, img_format))

    @staticmethod
    def _is_matplotlib_figure(obj: Any) -> bool:  # noqa: ANN401
        try:
            from matplotlib.figure import Figure  # type: ignore[import-untyped]

            return isinstance(obj, Figure)
        except ImportError:
            return False

    @staticmethod
    def _is_plotly_figure(obj: Any) -> bool:  # noqa: ANN401
        try:
            from plotly.graph_objs import Figure  # type: ignore[import-untyped]

            return isinstance(obj, Figure)
        except ImportError:
            return False

    @staticmethod
    def _is_dataframe(obj: Any) -> bool:  # noqa: ANN401
        try:
            from pandas import DataFrame  # type: ignore[import-untyped]

            return isinstance(obj, DataFrame)
        except ImportError:
            return False

    @staticmethod
    def _is_pil_image(obj: Any) -> bool:  # noqa: ANN401
        try:
            from PIL import Image  # type: ignore[import-untyped]

            return isinstance(obj, Image.Image)
        except ImportError:
            return False

    @staticmethod
    def _detect_image_format(img_bytes: bytes) -> str:
        if img_bytes.startswith(b"\x89PNG"):
            return "png"
        if img_bytes.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        if img_bytes.startswith(b"GIF87a") or img_bytes.startswith(b"GIF89a"):
            return "gif"
        if img_bytes.startswith(b"RIFF") and b"WEBP" in img_bytes[:12]:
            return "webp"
        return "png"

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    @staticmethod
    def _markdown_to_html(markdown: str) -> str:  # noqa: C901
        html_lines = []
        in_code_block = False
        code_block_lines = []
        in_list = False

        for line in markdown.split("\n"):
            if line.strip().startswith("```"):
                if in_code_block:
                    code = "\n".join(code_block_lines)
                    html_lines.append(
                        f"<pre><code>{ModelCardBuilder._escape_html(code)}</code></pre>"
                    )
                    code_block_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            if line.strip().startswith("#"):
                stripped = line.strip()
                level = 0
                for char in stripped:
                    if char == "#":
                        level += 1
                    else:
                        break
                level = min(level, 6)
                text = stripped[level:].strip()

                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h{level}>{text}</h{level}>")
                continue

            if line.strip().startswith(("- ", "* ", "+ ")):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                text = line.strip()[2:]
                text = ModelCardBuilder._process_inline_markdown(text)
                html_lines.append(f"<li>{text}</li>")
                continue
            if in_list:
                html_lines.append("</ul>")
                in_list = False

            if line.strip():
                processed = ModelCardBuilder._process_inline_markdown(line)
                html_lines.append(f"<p>{processed}</p>")
            else:
                html_lines.append("<br>")

        if in_list:
            html_lines.append("</ul>")

        return "\n".join(html_lines)

    @staticmethod
    def _process_inline_markdown(text: str) -> str:
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
