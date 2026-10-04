import argparse
import asyncio
import logging
import os
import signal
import sys
from collections.abc import Sequence

from luml_relay.frames import MAX_FRAME_BYTES, RelayLimits
from luml_relay.protocol import MAX_RENEWALS_PER_MINUTE
from luml_relay.relay_api import (
    DEFAULT_BASE_URL,
    MAX_REQUESTS_IN_FLIGHT,
    REPORT_INTERVAL_SECONDS,
    RelayApi,
    RelayTokenRefusedError,
)
from luml_relay.routing import MAX_AGENTS
from luml_relay.tokens import CACHE_WINDOW_SECONDS, MAX_CACHE_ENTRIES

TOKEN_ENV = "LUML_SESSION_TOKEN"
COOKIE_SECRET_ENV = "LUML_RELAY_COOKIE_SECRET"
RELAY_TOKEN_ENV = "LUML_RELAY_TOKEN"
BASE_URL_ENV = "LUML_BASE_URL"


def _expose(arguments: argparse.Namespace) -> int:
    registration = (arguments.organization, arguments.orbit)
    if arguments.relay_url is not None and (any(registration) or arguments.label):
        print("Give either --relay-url or --organization and --orbit", file=sys.stderr)
        return 2
    if arguments.relay_url is None:
        if not all(registration):
            print(
                "Give --organization and --orbit to start a session at LUML, "
                "or --relay-url and a token to connect directly",
                file=sys.stderr,
            )
            return 2
        return _expose_through_luml(arguments)
    return _expose_directly(arguments)


def _expose_directly(arguments: argparse.Namespace) -> int:
    from luml_relay.agent import Agent, AgentRefusedError, FixedToken, LoopbackService

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


def _expose_through_luml(arguments: argparse.Namespace) -> int:
    from luml_relay.agent import AgentRefusedError, LoopbackService
    from luml_relay.luml import LumlSessionError, expose_through_luml

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async def run() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for stop_signal in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(stop_signal, stop.set)
        service = LoopbackService(arguments.port, arguments.present_loopback_host)
        try:
            await expose_through_luml(
                arguments.organization, arguments.orbit, arguments.label, service, stop
            )
        finally:
            await service.aclose()

    try:
        asyncio.run(run())
    except (LumlSessionError, AgentRefusedError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


def _relay(arguments: argparse.Namespace) -> int:
    relay_token = os.environ.get(RELAY_TOKEN_ENV)
    if not relay_token:
        print(f"Set {RELAY_TOKEN_ENV} to the relay's token from LUML", file=sys.stderr)
        return 1
    base_url = os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        api = RelayApi(base_url, relay_token, max_in_flight=arguments.max_validations_in_flight)
        asyncio.run(_serve_relay(api, arguments))
    except RelayTokenRefusedError as error:
        print(
            f"LUML at {base_url} refused the relay token in {RELAY_TOKEN_ENV} ({error}); "
            "set it to the relay's current token",
            file=sys.stderr,
        )
        return 1
    return 0


async def _serve_relay(api: RelayApi, arguments: argparse.Namespace) -> None:
    """Serve sessions once LUML has described the relay."""
    import uvicorn

    from luml_relay.relay import Relay, RelayServer, RelaySettings, describe_relay
    from luml_relay.tokens import LumlTokenVerifier

    try:
        description = await describe_relay(api)
        logging.getLogger(__name__).info(
            "Serving sessions of relay %s under %s", description.label, description.base_domain
        )
        settings = RelaySettings(
            base_domain=description.base_domain,
            limits=RelayLimits(
                max_concurrent_streams=arguments.max_concurrent_streams,
                max_request_body_bytes=arguments.max_request_body_bytes,
                idle_timeout_seconds=arguments.idle_timeout,
            ),
            app_origins=description.app_origins,
            app_url=description.app_url,
            cookie_secret=os.environ.get(COOKIE_SECRET_ENV, "").encode() or None,
            max_agents=arguments.max_agents,
            max_renewals_per_minute=arguments.max_renewals_per_minute,
            report_interval=arguments.report_interval,
        )
        verifier = LumlTokenVerifier(
            api, arguments.cache_window, max_entries=arguments.max_cache_entries
        )
        relay = Relay(settings, verifier, reports_to=api)
        config = uvicorn.Config(
            relay,
            host=arguments.host,
            port=arguments.port,
            ws="websockets-sansio",
            ws_max_size=MAX_FRAME_BYTES,
        )
        await RelayServer(relay, config).serve()
    finally:
        await api.aclose()


def _port(value: str) -> int:
    if not value.isdigit() or not 0 < int(value) < 65536:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a port; the agent reaches only the loopback address"
        )
    return int(value)


