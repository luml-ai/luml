import html
import json

ACCESS_NEEDED_MESSAGE = "luml-relay:access-needed"

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: system-ui, sans-serif; color: #1f2937; display: grid;
  place-items: center; min-height: 100vh; margin: 0; }}
main {{ max-width: 28rem; padding: 1.5rem; text-align: center; }}
h1 {{ font-size: 1.25rem; }}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p>{text}</p>
</main>
{script}
</body>
</html>
"""

# Posted once per origin, and only inside a frame; the browser delivers it only to a parent
# on a matching origin.
_ACCESS_NEEDED_SCRIPT = """<script>
if (window.parent !== window) {{
  for (const origin of {origins}) {{
    window.parent.postMessage({message}, origin);
  }}
}}
</script>"""


def access_needed_page(session: str, app_origins: tuple[str, ...], app_url: str) -> str:
    message = {"type": ACCESS_NEEDED_MESSAGE, "session": session}
    script = _ACCESS_NEEDED_SCRIPT.format(
        origins=_script_json(list(app_origins)), message=_script_json(message)
    )
    app = f'<a href="{html.escape(app_url)}">the LUML app</a>' if app_url else "the LUML app"
    return _PAGE.format(
        title="Access is needed",
        text=f"Open this flow again from {app} to view it.",
        script=script if app_origins else "",
    )


def not_connected_page() -> str:
    return _PAGE.format(
        title="The session is not connected",
        text="The agent of this session is not connected to the relay. "
        "It may be restarting, or the session has ended.",
        script="",
    )


def _script_json(value: object) -> str:
    # Escaped so a value can never end the script element.
    return json.dumps(value).replace("<", "\\u003c")
