from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.infra.middleware import SecurityHeadersMiddleware


def test_security_headers_middleware() -> None:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"Hello": "World"}

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Content-Security-Policy"] == "frame-ancestors 'none';"
