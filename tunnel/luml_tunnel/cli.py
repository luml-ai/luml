import argparse
import json
import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from luml_tunnel.tokens import TokenKind

PRIVATE_KEY_FILE = "private-key.pem"
KEY_SET_FILE = "jwks.json"


def _dev_keygen(arguments: argparse.Namespace) -> int:
    from luml_tunnel.signing import generate_private_key, key_set, private_key_to_pem

    directory: Path = arguments.directory
    directory.mkdir(parents=True, exist_ok=True)
    private_key = generate_private_key()
    private_key_path = directory / PRIVATE_KEY_FILE
    try:
        private_key_path.touch(mode=0o600, exist_ok=False)
    except FileExistsError:
        print(f"{private_key_path} already exists", file=sys.stderr)
        return 1
    private_key_path.write_text(private_key_to_pem(private_key))
    key_set_path = directory / KEY_SET_FILE
    key_set_path.write_text(json.dumps(key_set(private_key.public_key()), indent=2) + "\n")
    print(f"Private key: {private_key_path}")
    print(f"Public keys: {key_set_path}")
    return 0


def _dev_token(arguments: argparse.Namespace) -> int:
    from luml_tunnel.signing import TokenSigner, load_private_key

    signer = TokenSigner(load_private_key(arguments.private_key.read_text()), arguments.issuer)
    token = signer.sign(
        kind=TokenKind(arguments.kind),
        relay=arguments.relay,
        session=arguments.session,
        user=arguments.user,
        lifetime=timedelta(seconds=arguments.lifetime),
    )
    print(token)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="luml-tunnel")
    commands = parser.add_subparsers(dest="command", required=True)

    dev = commands.add_parser("dev", help="Create keys and tokens for use without LUML")
    dev_commands = dev.add_subparsers(dest="dev_command", required=True)

    keygen = dev_commands.add_parser("keygen", help="Create a signing key and its JWKS file")
    keygen.add_argument("--directory", type=Path, required=True)
    keygen.set_defaults(handler=_dev_keygen)

    token = dev_commands.add_parser("token", help="Sign an expose or a view token")
    token.add_argument("--private-key", type=Path, required=True)
    token.add_argument("--kind", choices=[kind.value for kind in TokenKind], required=True)
    token.add_argument("--issuer", required=True)
    token.add_argument("--relay", required=True)
    token.add_argument("--session", required=True)
    token.add_argument("--user", required=True)
    token.add_argument("--lifetime", type=int, default=3600, help="Lifetime in seconds")
    token.set_defaults(handler=_dev_token)

    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = _build_parser().parse_args(arguments)
    try:
        return int(parsed.handler(parsed))
    except ModuleNotFoundError as error:
        print(
            f"{error.name} is missing; install luml-tunnel[relay] for this command",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
