from datetime import timedelta

import httpx
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from luml_relay.cookies import COOKIE_NAME, ViewerCookies
from luml_relay.frames import RelayLimits
from luml_relay.headers import TOKEN_HEADER, USER_HEADER
from luml_relay.pages import ACCESS_NEEDED_MESSAGE, access_needed_page
from luml_relay.relay import LAUNCH_PATH, Relay
from luml_relay.tokens import TokenKind
from tests.harness import (
    APP_URL,
    BASE_DOMAIN,
    SESSION,
    SESSION_HOST,
    EchoService,
    FakeClock,
    FakeRelayApi,
    Outage,
    create_relay,
    create_verifier,
    running_agent,
    serve,
    viewer,
)

APP_ORIGIN = "https://app.luml.example"
SESSION_ORIGIN = f"https://{SESSION_HOST}"
NAVIGATION = {"sec-fetch-mode": "navigate", "sec-fetch-dest": "document"}
MINUTE = 60.0
HOUR = 60 * MINUTE
WINDOW = MINUTE


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def luml(clock: FakeClock) -> FakeRelayApi:
    return FakeRelayApi(clock=clock)


@pytest.fixture()
def relay(luml: FakeRelayApi, relay_limits: RelayLimits, clock: FakeClock) -> Relay:
    verifier = create_verifier(luml, WINDOW, clock)
    return create_relay(luml, relay_limits, (APP_ORIGIN,), ViewerCookies(clock=clock), verifier)


async def launch(
    client: httpx.AsyncClient, token: str, headers: dict[str, str] | None = None
) -> httpx.Response:
    return await client.get(
        LAUNCH_PATH, params={"token": token}, headers=headers, follow_redirects=False
    )


def relay_cookie(response: httpx.Response) -> str:
    """The relay's cookie from a response, which httpx would not send back over http."""
    [cookie] = [
        header.split(";")[0]
        for header in response.headers.get_list("set-cookie")
        if header.startswith(f"{COOKIE_NAME}=")
    ]
    return cookie


async def launched_cookie(relay_port: int, view_token: str) -> str:
    async with viewer(relay_port, None) as client:
        return relay_cookie(await launch(client, view_token))


async def test_script_reaches_a_session_with_the_token_header(
    connected: None, relay_port: int, view_token: str, echo: EchoService, luml: FakeRelayApi
) -> None:
    async with viewer(relay_port, view_token) as client:
        responses = [await client.get(f"/page/{number}") for number in range(3)]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [request.path for request in echo.requests] == ["/page/0", "/page/1", "/page/2"]
    assert luml.launches == []
    assert not luml.tokens[view_token].launched


async def test_grant_is_not_accepted_in_the_token_header(
    connected: None, relay_port: int, luml: FakeRelayApi, echo: EchoService
) -> None:
    launched_token = luml.issue(TokenKind.VIEW)
    await launched_cookie(relay_port, launched_token)
    async with viewer(relay_port, luml.grant_of(launched_token)) as client:
        response = await client.get("/")

    assert response.status_code == 401
    assert echo.requests == []


async def test_launch_sets_the_cookie_and_redirects_to_the_root(
    connected: None, relay_port: int, view_token: str, echo: EchoService, luml: FakeRelayApi
) -> None:
    async with viewer(relay_port, None) as client:
        launched = await launch(client, view_token)
        cookie = relay_cookie(launched)
        pages = [await client.get(path, headers={"cookie": cookie}) for path in ("/", "/next")]

    assert luml.launches == [view_token]
    assert luml.tokens[view_token].launched
    assert launched.status_code == 303
    assert launched.headers["location"] == "/"
    attributes = {part.strip().lower() for part in launched.headers["set-cookie"].split(";")}
    assert {"path=/", "secure", "httponly", "samesite=none", "partitioned"} <= attributes
    assert not any(attribute.startswith("domain") for attribute in attributes)
    assert launched.headers["referrer-policy"] == "no-referrer"
    assert [page.status_code for page in pages] == [200, 200]
    assert [request.path for request in echo.requests] == ["/", "/next"]


