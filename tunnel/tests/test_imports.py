import subprocess
import sys


def test_core_modules_do_not_import_the_extras() -> None:
    script = (
        "import sys, luml_tunnel, luml_tunnel.tokens, luml_tunnel.relay_api, luml_tunnel.cli, "
        "luml_tunnel.agent; "
        "assert not {'starlette', 'uvicorn', 'luml_api'} & set(sys.modules), sorted(sys.modules)"
    )

    subprocess.run([sys.executable, "-c", script], check=True)
