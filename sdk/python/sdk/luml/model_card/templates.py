"""HTML and CSS templates for model cards."""


def get_html_template(title: str, plotly_script: str, css: str, body: str) -> str:
    """Generate the complete HTML document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
{plotly_script}    <style>
        {css}
    </style>
</head>
<body>
    {body}
</body>
</html>"""


def plot_container(img_base64: str) -> str:
    """Template for matplotlib plot container."""
    return (
        f'<div class="plot-container">'
        f'<img src="data:image/png;base64,{img_base64}" alt="Plot" class="plot-image">'
        f"</div>"
    )


def plotly_container(html: str) -> str:
    """Template for plotly plot container."""
    return f'<div class="plot-container">{html}</div>'


def table_container(html: str) -> str:
    """Template for dataframe table container."""
    return f'<div class="table-container">{html}</div>'


def image_container(img_base64: str, img_format: str) -> str:
    """Template for image container."""
    return (
        f'<div class="image-container">'
        f'<img src="data:image/{img_format};base64,{img_base64}" alt="Image" class="content-image">'  # noqa: E501
        f"</div>"
    )


def get_default_css() -> str:
    """Get default CSS styling optimized for iframe embedding."""
    return """
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background: transparent;
            padding: 16px;
            font-size: 14px;
        }

        h1, h2, h3, h4, h5, h6 {
            margin-top: 20px;
            margin-bottom: 12px;
            font-weight: 600;
            line-height: 1.3;
            color: #2c3e50;
        }

        h1:first-child, h2:first-child, h3:first-child {
            margin-top: 0;
        }

        h1 { font-size: 1.75em; }
        h2 { font-size: 1.4em; }
        h3 { font-size: 1.15em; }
        h4 { font-size: 1em; }
        h5 { font-size: 0.875em; }
        h6 { font-size: 0.85em; }

        p, div {
            margin-bottom: 12px;
        }

        a {
            color: #3498db;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        code {
            background: #f6f8fa;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
            font-size: 0.9em;
            color: #e83e8c;
        }

        pre {
            background: #f6f8fa;
            padding: 12px;
            border-radius: 4px;
            overflow-x: auto;
            margin-bottom: 16px;
            border: 1px solid #e1e4e8;
        }

        pre code {
            background: none;
            padding: 0;
            color: inherit;
        }

        hr {
            border: 0;
            border-top: 1px solid #e1e4e8;
            margin: 20px 0;
        }

        ul, ol {
            margin-bottom: 12px;
            padding-left: 24px;
        }

        li {
            margin-bottom: 6px;
        }

        .plot-container {
            margin: 16px 0;
            text-align: center;
            width: 100%;
        }

        .plot-image {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }

        .image-container {
            margin: 16px 0;
            text-align: center;
            width: 100%;
        }

        .content-image {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }

        .table-container {
            margin: 16px 0;
            overflow-x: auto;
            width: 100%;
        }

        .dataframe-table {
            border-collapse: collapse;
            width: 100%;
            margin: 0;
            font-size: 0.9em;
        }

        .dataframe-table th {
            background: #f6f8fa;
            color: #24292e;
            padding: 8px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #d1d5da;
        }

        .dataframe-table td {
            padding: 8px 12px;
            border-bottom: 1px solid #e1e4e8;
        }

        .dataframe-table tr:hover {
            background: #f6f8fa;
        }

        .dataframe-table tbody tr:nth-child(even) {
            background: #fafbfc;
        }

        .dataframe-table tbody tr:nth-child(even):hover {
            background: #f6f8fa;
        }

        strong {
            font-weight: 600;
            color: #24292e;
        }

        em {
            font-style: italic;
        }

        img, svg, video, canvas, audio, iframe, embed, object {
            max-width: 100%;
            height: auto;
        }

        @media (max-width: 600px) {
            body {
                padding: 12px;
                font-size: 13px;
            }

            h1 { font-size: 1.5em; }
            h2 { font-size: 1.25em; }
            h3 { font-size: 1.1em; }

            pre {
                padding: 10px;
                font-size: 0.85em;
            }

            .dataframe-table th,
            .dataframe-table td {
                padding: 6px 8px;
                font-size: 0.85em;
            }
        }
        """  # noqa: E501
