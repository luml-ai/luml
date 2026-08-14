"""Native outputs: staged locally by the kernel, published by the daemon.

`model`, `dataset` and `experiment` outputs are serialized into the flow's own
value store exactly like an `asset` — a fork, a cold rerun and an offline
consumer all need a local byte source, and none of them can wait on a network.
Publishing happens afterwards and here, from those staged bytes: a queue whose
every state is a journal line, drained whenever the daemon is asked to do
something and retried the next time if the network was not there.

Three rules keep it honest. Only a **succeeded** materialization enqueues — a
failure has nothing to publish. A **memo hit** enqueues nothing either: it
produced no new bytes, so it reuses the reference logged by the run it hit. And
a run **never fails because an upload did**: the queue sits downstream of the
record, so an upload that cannot happen stays a fact in the journal until it
can.
"""

import asyncio
import contextlib
import io
import json
import re
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lumlflow.flow.errors import FlowError
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.index import UploadRow
from lumlflow.flow.store.models import (
    LumlRef,
    OutputRecord,
    UploadRecorded,
    UploadState,
    UploadStateChanged,
)

NATIVE_TYPES = frozenset({"model", "dataset", "experiment"})
SYSTEM_ACTOR = "system"
MANIFEST_MEMBER = "manifest.json"
_CONTENT_HASH = re.compile(r"\b[0-9a-f]{64}\b")


@dataclass(frozen=True)
class UploadRequest:
    """What the platform is handed: names a reader would recognise, and bytes."""

    flow: str
    slug: str
    output: str
    kind: str
    asset_type: str
    path: Path
    content_hash: str
    size: int


class Uploader(Protocol):
    async def upload(self, request: UploadRequest) -> LumlRef: ...


@dataclass(frozen=True)
class Published:
    """One output's standing with the platform, in words a surface can print."""

    slug: str
    output: str
    state: str
    reference: LumlRef | None = None
    detail: str | None = None


@dataclass(frozen=True)
class _Staged:
    """The bytes a queue entry points at, and what the cell declared them to be."""

    slug: str
    record: OutputRecord
    asset_type: str