async def test_browser_is_served_through_its_grant_checked_once_per_window(
    connected: None, relay_port: int, view_token: str, luml: FakeRelayApi, clock: FakeClock
) -> None:
    cookie = await launched_cookie(relay_port, view_token)
    async with viewer(relay_port, None) as client:
        within = [
            await client.get(f"/page/{number}", headers={"cookie": cookie}) for number in range(3)
        ]
        checks_within_the_window = len(luml.grant_checks)
        clock.now += WINDOW
        after = await client.get("/page/3", headers={"cookie": relay_cookie(within[-1])})

    assert [response.status_code for response in [*within, after]] == [200] * 4
    assert checks_within_the_window == 1
    assert luml.grant_checks == [luml.grant_of(view_token)] * 2


async def test_launch_token_is_accepted_once(
    connected: None,
    relay_port: int,
    view_token: str,
    luml: FakeRelayApi,
    relay_limits: RelayLimits,
    clock: FakeClock,
) -> None:
    async with viewer(relay_port, view_token) as client:
        header_use = await client.get("/")
    async with viewer(relay_port, None) as client:
        first = await launch(client, view_token)
        cookie = relay_cookie(first)
        second = await launch(client, view_token, NAVIGATION)
        with_cookie = await client.get("/", headers={"cookie": cookie})
    async with viewer(relay_port, view_token) as client:
        header_after_launch = await client.get("/")
    other_relay = create_relay(luml, relay_limits, verifier=create_verifier(luml, WINDOW, clock))
    async with serve(other_relay) as other_port, viewer(other_port, None) as client:
        on_another_relay = await launch(client, view_token)

    assert header_use.status_code == 200
    assert first.status_code == 303
    assert second.status_code == 401
    assert "set-cookie" not in second.headers
    assert "Access is needed" in second.text
    assert header_after_launch.status_code == 401
    assert with_cookie.status_code == 200
    assert on_another_relay.status_code == 401
    assert luml.launches == [view_token] * 3


async def test_grant_outlives_the_view_token(
    connected: None, relay_port: int, luml: FakeRelayApi, clock: FakeClock
) -> None:
    token = luml.issue(TokenKind.VIEW, lifetime=timedelta(minutes=5))
    cookie = await launched_cookie(relay_port, token)
    async with viewer(relay_port, None) as client:
        clock.now += 9 * MINUTE
        earlier = await client.get("/", headers={"cookie": cookie})
        clock.now += MINUTE
        response = await client.get("/", headers={"cookie": relay_cookie(earlier)})

    assert earlier.status_code == 200
    assert response.status_code == 200


async def test_launch_redirects_to_the_destination(
    connected: None, relay_port: int, luml: FakeRelayApi, echo: EchoService
) -> None:
    token = luml.issue(TokenKind.VIEW, destination="/experiments/42?tab=metrics")
    async with viewer(relay_port, None) as client:
        launched = await launch(client, token)
        page = await client.get(
            launched.headers["location"], headers={"cookie": relay_cookie(launched)}
        )

    assert launched.status_code == 303
    assert launched.headers["location"] == "/experiments/42?tab=metrics"
    assert page.status_code == 200
    assert (echo.requests[0].path, echo.requests[0].query) == ("/experiments/42", "tab=metrics")


@pytest.mark.parametrize("destination", ["//evil.example/page", "https://evil.example/", "page"])
async def test_launch_never_redirects_off_the_session_hostname(
    connected: None, relay_port: int, luml: FakeRelayApi, destination: str
) -> None:
    async with viewer(relay_port, None) as client:
        launched = await launch(client, luml.issue(TokenKind.VIEW, destination=destination))

    assert launched.status_code == 303
    assert launched.headers["location"] == "/"


