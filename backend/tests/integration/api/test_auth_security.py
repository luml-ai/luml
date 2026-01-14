from fastapi.testclient import TestClient
from luml.server import app

# raise_server_exceptions=False allows us to capture 500 errors
# instead of crashing the client
client = TestClient(app, raise_server_exceptions=False)


def test_delete_account_unauthenticated_security() -> None:
    # Calling delete account without auth token
    response = client.delete("/auth/users/me")

    # We expect 401 Unauthorized.
    # Currently it returns 500 (AttributeError) or raises exception
    # if raise_server_exceptions=True
    assert response.status_code == 401, (
        f"Expected 401, got {response.status_code}. content: {response.text}"
    )