class Uploads:
    """One flow's queue. The `uploader` is injected at the process edge — an
    object graph that reaches the network because nobody said otherwise is the
    wrong default, and without one every entry simply stays queued, which is
    the same state an offline daemon is in."""

    def __init__(
        self, store: FlowStore, *, flow: str, uploader: Uploader | None = None
    ) -> None:
        self._store = store
        self._flow = flow
        self._uploader = uploader
        # Enqueueing walks materializations forward from here. The queue table
        # holds what is still owed, so a cursor that only moves ahead loses
        # nothing — and a daemon starting at 0 sweeps the history once, which is
        # how a run whose upload was interrupted by a crash is picked back up.
        self._scanned = 0
        self._lock = asyncio.Lock()
        self._draining: asyncio.Task[None] | None = None

    @property
    def draining(self) -> "asyncio.Task[None] | None":
        """The background drain, while one is in flight."""
        return self._draining

    def sync(self, *, actor: str = SYSTEM_ACTOR) -> list[Published]:
        """Journal what the runs since the last look left to publish, and start
        publishing it. The op that called this does not wait on a network."""
        queued = self._enqueue(actor=actor)
        if self._uploader is not None and self._store.index.uploads(pending=True):
            self._start_draining(actor=actor)
        return queued

    async def drain(self, *, actor: str = SYSTEM_ACTOR) -> list[Published]:
        """Attempt every entry the queue still owes, one at a time.

        Entries that failed before are retried: "the network came back" is not
        an event anything reports, so every drain is the retry.
        """
        if self._uploader is None:
            return []
        async with self._lock:
            return [
                await self._publish(entry, self._uploader, actor=actor)
                for entry in self._store.index.uploads(pending=True)
            ]

    async def promote(
        self,
        mat_id: str,
        output: str,
        *,
        actor: str = "user",
        intent: str | None = None,
    ) -> Published:
        """Publish an output whose cell never declared it native.

        The bytes are already staged, so promoting is enqueueing plus the one
        attempt the caller waits on — it asked for this output, and the answer
        it wants is whether this one landed.
        """
        staged = self._locate(mat_id, output)
        if staged is None:
            raise FlowError(f"`{output}` has no stored value to publish")
        slug = staged.slug
        if staged.record.luml_ref is not None:
            return Published(slug, output, "uploaded", reference=staged.record.luml_ref)
        if not self._queued(mat_id, output):
            self._store.commit(
                [UploadStateChanged(mat_id=mat_id, output=output, state="queued")],
                intent=intent or f"promoting {slug}.{output}",
                actor=actor,
            )
        # This entry's own answer, not a scan over everything the queue owes:
        # two runs of one cell share a slug and an output name, so a match on
        # those would hand back another materialization's artifact. Only the
        # attempt knows why the platform said no, and "failed" without a reason
        # is not an answer, so the queue is read back only when none was made.
        attempted = await self._publish_one(mat_id, output, actor=actor)
        return (
            attempted
            if attempted is not None
            else self._published(mat_id, output, slug)
        )

    async def close(self) -> None:
        """Let go of a drain in flight. Whatever it had not reached is still
        queued in the journal, which is where the next daemon picks it up."""
        draining = self._draining
        if draining is None or draining.done():
            return
        draining.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await draining

    def _enqueue(self, *, actor: str) -> list[Published]:
        index = self._store.index
        known = {(row.mat_id, row.output) for row in index.uploads()}
        found: list[tuple[str, str, str]] = []
        scanned = self._scanned
        for mat in index.materializations_since(self._scanned):
            scanned = max(scanned, mat.finished_step or mat.started_step)
            version = index.version(mat.version_id)
            if version is None:
                continue
            for output, record in sorted(mat.outputs.items()):
                spec = version.manifest.produces.get(output)
                if spec is None or spec.type not in NATIVE_TYPES:
                    continue
                # No bytes, no upload: a declared `persist: False` output was
                # never kept, and one already published has its reference.
                if record.value_ref is None or record.luml_ref is not None:
                    continue
                if (mat.mat_id, output) not in known:
                    found.append((mat.mat_id, output, version.slug))
        self._scanned = scanned
        if not found:
            return []
        self._store.commit(
            [
                UploadStateChanged(mat_id=mat_id, output=output, state="queued")
                for mat_id, output, _ in found
            ],
            intent=_queued_intent(found),
            actor=actor,
        )
        return [Published(slug, output, "queued") for _, output, slug in found]

    def _start_draining(self, *, actor: str) -> None:
        if self._draining is not None and not self._draining.done():
            return
        self._draining = asyncio.create_task(self._drain_quietly(actor=actor))

    async def _drain_quietly(self, *, actor: str) -> None:
        """The background drain. Nothing awaits it, so nothing may raise out of
        it — a publish that fails is already recorded as one.

        It goes round again while entries it has not tried yet keep arriving: a
        run that queues an output while a slow upload holds the drain asked for
        that output to be published, and `sync` will not start a second drain
        over it. Entries that were tried and failed stay queued for the next
        drain rather than being retried in a loop nothing is waiting on.
        """
        with contextlib.suppress(Exception):
            tried: set[tuple[str, str]] = set()
            while True:
                waiting = {
                    (entry.mat_id, entry.output)
                    for entry in self._store.index.uploads(pending=True)
                }
                if waiting <= tried:
                    return
                tried |= waiting
                await self.drain(actor=actor)

    async def _publish_one(
        self, mat_id: str, output: str, *, actor: str
    ) -> "Published | None":
        """Attempt exactly one queued output. `None` if there was nothing to
        attempt — no platform to attempt it against, or no entry owed."""
        if self._uploader is None:
            return None
        async with self._lock:
            entry = next(
                (
                    row
                    for row in self._store.index.uploads(pending=True)
                    if row.mat_id == mat_id and row.output == output
                ),
                None,
            )
            if entry is None:
                return None
            return await self._publish(entry, self._uploader, actor=actor)

    async def _publish(
        self, entry: UploadRow, uploader: Uploader, *, actor: str
    ) -> Published:
        staged = self._locate(entry.mat_id, entry.output)
        if staged is None:
            # The record the entry names is gone, so there is nothing to send.
            # The entry stays owed rather than being dropped: only the value
            # coming back could publish it, and forgetting it was owed would
            # lose the one fact left about it.
            self._commit_state(entry, "failed", entry.attempts, actor=actor)
            return Published("", entry.output, "failed", detail="the value is gone")
        slug, record = staged.slug, staged.record
        self._commit_state(entry, "uploading", entry.attempts, actor=actor, slug=slug)
        request = UploadRequest(
            flow=self._flow,
            slug=slug,
            output=entry.output,
            kind=record.kind,
            asset_type=staged.asset_type,
            path=self._store.values.path(str(record.value_ref)),
            content_hash=record.content_hash,
            size=record.size,
        )
        try:
            reference = await uploader.upload(request)
        except Exception as failure:
            # Every failure lands the same way: offline, unauthorised, or the
            # platform saying no. The queue is what carries it, not the caller.
            self._commit_state(
                entry, "failed", entry.attempts + 1, actor=actor, slug=slug
            )
            return Published(slug, entry.output, "failed", detail=_reason(failure))
        self._store.commit(
            [UploadRecorded(mat_id=entry.mat_id, output=entry.output, ref=reference)],
            intent=f"published {slug}.{entry.output}",
            actor=actor,
        )
        return Published(slug, entry.output, "uploaded", reference=reference)

    def _commit_state(
        self,
        entry: UploadRow,
        state: UploadState,
        attempts: int,
        *,
        actor: str,
        slug: str | None = None,
    ) -> None:
        named = f"{slug}.{entry.output}" if slug else entry.output
        intent = (
            f"uploading {named}" if state == "uploading" else f"{named} did not upload"
        )
        self._store.commit(
            [
                UploadStateChanged(
                    mat_id=entry.mat_id,
                    output=entry.output,
                    state=state,
                    attempts=attempts,
                )
            ],
            intent=intent,
            actor=actor,
        )

    def _locate(self, mat_id: str, output: str) -> "_Staged | None":
        """What a queue entry names, if the record and its bytes still stand."""
        mat = self._store.index.materialization(mat_id)
        record = mat.outputs.get(output) if mat is not None else None
        if mat is None or record is None or record.value_ref is None:
            return None
        version = self._store.index.version(mat.version_id)
        if version is None:
            return None
        spec = version.manifest.produces.get(output)
        return _Staged(
            slug=version.slug,
            record=record,
            asset_type=spec.type if spec is not None else "asset",
        )

    def _queued(self, mat_id: str, output: str) -> bool:
        return any(
            row.mat_id == mat_id and row.output == output
            for row in self._store.index.uploads(pending=True)
        )

    def _published(self, mat_id: str, output: str, slug: str) -> Published:
        staged = self._locate(mat_id, output)
        reference = staged.record.luml_ref if staged is not None else None
        if reference is not None:
            return Published(slug, output, "uploaded", reference=reference)
        entry = next(
            (
                row
                for row in self._store.index.uploads(pending=True)
                if row.mat_id == mat_id and row.output == output
            ),
            None,
        )
        return Published(slug, output, entry.state if entry else "queued")