async def test_launch_while_luml_cannot_answer_asks_to_try_again(
    connected: None, relay_port: int, view_token: str, luml: FakeRelayApi
) -> None:
    luml.outage = Outage.UNREACHABLE
    async with viewer(relay_port, None) as client:
        response = await launch(client, view_token)

    assert response.status_code == 503
    assert "try again" in response.text
    assert "set-cookie" not in response.headers
    assert not luml.tokens[view_token].launched


async def test_cached_grant_is_served_while_luml_cannot_answer(
    connected: None, relay_port: int, luml: FakeRelayApi, clock: FakeClock
) -> None:
    cached = await launched_cookie(relay_port, luml.issue(TokenKind.VIEW))
    async with viewer(relay_port, None) as client:
        first = await client.get("/", headers={"cookie": cached})
        new = await launched_cookie(relay_port, luml.issue(TokenKind.VIEW))
        luml.outage = Outage.UNREACHABLE
        clock.now += 2 * WINDOW
        served = await client.get("/", headers={"cookie": relay_cookie(first)})
        refused = await client.get("/", headers={"cookie": new})

    assert served.status_code == 200
    assert refused.status_code == 503
    assert "try again" in refused.text


async def test_ending_the_session_revokes_viewers_with_a_cookie(
    connected: None, relay_port: int, view_token: str, luml: FakeRelayApi, clock: FakeClock
) -> None:
    cookie = await launched_cookie(relay_port, view_token)
    async with viewer(relay_port, None) as client:
        before = await client.get("/", headers={"cookie": cookie})
        luml.ended_sessions.add(SESSION)
        clock.now += WINDOW
        after = await client.get("/", headers={"cookie": relay_cookie(before), **NAVIGATION})

    assert before.status_code == 200
    assert after.status_code == 401
    assert "Access is needed" in after.text


@pytest.mark.parametrize("token_kind", [TokenKind.EXPOSE, "other-session", "missing"])
async def test_launch_refuses_a_token_that_does_not_fit(
    connected: None, relay_port: int, luml: FakeRelayApi, token_kind: TokenKind | str
) -> None:
    async with viewer(relay_port, None) as client:
        if token_kind == "missing":
            response = await client.get(LAUNCH_PATH, follow_redirects=False)
        elif token_kind == "other-session":
            response = await launch(client, luml.issue(TokenKind.VIEW, session="other1"))
        else:
            response = await launch(client, luml.issue(TokenKind.EXPOSE))

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


async def test_cookie_ends_after_30_minutes_without_requests(
    connected: None, relay_port: int, view_token: str, clock: FakeClock, luml: FakeRelayApi
) -> None:
    cookie = await launched_cookie(relay_port, view_token)
    async with viewer(relay_port, None) as client:
        clock.now += 29 * MINUTE
        within = await client.get("/", headers={"cookie": cookie})
        cookie = relay_cookie(within)
        clock.now += 30 * MINUTE
        checks_before = len(luml.grant_checks)
        after = await client.get("/", headers={"cookie": cookie, **NAVIGATION})

    assert within.status_code == 200
    assert after.status_code == 401
    assert "Access is needed" in after.text
    assert len(luml.grant_checks) == checks_before


async def test_cookie_ends_after_12_hours_in_any_case(
    connected: None, relay_port: int, view_token: str, clock: FakeClock, luml: FakeRelayApi
) -> None:
    launched_at = clock.now
    cookie = await launched_cookie(relay_port, view_token)
    statuses: list[int] = []
    async with viewer(relay_port, None) as client:
        while clock.now + 10 * MINUTE < launched_at + 12 * HOUR:
            clock.now += 10 * MINUTE
            response = await client.get("/", headers={"cookie": cookie})
            statuses.append(response.status_code)
            cookie = relay_cookie(response)
        clock.now = launched_at + 12 * HOUR
        checks_before = len(luml.grant_checks)
        after = await client.get("/", headers={"cookie": cookie, **NAVIGATION})

    assert set(statuses) == {200}
    assert after.status_code == 401
    assert "Access is needed" in after.text
    assert len(luml.grant_checks) == checks_before


