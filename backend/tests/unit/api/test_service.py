import pytest
from fastapi.testclient import TestClient
from luml.service import AppService

from tests.support.auth import ANONYMOUS

STATS_EMAIL_SEND_PATH = "/v1/stats/email-send"
WAITLIST_PAYLOAD = {"email": "waitlist@example.com", "description": "landing"}


class TestService:
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
