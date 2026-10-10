import subprocess
import sys


def test_core_modules_do_not_import_the_extras() -> None:
    script = (
        "import sys, luml_relay, luml_relay.tokens, luml_relay.relay_api, luml_relay.cli, "
        "luml_relay.agent; "
        "assert not {'starlette', 'uvicorn', 'luml_api'} & set(sys.modules), sorted(sys.modules)"
    )

    subprocess.run([sys.executable, "-c", script], check=True)
