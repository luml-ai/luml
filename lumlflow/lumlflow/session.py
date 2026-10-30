import os
import secrets
from pathlib import Path

SESSION_TOKEN_FILE = ".lumlflow-session-token"


def stored_session_token(store: Path, rotate: bool = False) -> str:
    path = store / SESSION_TOKEN_FILE
    if not rotate and path.is_file():
        token = path.read_text().strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    store.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as file:
        file.write(token)
    path.chmod(0o600)
    return token
