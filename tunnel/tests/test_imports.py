import subprocess
import sys


def test_core_modules_do_not_import_token_libraries() -> None:
    script = (
        "import sys, luml_tunnel, luml_tunnel.tokens, luml_tunnel.cli, luml_tunnel.agent; "
        "assert not {'jwt', 'cryptography'} & set(sys.modules), sorted(sys.modules)"
    )

    subprocess.run([sys.executable, "-c", script], check=True)