async def test_cookie_is_valid_for_one_session_only(
    connected: None, relay_port: int, view_token: str
) -> None:
    cookie = await launched_cookie(relay_port, view_token)
    async with viewer(relay_port, None, host=f"other1.{BASE_DOMAIN}") as client:
        response = await client.get("/", headers={"cookie": cookie})

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "fetch_headers", "status"),
    [
        ("POST", {"sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate"}, 403),
        ("GET", {"sec-fetch-site": "cross-site", "sec-fetch-mode": "cors"}, 403),
        ("GET", {"sec-fetch-site": "same-site", "sec-fetch-mode": "no-cors"}, 403),
        ("POST", {"origin": "https://evil.example"}, 403),
        ("POST", {"origin": "null"}, 403),
        ("GET", {"sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate"}, 200),
        ("GET", {"sec-fetch-site": "none", "sec-fetch-mode": "navigate"}, 200),
        ("POST", {"sec-fetch-site": "same-origin", "sec-fetch-mode": "cors"}, 200),
        ("POST", {"origin": f"http://{SESSION_HOST}"}, 200),
        ("GET", {}, 200),
    ],
)
async def test_requests_started_by_other_sites_are_refused(
    connected: None,
    relay_port: int,
    view_token: str,
    echo: EchoService,
    method: str,
    fetch_headers: dict[str, str],
    status: int,
) -> None:
    cookie = await launched_cookie(relay_port, view_token)
    async with viewer(relay_port, None) as client:
        response = await client.request(method, "/", headers={"cookie": cookie, **fetch_headers})

    assert response.status_code == status
    assert len(echo.requests) == (1 if status == 200 else 0)


async def test_websocket_started_by_another_site_is_refused(
    connected: None, relay_port: int, view_token: str
) -> None:
    cookie = await launched_cookie(relay_port, view_token)

    def open_websocket(origin: str) -> connect:
        return connect(
            f"ws://{SESSION_HOST}/ws/echo",
            host="127.0.0.1",
            port=relay_port,
            proxy=None,
            additional_headers={"cookie": cookie, "origin": origin},
        )

    with pytest.raises(InvalidStatus) as refused:
        await open_websocket("https://evil.example")
    async with open_websocket(f"http://{SESSION_HOST}") as websocket:
        greeting = await websocket.recv()

    assert refused.value.response.status_code == 403
    assert greeting == "hello"


async def test_request_without_access(connected: None, relay_port: int, echo: EchoService) -> None:
    async with viewer(relay_port, None) as client:
        navigation = await client.get("/page", headers=NAVIGATION)
        script = await client.get("/page", headers={"sec-fetch-mode": "cors"})
        legacy_navigation = await client.get("/page", headers={"accept": "text/html"})

    assert navigation.status_code == 401
    assert navigation.headers["content-type"].startswith("text/html")
    assert "Access is needed" in navigation.text
    assert legacy_navigation.headers["content-type"].startswith("text/html")
    assert script.status_code == 401
    assert script.headers["content-type"].startswith("text/plain")
    assert echo.requests == []


async def test_access_needed_page_tells_the_embedding_app(connected: None, relay_port: int) -> None:
    async with viewer(relay_port, None) as client:
        page = await client.get("/", headers=NAVIGATION)

    assert "window.parent.postMessage" in page.text
    assert ACCESS_NEEDED_MESSAGE in page.text
    assert f'"{APP_ORIGIN}"' in page.text
    assert page.headers["content-security-policy"] == f"frame-ancestors {APP_ORIGIN}"


