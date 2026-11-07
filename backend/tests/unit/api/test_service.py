import pytest
from fastapi.testclient import TestClient
from luml.service import AppService

from tests.support.auth import ANONYMOUS

STATS_EMAIL_SEND_PATH = "/v1/stats/email-send"
WAITLIST_PAYLOAD = {"email": "waitlist@example.com", "description": "landing"}


class TestService:
    def test_openapi_preserves_metadata_and_authentication_after_route_changes(
        self, app: AppService
    ) -> None:
        def endpoint() -> dict[str, str]:
            return {"status": "ok"}

        for register_route in [False, True]:
            if register_route:
                app.add_api_route("/schema-regression", endpoint)
            schema = app.openapi()
            assert schema["info"] == {
                "title": "LUML AI API",
                "version": "1.0.0",
                "description": "API docs for LUML AI",
            }
            assert schema["components"]["securitySchemes"]["BearerAuth"] == {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
            assert schema["security"] == [{"BearerAuth": []}]
            assert ("/schema-regression" in schema["paths"]) == register_route

    @pytest.mark.parametrize("principal", [ANONYMOUS], indirect=True)
    def test_stats_email_send_is_not_routed_for_an_anonymous_caller(
        self, client: TestClient
    ) -> None:
        response = client.post(STATS_EMAIL_SEND_PATH, json=WAITLIST_PAYLOAD)

        assert response.status_code == 404

    def test_stats_email_send_is_not_routed_for_an_authenticated_caller(
        self, client: TestClient
    ) -> None:
        response = client.post(STATS_EMAIL_SEND_PATH, json=WAITLIST_PAYLOAD)

        assert response.status_code == 404

    def test_stats_email_send_is_absent_from_the_openapi_schema(
        self, app: AppService
    ) -> None:
        assert STATS_EMAIL_SEND_PATH not in app.openapi()["paths"]

    def test_openapi_keeps_metadata_and_authentication_after_routes_change(
        self,
    ) -> None:
        app = AppService()
        app.openapi()

        @app.get("/schema-check")
        def schema_check() -> dict[str, bool]:
            return {"ok": True}

        schema = TestClient(app).get("/openapi.json").json()

        assert "/schema-check" in schema["paths"]
        assert schema["info"] == {
            "title": "LUML AI API",
            "version": "1.0.0",
            "description": "API docs for LUML AI",
        }
        assert schema["components"]["securitySchemes"]["BearerAuth"] == {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        assert schema["security"] == [{"BearerAuth": []}]

    def test_json_body_without_content_type_is_parsed(self) -> None:
        app = AppService()

        @app.post("/body-check")
        def body_check(payload: dict[str, int]) -> dict[str, int]:
            return payload

        response = TestClient(app).post("/body-check", content=b'{"value": 1}')

        assert "content-type" not in response.request.headers
        assert response.status_code == 200
        assert response.json() == {"value": 1}

    def test_json_body_with_a_non_json_content_type_is_rejected(self) -> None:
        app = AppService()

        @app.post("/body-check")
        def body_check(payload: dict[str, int]) -> dict[str, int]:
            return payload

        response = TestClient(app).post(
            "/body-check",
            content=b'{"value": 1}',
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 422
