import uuid
from http.cookies import SimpleCookie

from tests.support import (
    build_app,
    client_for,
    introspect_raises,
    introspect_returning,
    make_claims,
)

from agent.monitoring import SESSION_COOKIE_NAME
from agent.monitoring.app import MONITORING_APP_PATH
from agent.schemas.monitoring import MONITORING_READ_SCOPE, MonitoringIntrospection


def _session_id(set_cookie: str) -> str:
    jar: SimpleCookie = SimpleCookie()
    jar.load(set_cookie)
    return jar[SESSION_COOKIE_NAME].value


async def test_valid_token_issues_session_and_clean_redirect() -> None:
    claims = make_claims()
    app = build_app(introspect_returning(MonitoringIntrospection(active=True, claims=claims)))

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/launch", params={"token": "launch-token"}, follow_redirects=False
        )

    assert resp.status_code == 303
    assert resp.headers["location"] == MONITORING_APP_PATH
    assert "launch-token" not in resp.headers["location"]
    assert "token" not in resp.headers["location"]

    set_cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=none" in set_cookie
    assert "path=/monitoring" in set_cookie
    assert _session_id(resp.headers["set-cookie"])


async def test_session_cookie_resolves_to_token_deployment() -> None:
    deployment_id = uuid.uuid4()
    claims = make_claims(deployment_id=deployment_id)
    app = build_app(introspect_returning(MonitoringIntrospection(active=True, claims=claims)))

    async with client_for(app) as client:
        launch = await client.get(
            "/monitoring/launch", params={"token": "t"}, follow_redirects=False
        )
        session_id = _session_id(launch.headers["set-cookie"])
        resp = await client.get(
            "/monitoring/api/session",
            headers={"cookie": f"{SESSION_COOKIE_NAME}={session_id}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["deployment_id"] == str(deployment_id)
    assert body["scope"] == MONITORING_READ_SCOPE


async def test_invalid_or_expired_token_is_denied() -> None:
    app = build_app(introspect_returning(MonitoringIntrospection(active=False)))

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/launch", params={"token": "expired"}, follow_redirects=False
        )

    assert resp.status_code == 403
    assert "set-cookie" not in resp.headers


async def test_missing_token_is_denied() -> None:
    active = MonitoringIntrospection(active=True, claims=make_claims())
    app = build_app(introspect_returning(active))

    async with client_for(app) as client:
        resp = await client.get("/monitoring/launch", follow_redirects=False)

    assert resp.status_code == 403
    assert "set-cookie" not in resp.headers


async def test_wrong_scope_is_denied() -> None:
    claims = make_claims(scope="inference:write")
    app = build_app(introspect_returning(MonitoringIntrospection(active=True, claims=claims)))

    async with client_for(app) as client:
        resp = await client.get("/monitoring/launch", params={"token": "t"}, follow_redirects=False)

    assert resp.status_code == 403
    assert "set-cookie" not in resp.headers


async def test_single_use_token_refused_on_reuse() -> None:
    claims = make_claims()
    introspect = introspect_returning(
        MonitoringIntrospection(active=True, claims=claims),
        MonitoringIntrospection(active=False),
    )
    app = build_app(introspect)

    async with client_for(app) as client:
        first = await client.get(
            "/monitoring/launch", params={"token": "once"}, follow_redirects=False
        )
        second = await client.get(
            "/monitoring/launch", params={"token": "once"}, follow_redirects=False
        )

    assert first.status_code == 303
    assert second.status_code == 403
    assert "set-cookie" not in second.headers


async def test_platform_introspection_failure_is_unavailable() -> None:
    app = build_app(introspect_raises)

    async with client_for(app) as client:
        resp = await client.get("/monitoring/launch", params={"token": "t"}, follow_redirects=False)

    assert resp.status_code == 502
    assert "set-cookie" not in resp.headers