class LumlUploader:
    """The platform, reached through the SDK.

    The client is built per upload rather than kept: credentials and the
    default collection are the user's to change while the daemon runs, and one
    cached across that would keep failing for a reason already fixed.
    """

    async def upload(self, request: UploadRequest) -> LumlRef:
        return await asyncio.to_thread(self._upload, request)

    def _upload(self, request: UploadRequest) -> LumlRef:
        from luml_api._client import LumlClient

        from lumlflow.handlers.auth import AuthHandler
        from lumlflow.settings import get_config

        api_key = AuthHandler().get_stored_credentials().api_key
        if not api_key:
            raise FlowError(
                "no luml API key is configured, so nothing can be published yet"
            )
        client = LumlClient(base_url=get_config().LUML_BASE_URL, api_key=api_key)
        with tempfile.TemporaryDirectory() as staging:
            artifact = client.artifacts.upload(
                str(bundle(request, Path(staging))),
                name=f"{request.slug}.{request.output}",
                description=f"{request.asset_type} from the `{request.flow}` flow",
                tags=[request.flow, request.asset_type, request.kind],
            )
        return LumlRef(
            collection=artifact.collection_id,
            artifact_id=artifact.id,
            version=artifact.unique_identifier,
            digest=artifact.file_hash,
        )


def bundle(request: UploadRequest, into: Path) -> Path:
    """Pack a staged value the way the platform takes one.

    The store keeps a value as a bare content-addressed blob — no extension, a
    name that is a hash. An artifact is an archive carrying a manifest beside
    its payload, filed under a name a reader recognises, so publishing packs
    the blob rather than handing over its path. The bytes are untouched; what
    is added is the description of what they are.
    """
    named = f"{request.slug}_{request.output}"
    packed = into / f"{named}.tar"
    manifest = json.dumps(
        {
            "variant": "flow_output",
            "name": f"{request.slug}.{request.output}",
            "description": f"{request.asset_type} from the `{request.flow}` flow",
            "producer_name": "lumlflow",
            "producer_tags": [f"lumlflow::{request.asset_type}:v1"],
            "inputs": [],
            "outputs": [{"name": request.output, "content_type": request.kind}],
        },
        indent=2,
    ).encode("utf-8")
    with tarfile.open(packed, "w") as archive:
        entry = tarfile.TarInfo(MANIFEST_MEMBER)
        entry.size = len(manifest)
        archive.addfile(entry, io.BytesIO(manifest))
        archive.add(request.path, arcname=named)
    return packed


def _reason(failure: Exception) -> str:
    """Why the platform said no, in words a reader may see.

    The path handed to the SDK ends in a content hash, so a failure that names
    the file it could not read would print one — and hashes never leave `--json`.
    """
    spoken = _CONTENT_HASH.sub("…", str(failure)).strip()
    return spoken or type(failure).__name__


def _queued_intent(found: list[tuple[str, str, str]]) -> str:
    if len(found) == 1:
        _, output, slug = found[0]
        return f"queued {slug}.{output} for upload"
    return f"queued {len(found)} outputs for upload"
