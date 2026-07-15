from tests.support import build_app, client_for, introspect_returning, make_claims

from agent.schemas.monitoring import MonitoringIntrospection

_INACTIVE = introspect_returning(MonitoringIntrospection(active=False))


async def test_csp_frame_ancestors_restricts_to_platform_origin() -> None:
    app = build_app(
        introspect_returning(MonitoringIntrospection(active=True, claims=make_claims())),
        frame_ancestors=["https://app.luml.ai"],
    )

    async with client_for(app) as client:
        resp = await client.get("/monitoring/launch", params={"token": "t"}, follow_redirects=False)

    csp = resp.headers["content-security-policy"]
    assert csp == "frame-ancestors https://app.luml.ai"
    assert "https://evil.example" not in csp


async def test_csp_allows_multiple_platform_origins() -> None:
    app = build_app(_INACTIVE, frame_ancestors=["https://app.luml.ai", "https://eu.luml.ai"])

    async with client_for(app) as client:
        resp = await client.get("/monitoring/launch", params={"token": "x"}, follow_redirects=False)

    assert resp.headers["content-security-policy"] == (
        "frame-ancestors https://app.luml.ai https://eu.luml.ai"
    )


async def test_csp_defaults_to_none_when_no_origins_configured() -> None:
    app = build_app(_INACTIVE, frame_ancestors=[])

    async with client_for(app) as client:
        resp = await client.get("/monitoring/launch", params={"token": "x"}, follow_redirects=False)

    assert resp.headers["content-security-policy"] == "frame-ancestors 'none'"


async def test_csp_present_on_denied_response() -> None:
    app = build_app(_INACTIVE, frame_ancestors=["https://app.luml.ai"])

    async with client_for(app) as client:
        resp = await client.get("/monitoring/launch", params={"token": "x"}, follow_redirects=False)

    assert resp.status_code == 403
    assert resp.headers["content-security-policy"] == "frame-ancestors https://app.luml.ai"


async def test_static_dashboard_bundle_served_with_csp() -> None:
    app = build_app(_INACTIVE, frame_ancestors=["https://app.luml.ai"])

    async with client_for(app) as client:
        resp = await client.get("/monitoring/app/")

    assert resp.status_code == 200
    assert '<div id="app">' in resp.text
    assert resp.headers["content-security-policy"] == "frame-ancestors https://app.luml.ai"
