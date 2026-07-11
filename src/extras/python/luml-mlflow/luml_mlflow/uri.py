from dataclasses import dataclass
from urllib.parse import parse_qs, quote, urlparse

LUML_SCHEME = "luml"
LOCAL_HOST = "local"
RUNS_SEGMENT = "runs"
ARTIFACTS_SEGMENT = "artifacts"
MODEL_NAME_PARAM = "name"


@dataclass(frozen=True)
class LumlTarget:
    """A parsed ``luml://...`` tracking URI.

    Either ``local_only`` is ``True`` (a ``luml://local`` URI) or both ``org``
    and ``orbit`` are populated. The sync layer treats local-only targets as
    skipped uploads.
    """

    org: str | None
    orbit: str | None
    local_only: bool

    @property
    def sync_eligible(self) -> bool:
        return not self.local_only and self.org is not None and self.orbit is not None


@dataclass(frozen=True)
class LumlArtifactLocation:
    """A parsed ``luml://.../runs/<run_id>/artifacts`` artifact URI.

    Combines the resolved :class:`LumlTarget` with the owning run id so the
    artifact repository can write into the right luml experiment. ``model_name``
    carries the optional ``?name=`` hint a LoggedModel artifact location sets so
    the model is stored under its MLflow-given name.
    """

    target: LumlTarget
    run_id: str
    model_name: str | None = None


def build_artifact_uri(base: str, model_name: str | None) -> str:
    """Append a ``?name=`` model-name hint to an artifact URI when given."""
    if not model_name:
        return base
    return f"{base}?{MODEL_NAME_PARAM}={quote(model_name, safe='')}"


def parse_tracking_uri(uri: str) -> LumlTarget:
    """Parse a ``luml://`` tracking URI into a :class:`LumlTarget`.

    Raises ``ValueError`` for non-``luml://`` schemes or for a sync-eligible URI
    that is missing the orbit id.
    """
    parsed = urlparse(uri)
    if parsed.scheme != LUML_SCHEME:
        raise ValueError(
            f"Expected a 'luml://' tracking URI, got scheme {parsed.scheme!r}"
        )
    netloc = parsed.netloc
    path = parsed.path.strip("/")

    if netloc == LOCAL_HOST:
        return LumlTarget(org=None, orbit=None, local_only=True)

    if not netloc:
        raise ValueError(
            "luml tracking URI is missing the organization id "
            "(expected 'luml://<org>/<orbit>' or 'luml://local')"
        )

    segments = [s for s in path.split("/") if s]
    if not segments:
        raise ValueError(
            f"luml tracking URI {uri!r} is missing the orbit id "
            "(expected 'luml://<org>/<orbit>')"
        )

    orbit = segments[0]
    return LumlTarget(org=netloc, orbit=orbit, local_only=False)


def parse_artifact_uri(uri: str) -> LumlArtifactLocation:
    """Parse a per-run artifact URI written by the tracking store.

    Expected layouts:
    * sync-eligible: ``luml://<org>/<orbit>/runs/<run_id>/artifacts``
    * local-only:    ``luml://local/runs/<run_id>/artifacts``

    Raises ``ValueError`` if the URI is malformed.
    """
    parsed = urlparse(uri)
    if parsed.scheme != LUML_SCHEME:
        raise ValueError(
            f"Expected a 'luml://' artifact URI, got scheme {parsed.scheme!r}"
        )
    netloc = parsed.netloc
    segments = [s for s in parsed.path.split("/") if s]
    model_name = parse_qs(parsed.query).get(MODEL_NAME_PARAM, [None])[0]

    if netloc == LOCAL_HOST:
        target = LumlTarget(org=None, orbit=None, local_only=True)
        # path is /runs/<run_id>/artifacts
        run_id = _extract_run_id(segments, after_offset=0, uri=uri)
        return LumlArtifactLocation(target=target, run_id=run_id, model_name=model_name)

    if not netloc:
        raise ValueError(f"luml artifact URI {uri!r} is missing the organization id")

    if len(segments) < 1:
        raise ValueError(f"luml artifact URI {uri!r} is missing the orbit id")

    orbit = segments[0]
    run_id = _extract_run_id(segments, after_offset=1, uri=uri)
    return LumlArtifactLocation(
        target=LumlTarget(org=netloc, orbit=orbit, local_only=False),
        run_id=run_id,
        model_name=model_name,
    )


def _extract_run_id(segments: list[str], after_offset: int, uri: str) -> str:
    """Read ``runs/<run_id>/artifacts`` starting at ``segments[after_offset]``."""
    tail = segments[after_offset:]
    if len(tail) < 3 or tail[0] != RUNS_SEGMENT or tail[2] != ARTIFACTS_SEGMENT:
        raise ValueError(
            f"luml artifact URI {uri!r} must end in '/runs/<run_id>/artifacts'"
        )
    run_id = tail[1]
    if not run_id:
        raise ValueError(f"luml artifact URI {uri!r} is missing the run id")
    return run_id
