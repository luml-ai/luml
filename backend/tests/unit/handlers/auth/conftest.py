import uuid
from dataclasses import dataclass
from time import time

import jwt
import pytest
from luml.clients.oauth_providers import OAuthGoogleProvider
from luml.handlers.auth import AuthHandler
from luml.schemas.auth import Token

from tests.support.mocks import CollaboratorMocks, mock_collaborators

SECRET_KEY = "test"
ALGORITHM = "HS256"


@dataclass
class Passwords:
    password: str
    hashed_password: str


@pytest.fixture
def mocks() -> CollaboratorMocks[AuthHandler]:
    return mock_collaborators(
        AuthHandler(
            secret_key=SECRET_KEY,
            algorithm=ALGORITHM,
            oauth_provider=OAuthGoogleProvider,
        )
    )


@pytest.fixture
def passwords() -> Passwords:
    return Passwords(
        password="test_password",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$GZPWq5NMO1CsJrHq+EpiTA$E2QWHVvlRyMcPb4231Bh9pBhnjjENgeqYdb1M7lsIXs",
    )


@pytest.fixture
def tokens() -> Token:
    email = str(uuid.uuid4())
    now = int(time())
    access_payload = {"sub": email, "exp": now + 3600}
    refresh_payload = {
        "sub": email,
        "type": "refresh",
        "exp": now + 7200,
    }

    return Token(
        access_token=jwt.encode(access_payload, SECRET_KEY, algorithm=ALGORITHM),
        refresh_token=jwt.encode(refresh_payload, SECRET_KEY, algorithm=ALGORITHM),
        token_type="bearer",
    )


@pytest.fixture
def tokens_by_purpose(mocks: CollaboratorMocks[AuthHandler]) -> dict[str, str]:
    email = "purpose@example.com"
    signed_in_tokens = mocks.handler._create_tokens(email)
    assert signed_in_tokens.refresh_token

    return {
        "access": signed_in_tokens.access_token,
        "refresh": signed_in_tokens.refresh_token,
        "email_confirmation": mocks.handler._generate_email_confirmation_token(email),
        "password_reset": mocks.handler._generate_password_reset_token(email),
        "legacy_typeless": mocks.handler._create_token(
            data={"sub": email}, expires_delta=3600
        ),
    }
