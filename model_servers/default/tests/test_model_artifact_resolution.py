import tarfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from clients.agent_client import AgentClient, ArtifactResolutionError
from handlers.file_handler import ArtifactAccessExpired
from handlers.model_handler import ModelHandler

AGENT_URL = "http://satellite-agent:8000"
DEPLOYMENT_ID = "01a014fd-1ebc-7021-b0f5-fe92f2fdaf9b"
ARTIFACT_ID = "01a014fd-0000-7021-b0f5-fe92f2fdaf9b"
TOKEN = "a-token"
DOWNLOAD_URL = "https://s3.example.com/artifacts/iris.luml?X-Amz-Signature=fresh"


def _agent() -> AgentClient:
    return AgentClient(base_url=AGENT_URL, deployment_id=DEPLOYMENT_ID, token=TOKEN)


def _artifact_route(**kwargs) -> respx.Route:  # noqa: ANN003 — test helper
    return respx.get(f"{AGENT_URL}/satellites/deployments/{DEPLOYMENT_ID}/artifact").mock(**kwargs)


def _ok_response() -> httpx.Response:
    return httpx.Response(200, json={"url": DOWNLOAD_URL, "artifact_id": ARTIFACT_ID})


def _make_archive(tmp_path: Path) -> bytes:
    """A minimal .luml tarball, enough to unpack."""
    payload = tmp_path / "manifest.json"
    payload.write_text('{"name": "iris"}')
    archive = tmp_path / "model.tar"
    with tarfile.open(archive, "w") as tar:
        tar.add(payload, arcname="manifest.json")
    return archive.read_bytes()


def _handler(cache_dir: Path, agent: AgentClient | None = None) -> ModelHandler:
    """A ModelHandler stopped after extraction — building a conda env is not under test."""
    handler = ModelHandler.__new__(ModelHandler)
    handler._model_url = None
    handler._agent = agent or _agent()
    handler._models_cache_dir = cache_dir
    from handlers.file_handler import FileHandler

    handler._file_handler = FileHandler()
    return handler


