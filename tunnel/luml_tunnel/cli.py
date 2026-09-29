import argparse
import asyncio
import json
import logging
import os
import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from luml_tunnel.tokens import TokenKind

PRIVATE_KEY_FILE = "private-key.pem"
KEY_SET_FILE = "jwks.json"
TOKEN_ENV = "LUML_TUNNEL_TOKEN"


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


def _expose(arguments: argparse.Namespace) -> int:
    from luml_tunnel.agent import Agent, AgentRefusedError, FixedToken, LoopbackService

    token = arguments.token or os.environ.get(TOKEN_ENV)
    if not token:
        print(f"Give an expose token with --token or {TOKEN_ENV}", file=sys.stderr)
        return 1
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async def run() -> None:
        service = LoopbackService(arguments.port, arguments.present_loopback_host)
        try:
            await Agent(arguments.relay_url, FixedToken(token), service).run()
        finally:
            await service.aclose()

    try:
        asyncio.run(run())
    except AgentRefusedError as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


def _relay(arguments: argparse.Namespace) -> int:
    import uvicorn

    from luml_tunnel.relay import Relay, RelaySettings
    from luml_tunnel.verification import IssuerKeys, JwksTokenVerifier

    settings = RelaySettings(
        base_domain=arguments.base_domain,
        relay_id=arguments.relay_id,
        issuer=arguments.issuer,
        issuer_keys=arguments.issuer_keys,
    )
    verifier = JwksTokenVerifier(
        IssuerKeys(settings.issuer_keys), settings.issuer, settings.relay_id
    )
    uvicorn.run(
        Relay(settings, verifier), host=arguments.host, port=arguments.port, ws="websockets-sansio"
    )
    return 0


def _port(value: str) -> int:
    if not value.isdigit() or not 0 < int(value) < 65536:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a port; the agent reaches only the loopback address"
        )
    return int(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="luml-tunnel")
    commands = parser.add_subparsers(dest="command", required=True)

    expose = commands.add_parser("expose", help="Expose a service on a loopback port")
    expose.add_argument("port", type=_port, help="Port of the service on the loopback address")
    expose.add_argument("--relay-url", required=True, help="Address agents connect to")
    expose.add_argument("--token", help=f"Expose token; defaults to ${TOKEN_ENV}")
    expose.add_argument(
        "--present-loopback-host",
        action="store_true",
        help="Send the loopback address as the host instead of the public hostname",
    )
    expose.set_defaults(handler=_expose)

    relay = commands.add_parser("relay", help="Run the relay")
    relay.add_argument("--base-domain", required=True)
    relay.add_argument("--relay-id", required=True)
    relay.add_argument("--issuer", required=True)
    relay.add_argument("--issuer-keys", required=True, help="Address or file of the issuer's JWKS")
    relay.add_argument("--host", default="0.0.0.0")
    relay.add_argument("--port", type=int, default=8080)
    relay.set_defaults(handler=_relay)

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
