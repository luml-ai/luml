mermaid_template = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({{ startOnLoad: true }});</script>

  <style>
    html, body {{
      margin: 0;
      padding: 0;
      overflow: hidden;
    }}

    body {{
      display: flex;
      justify-content: center;
      align-items: flex-start;
      min-height: 100vh;
      background: transparent;
      font-family: sans-serif;
    }}

    .mermaid {{
      max-width: 90vw;
      padding: 24px;
      box-sizing: border-box;
    }}

    .mermaid > svg {{
      max-width: 100%;
      height: auto;
    }}
  </style>
</head>

<body>
  <div class="mermaid">
{mermaid_code}
  </div>
</body>
</html>
"""


def create_mermaid_html(mermaid_code: str) -> str:
    return mermaid_template.format(mermaid_code=mermaid_code)
