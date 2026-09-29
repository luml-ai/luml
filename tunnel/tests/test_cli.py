import json
from pathlib import Path

import pytest

from luml_tunnel.cli import KEY_SET_FILE, PRIVATE_KEY_FILE, main
from luml_tunnel.tokens import TokenKind
from luml_tunnel.verification import IssuerKeys, JwksTokenVerifier


def _sign(directory: Path, kind: str, capsys: pytest.CaptureFixture[str]) -> str:
    exit_code = main(
        [
            "dev",
            "token",
            "--private-key",
            str(directory / PRIVATE_KEY_FILE),
            "--kind",
            kind,
            "--issuer",
            "dev-issuer",
            "--relay",
            "dev-relay",
            "--session",
            "k3f9x2ab",
            "--user",
            "developer",
        ]
    )
    assert exit_code == 0
    return capsys.readouterr().out.strip()


async def test_dev_commands_create_keys_and_tokens_the_relay_accepts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["dev", "keygen", "--directory", str(tmp_path)]) == 0
    capsys.readouterr()
    expose_token = _sign(tmp_path, "expose", capsys)
    view_token = _sign(tmp_path, "view", capsys)
    keys = IssuerKeys(str(tmp_path / KEY_SET_FILE))
    verifier = JwksTokenVerifier(keys, "dev-issuer", "dev-relay")

    expose = await verifier.verify(expose_token, TokenKind.EXPOSE)
    view = await verifier.verify(view_token, TokenKind.VIEW, "k3f9x2ab")

    assert expose.session == view.session == "k3f9x2ab"
    assert view.user == "developer"


def test_keygen_writes_private_key_readable_only_by_owner(tmp_path: Path) -> None:
    main(["dev", "keygen", "--directory", str(tmp_path)])

    assert (tmp_path / PRIVATE_KEY_FILE).stat().st_mode & 0o077 == 0
    published = json.loads((tmp_path / KEY_SET_FILE).read_text())
    assert [key["alg"] for key in published["keys"]] == ["ES256"]
    assert "d" not in published["keys"][0]


def test_keygen_does_not_overwrite_an_existing_key(tmp_path: Path) -> None:
    main(["dev", "keygen", "--directory", str(tmp_path)])
    original = (tmp_path / PRIVATE_KEY_FILE).read_text()

    assert main(["dev", "keygen", "--directory", str(tmp_path)]) == 1
    assert (tmp_path / PRIVATE_KEY_FILE).read_text() == original


@pytest.mark.parametrize(
    "arguments",
    [["localhost:5000"], ["10.0.0.5:5000"], ["5000", "--host", "10.0.0.5"], ["0"]],
)
def test_expose_accepts_only_a_port(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["expose", *arguments, "--relay-url", "ws://relay.example/connect", "--token", "t"])

    assert exit_info.value.code == 2


def test_expose_without_a_token_names_the_cause(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("LUML_TUNNEL_TOKEN", raising=False)

    assert main(["expose", "5000", "--relay-url", "ws://relay.example/connect"]) == 1
    assert "LUML_TUNNEL_TOKEN" in capsys.readouterr().err