def _positive_int(value: str) -> int:
    if not value.isdigit() or int(value) == 0:
        raise argparse.ArgumentTypeError(f"{value!r} is not a positive integer")
    return int(value)


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = 0.0
    if not number > 0:
        raise argparse.ArgumentTypeError(f"{value!r} is not a positive number")
    return number


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="luml-relay")
    commands = parser.add_subparsers(dest="command", required=True)

    expose = commands.add_parser("expose", help="Expose a service on a loopback port")
    expose.add_argument("port", type=_port, help="Port of the service on the loopback address")
    expose.add_argument("--label", help="Label of the session in LUML, for operators")
    expose.add_argument("--organization", help="Organization in LUML, by id or name")
    expose.add_argument("--orbit", help="Orbit in LUML, by id or name")
    expose.add_argument("--relay-url", help="Address agents connect to, to connect without LUML")
    expose.add_argument(
        "--token", help=f"Expose token when connecting without LUML; defaults to ${TOKEN_ENV}"
    )
    expose.add_argument(
        "--present-loopback-host",
        action="store_true",
        help="Send the loopback address as the host instead of the public hostname",
    )
    expose.set_defaults(handler=_expose)

    relay = commands.add_parser(
        "serve",
        help="Run the relay",
        description=f"Run the relay. It reads the address of LUML from ${BASE_URL_ENV}, its "
        f"token from ${RELAY_TOKEN_ENV} and, optionally, the secret that signs its cookies "
        f"from ${COOKIE_SECRET_ENV}; everything else it learns from LUML.",
    )
    relay.add_argument("--host", default="0.0.0.0")
    relay.add_argument("--port", type=int, default=8080)
    default_limits = RelayLimits()
    relay.add_argument(
        "--max-concurrent-streams",
        type=_positive_int,
        default=default_limits.max_concurrent_streams,
        help="Open requests allowed per session",
    )
    relay.add_argument(
        "--max-request-body-bytes",
        type=_positive_int,
        default=default_limits.max_request_body_bytes,
    )
    relay.add_argument(
        "--idle-timeout",
        type=_positive_float,
        default=default_limits.idle_timeout_seconds,
        help="Seconds a request may pass without any data before the relay ends it",
    )
    relay.add_argument(
        "--cache-window",
        type=_positive_float,
        default=CACHE_WINDOW_SECONDS,
        help="Seconds a verdict of LUML on a token is reused before LUML is asked again "
        "(default: %(default)s)",
    )
    relay.add_argument(
        "--max-cache-entries",
        type=_positive_int,
        default=MAX_CACHE_ENTRIES,
        help="Verdicts of LUML kept; beyond them the oldest are evicted (default: %(default)s)",
    )
    relay.add_argument(
        "--max-validations-in-flight",
        type=_positive_int,
        default=MAX_REQUESTS_IN_FLIGHT,
        help="Requests to LUML, token validations above all, open at once; more wait for a "
        "slot, and one that cannot get it in time is answered 'try again' "
        "(default: %(default)s)",
    )
    relay.add_argument(
        "--max-agents",
        type=_positive_int,
        default=MAX_AGENTS,
        help="Agents connected at once; one more is refused with status 503 (default: %(default)s)",
    )
    relay.add_argument(
        "--max-renewals-per-minute",
        type=_positive_int,
        default=MAX_RENEWALS_PER_MINUTE,
        help="Renewed tokens checked per agent connection and minute; more are dropped "
        "unchecked (default: %(default)s)",
    )
    relay.add_argument(
        "--report-interval",
        type=_positive_float,
        default=REPORT_INTERVAL_SECONDS,
        help="Seconds between reports of the connected agents to LUML (default: %(default)s)",
    )
    relay.set_defaults(handler=_relay)

    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = _build_parser().parse_args(arguments)
    try:
        return int(parsed.handler(parsed))
    except ModuleNotFoundError as error:
        extra = "luml" if (error.name or "").startswith("luml_api") else "server"
        print(
            f"{error.name} is missing; install luml-relay[{extra}] for this command",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