class TestModelArtifactResolution:
    @respx.mock
    def test_the_url_is_asked_for_at_download_time(self, tmp_path: Path) -> None:
        route = _artifact_route(return_value=_ok_response())
        respx.get(DOWNLOAD_URL).mock(
            return_value=httpx.Response(200, content=_make_archive(tmp_path))
        )
        cache = tmp_path / "models"
        cache.mkdir()

        extracted = _handler(cache)._get_or_extract_model()

        assert route.called
        # keyed on the artifact, not on the URL whose signature changes every request
        assert Path(extracted) == cache / ARTIFACT_ID
        assert (Path(extracted) / "manifest.json").exists()

    @respx.mock
    def test_a_cached_model_never_touches_the_network(self, tmp_path: Path) -> None:
        """This is what lets a container come back up while the Agent or Platform is down.

        The cache key comes from the environment the Agent pinned at container creation, so the
        lookup happens before anything is asked of anyone.
        """
        route = _artifact_route(return_value=_ok_response())
        cache = tmp_path / "models"
        (cache / ARTIFACT_ID).mkdir(parents=True)
        (cache / ARTIFACT_ID / "manifest.json").write_text("{}")

        with patch.dict("os.environ", {"MODEL_ARTIFACT_ID": ARTIFACT_ID}):
            extracted = _handler(cache)._get_or_extract_model()

        assert Path(extracted) == cache / ARTIFACT_ID
        assert not route.called

    @respx.mock
    def test_a_cache_miss_still_asks_the_agent(self, tmp_path: Path) -> None:
        """The pinned id is only a lookup hint; an unpacked model is what makes it a hit."""
        route = _artifact_route(return_value=_ok_response())
        respx.get(DOWNLOAD_URL).mock(
            return_value=httpx.Response(200, content=_make_archive(tmp_path))
        )
        cache = tmp_path / "models"
        cache.mkdir()

        with patch.dict("os.environ", {"MODEL_ARTIFACT_ID": ARTIFACT_ID}):
            extracted = _handler(cache)._get_or_extract_model()

        assert route.called
        assert (Path(extracted) / "manifest.json").exists()

    @respx.mock
    def test_a_url_that_expires_mid_download_is_retried_once(self, tmp_path: Path) -> None:
        """A large artifact can outlive the link it started downloading from.

        The retry must go back to the Agent for a freshly signed link — repeating the request
        on the stale one would be refused the same way. The two links differ so the test can
        tell a real re-ask from a blind retry.
        """
        stale_url = "https://s3.example.com/artifacts/iris.luml?X-Amz-Signature=stale"
        agent_route = _artifact_route(
            side_effect=[
                httpx.Response(200, json={"url": stale_url, "artifact_id": ARTIFACT_ID}),
                _ok_response(),  # a fresh link, signed for the retry
            ]
        )
        respx.get(stale_url).mock(return_value=httpx.Response(403))
        fresh_route = respx.get(DOWNLOAD_URL).mock(
            return_value=httpx.Response(200, content=_make_archive(tmp_path))
        )
        cache = tmp_path / "models"
        cache.mkdir()

        extracted = _handler(cache)._get_or_extract_model()

        assert agent_route.call_count == 2
        assert fresh_route.called
        assert (Path(extracted) / "manifest.json").exists()

    @respx.mock
    def test_a_second_refusal_is_not_retried_forever(self, tmp_path: Path) -> None:
        _artifact_route(return_value=_ok_response())
        respx.get(DOWNLOAD_URL).mock(return_value=httpx.Response(403))
        cache = tmp_path / "models"
        cache.mkdir()

        with pytest.raises(ArtifactAccessExpired):
            _handler(cache)._get_or_extract_model()

    @respx.mock
    def test_a_caller_supplied_url_is_used_as_is(self, tmp_path: Path) -> None:
        """Local runs and tests pass a URL directly; there is no Agent to ask."""
        route = _artifact_route(return_value=_ok_response())
        respx.get(DOWNLOAD_URL).mock(
            return_value=httpx.Response(200, content=_make_archive(tmp_path))
        )
        cache = tmp_path / "models"
        cache.mkdir()

        handler = _handler(cache)
        handler._model_url = DOWNLOAD_URL

        extracted = handler._get_or_extract_model()

        assert not route.called
        assert (Path(extracted) / "manifest.json").exists()

    @respx.mock
    def test_an_unreachable_agent_says_so_plainly(self, tmp_path: Path) -> None:
        _artifact_route(side_effect=httpx.ConnectError("no route to host"))

        with pytest.raises(ArtifactResolutionError, match="unreachable"):
            _agent().fetch_artifact()

    @respx.mock
    def test_a_rejected_token_points_at_the_fix(self) -> None:
        _artifact_route(return_value=httpx.Response(403))

        with pytest.raises(ArtifactResolutionError, match="redeploy"):
            _agent().fetch_artifact()

    def test_a_container_without_its_environment_fails_loudly(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            client = AgentClient()
            assert not client.configured
            with pytest.raises(ArtifactResolutionError, match="missing from the environment"):
                client.fetch_artifact()

    @respx.mock
    def test_a_url_from_an_old_agents_environment_is_honoured(self, tmp_path: Path) -> None:
        """An Agent from before the token contract hands over a URL, not a token.

        Image tags move independently of the Agent, so a new model_server image can be
        launched by an old Agent: MODEL_ARTIFACT_URL set, MODEL_ARTIFACT_TOKEN absent.
        Ignoring the URL would crash-loop a container that holds everything it needs.
        """
        route = _artifact_route(return_value=_ok_response())
        respx.get(DOWNLOAD_URL).mock(
            return_value=httpx.Response(200, content=_make_archive(tmp_path))
        )
        cache = tmp_path / "models"
        cache.mkdir()

        with patch.dict("os.environ", {"MODEL_ARTIFACT_URL": DOWNLOAD_URL}):
            extracted = _handler(cache)._get_or_extract_model()

        assert not route.called  # the Agent was never asked — there is no token to ask with
        assert (Path(extracted) / "manifest.json").exists()

    def test_the_agent_request_ignores_environment_proxies(self) -> None:
        """HTTP_PROXY must not stand between the container and its Agent.

        Deployment environment variables can set proxy variables, and httpx honours
        them by default — the internal request carrying the artifact token would go
        through, and disclose the token to, whatever host they name.
        """
        with patch("clients.agent_client.httpx.get") as get:
            get.return_value = httpx.Response(
                200, json={"url": DOWNLOAD_URL, "artifact_id": ARTIFACT_ID}
            )
            _agent().fetch_artifact()

        assert get.call_args.kwargs["trust_env"] is False

    @respx.mock
    def test_two_containers_unpacking_the_same_artifact_do_not_corrupt_each_other(
        self,
        tmp_path: Path,
    ) -> None:
        """The cache is shared by every model container on the Satellite.

        Two deployments of one artifact can be unpacking it at the same moment. Each stages into
        its own directory, and whoever lands first wins — the archive is immutable, so the loser
        can simply adopt the winner's copy instead of failing or half-overwriting it.
        """
        _artifact_route(return_value=_ok_response())
        respx.get(DOWNLOAD_URL).mock(
            side_effect=lambda request: httpx.Response(200, content=_make_archive(tmp_path))
        )
        cache = tmp_path / "models"
        cache.mkdir()

        first = _handler(cache)._get_or_extract_model()
        # the second container finds the entry already there and takes it
        second = _handler(cache)._get_or_extract_model()

        assert Path(first) == Path(second) == cache / ARTIFACT_ID
        assert (Path(first) / "manifest.json").exists()
        # nothing half-written left behind
        assert not list(cache.glob(".*partial"))

    @respx.mock
    def test_a_loser_of_the_race_adopts_the_winners_copy(self, tmp_path: Path) -> None:
        """The rename lands on a directory that appeared while this one was unpacking."""
        _artifact_route(return_value=_ok_response())
        respx.get(DOWNLOAD_URL).mock(
            return_value=httpx.Response(200, content=_make_archive(tmp_path))
        )
        cache = tmp_path / "models"
        cache.mkdir()
        handler = _handler(cache)

        real_unpack = handler._unpack_model_archive

        def unpack_then_let_the_other_win(archive: Path, staging: Path) -> str:
            result = real_unpack(archive, staging)
            # another container finishes in this window
            winner = cache / ARTIFACT_ID
            winner.mkdir(parents=True)
            (winner / "manifest.json").write_text('{"name": "iris"}')
            return result

        handler._unpack_model_archive = unpack_then_let_the_other_win

        extracted = handler._get_or_extract_model()

        assert Path(extracted) == cache / ARTIFACT_ID
        assert (Path(extracted) / "manifest.json").exists()
        assert not list(cache.glob(".*partial"))