async def test_access_needed_page_as_a_top_level_document(connected: None, relay_port: int) -> None:
    async with viewer(relay_port, None) as client:
        page = await client.get("/", headers=NAVIGATION)

    assert "Open this flow again from" in page.text
    assert f'<a href="{APP_URL}">the LUML app</a>' in page.text
    # The message goes out only from inside a frame, so a top-level tab posts nothing.
    assert "if (window.parent !== window)" in page.text


def test_access_needed_page_without_app_origins_or_address() -> None:
    page = access_needed_page(SESSION, (), "")

    assert "<script>" not in page
    assert "<a " not in page
    assert "Open this flow again from the LUML app" in page


def test_access_needed_page_escapes_the_app_address() -> None:
    page = access_needed_page(SESSION, (), "https://app.example/?a=1&b=2")

    assert '<a href="https://app.example/?a=1&amp;b=2">' in page


async def test_session_not_connected_page(relay_port: int, view_token: str) -> None:
    async with viewer(relay_port, view_token) as client:
        response = await client.get("/", headers=NAVIGATION)

    assert response.status_code == 502
    assert response.headers["content-type"].startswith("text/html")
    assert "The session is not connected" in response.text
    assert response.headers["content-security-policy"] == f"frame-ancestors {APP_ORIGIN}"


async def test_what_the_service_sees_of_a_viewer_with_a_cookie(
    connected: None, relay_port: int, luml: FakeRelayApi, echo: EchoService
) -> None:
    cookie = await launched_cookie(relay_port, luml.issue(TokenKind.VIEW, user="U"))
    async with viewer(relay_port, None) as client:
        await client.get(
            "/", headers={"cookie": f"theme=dark; {cookie}; lang=en", USER_HEADER: "someone-else"}
        )

    [received] = echo.requests
    assert received.header(USER_HEADER) == ["U"]
    assert received.header("cookie") == ["theme=dark; lang=en"]
    assert received.header(TOKEN_HEADER) == []


async def test_framing_is_limited_to_the_luml_app(
    connected: None, relay_port: int, view_token: str
) -> None:
    async with viewer(relay_port, view_token) as client:
        response = await client.get("/no-frames")

    assert response.headers.get_list("content-security-policy") == [
        "default-src 'self'",
        f"frame-ancestors {APP_ORIGIN}",
    ]
    assert "x-frame-options" not in response.headers


async def test_framing_is_forbidden_without_an_app_origin(
    luml: FakeRelayApi, service_port: int
) -> None:
    relay = create_relay(luml)
    async with (
        serve(relay) as relay_port,
        running_agent(relay, relay_port, luml.issue(TokenKind.EXPOSE), service_port),
        viewer(relay_port, luml.issue(TokenKind.VIEW)) as client,
    ):
        response = await client.get("/no-frames")

    assert response.headers.get_list("content-security-policy") == [
        "default-src 'self'",
        "frame-ancestors 'none'",
    ]
    assert response.headers.get_list("x-frame-options") == ["DENY"]


async def test_cookies_of_the_service_stay_on_the_session_hostname(
    connected: None, relay_port: int, view_token: str
) -> None:
    async with viewer(relay_port, view_token) as client:
        response = await client.get("/domain-cookie")

    [cookie] = response.headers.get_list("set-cookie")
    assert cookie.startswith("service=1;")
    assert "domain" not in cookie.lower()
    assert "httponly" in cookie.lower()


def test_cookie_with_a_forged_signature_is_refused(clock: FakeClock) -> None:
    cookies = ViewerCookies(b"secret", clock=clock)
    forged = ViewerCookies(b"other", clock=clock).issue(SESSION, "U", "grant-1")

    assert cookies.renew(forged.value, SESSION) is None
    assert cookies.renew("not-a-cookie", SESSION) is None
    assert cookies.renew("é.é", SESSION) is None
    renewed = cookies.renew(cookies.issue(SESSION, "U", "grant-1").value, SESSION)
    assert renewed is not None
    assert (renewed.user, renewed.grant) == ("U", "grant-1")
