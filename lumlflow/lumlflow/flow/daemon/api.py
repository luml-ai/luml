"""The daemon API: the one door every CLI, MCP and browser action goes through.

Methods take a params dict and return JSON — no store handles, no uids, no
content hashes. Cells are addressed by slug and branches by name here, because
everything downstream renders what this returns.

Verdicts arrive computed. Staleness, preflight costs and run outcomes are the
runtime's facts, derived here from what the store recorded, so no surface has
to re-derive them and none can disagree.
"""

import os
import shutil
from collections.abc import Awaitable, Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args

from lumlflow.flow.daemon import envs, handoff, harnesses, queries, workspace
from lumlflow.flow.daemon.hub import FlowSession, Hub
from lumlflow.flow.daemon.projections import Projection
from lumlflow.flow.daemon.workspace import FlowRef
from lumlflow.flow.dsl import loader, portable, scaffold
from lumlflow.flow.dsl.accept import PLACEHOLDER_SLUG, AcceptedCell, Batch
from lumlflow.flow.dsl.portable import PortableCell
from lumlflow.flow.errors import (
    EditConflict,
    FlowError,
    ValueNotStored,
)
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.scheduler.planner import Preflight, reading_order
from lumlflow.flow.scheduler.queue import RunOutcome
from lumlflow.flow.store import gc
from lumlflow.flow.store.flowstore import FlowStore, store_dir
from lumlflow.flow.store.index import VersionRow
from lumlflow.flow.store.models import AgentBegin, AgentEnd, OutputRecord, Reactivity

Method = Callable[[dict[str, Any]], Awaitable[Any]]
AttachmentCheck = Callable[[str], dict[str, Any]]

# One pass names every cell an imported file holds, a second binds the
# references the first could not see yet. Nothing a third would find.
_IMPORT_PASSES = 2


class Api:
    def __init__(
        self,
        hub: Hub,
        *,
        directory: Path | None = None,
        stop: Callable[[], None] | None = None,
        attachments: AttachmentCheck | None = None,
        instance_id: str = "",
        harness_service: harnesses.HarnessService | None = None,
    ) -> None:
        self.hub = hub
        self.directory = (directory or Path.cwd()).resolve()
        self.instance_id = instance_id
        # Where the browser reaches this workspace, once the daemon has bound
        # it. A process serving only the socket leaves it None rather than
        # naming a port nothing answers on.
        self.web: str | None = None
        self._stop = stop
        self._attachments = attachments
        self._harnesses = harness_service or harnesses.HarnessService()
        self.methods: dict[str, Method] = {
            "ping": self.ping,
            "status": self.status,
            "gc.sweep": self.gc_sweep,
            "context": self.context,
            "tree": self.tree,
            "graph": self.graph,
            "diff": self.diff,
            "workspace.list": self.workspace_list,
            "agents.harnesses": self.agents_harnesses,
            "agents.setup": self.agents_setup,
            "agents.remove": self.agents_remove,
            "flow.init": self.flow_init,
            "flow.open": self.flow_open,
            "flow.checkout": self.flow_checkout,
            "flow.delete": self.flow_delete,
            "flow.rename": self.flow_rename,
            "flow.duplicate": self.flow_duplicate,
            "cells.list": self.cells_list,
            "cells.show": self.cells_show,
            "cells.logs": self.cells_logs,
            "cells.new": self.cells_new,
            "cells.reorder": self.cells_reorder,
            "cells.edit": self.cells_edit,
            "cells.delete": self.cells_delete,
            "cells.eager": self.cells_eager,
            "asset.preview": self.asset_preview,
            "asset.page": self.asset_page,
            "asset.download": self.asset_download,
            "export": self.export,
            "import": self.import_cells,
            "fork": self.fork,
            "switch": self.switch,
            "rewind": self.rewind,
            "checkpoint": self.checkpoint,
            "adopt": self.adopt,
            "archive": self.archive,
            "rename": self.rename,
            "agent.begin": self.agent_begin,
            "agent.end": self.agent_end,
            "agent.payload": self.agent_payload,
            "settings.set": self.settings_set,
            "env.status": self.env_status,
            "run": self.run,
            "eval": self.eval,
            "preflight": self.preflight,
            "cancel": self.cancel,
            "kernel.restart": self.kernel_restart,
            "journal.since": self.journal_since,
            "shutdown.if_idle": self.shutdown_if_idle,
            "shutdown": self.shutdown,
        }

    async def ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liveness, cheap enough to ask on every verb — and where the UI is.

        `running` is how `lumlflow ui` decides whether the process holding this
        workspace may be restarted under it: nothing in flight, nothing lost.
        """
        return {
            "workspace": str(self.directory),
            "pid": os.getpid(),
            "instance_id": self.instance_id,
            "web": self.web,
            "running": self.hub.running(),
        }

    async def status(self, params: dict[str, Any]) -> dict[str, Any]:
        """The workspace, its flows, and what is unsynced in each."""
        directory = self._directory(params)
        interpreter = envs.describe(directory)
        refs = (
            [self.resolve(_flow_name(params), directory=directory)]
            if params.get("flow")
            else workspace.find_flows(directory)
        )
        return {
            "workspace": str(directory),
            "pid": os.getpid(),
            "python": {
                "path": str(interpreter.python),
                "source": interpreter.source,
            },
            "flows": [
                await self._flow_status(ref, actor=_actor(params)) for ref in refs
            ],
        }

    async def gc_sweep(self, params: dict[str, Any]) -> dict[str, Any]:
        directory = self._directory(params)
        flows: list[dict[str, Any]] = []
        for ref in workspace.find_flows(directory):
            session = self.hub.attached(ref.path)
            if session is None and not store_dir(ref.path).is_dir():
                continue
            store = session.store if session is not None else FlowStore.open(ref.path)
            try:
                report = gc.sweep(store)
            finally:
                if session is None:
                    store.close()
            flows.append(
                {
                    "flow": ref.name,
                    "path": ref.address,
                    "collected": report.collected,
                    "freed_bytes": report.freed_bytes,
                    "kept": report.kept,
                }
            )
        return {
            "directory": str(directory),
            "flows": flows,
            "collected": sum(int(flow["collected"]) for flow in flows),
            "freed_bytes": sum(int(flow["freed_bytes"]) for flow in flows),
            "kept": sum(int(flow["kept"]) for flow in flows),
        }

    async def context(self, params: dict[str, Any]) -> dict[str, Any]:
        """The orientation brief: where you are, what is unsynced, what broke."""
        session, branch = await self._read(params)
        interpreter = envs.describe(session.workspace_dir)
        return queries.context(session, branch) | {
            "python": {
                "path": str(interpreter.python),
                "source": interpreter.source,
            }
        }

    async def tree(self, params: dict[str, Any]) -> dict[str, Any]:
        session, _ = await self._read(params)
        return queries.tree(session)

    async def graph(self, params: dict[str, Any]) -> dict[str, Any]:
        session, branch = await self._read(params)
        around = params.get("around")
        return queries.graph(
            session,
            branch,
            around=str(around) if around else None,
            depth=_number(
                params.get("depth") or queries.DEFAULT_DEPTH, int, name="depth"
            ),
        )

    async def diff(self, params: dict[str, Any]) -> dict[str, Any]:
        session, _ = await self._read(params)
        return queries.diff(
            session, [str(name) for name in params.get("branches") or []]
        )

    async def workspace_list(self, params: dict[str, Any]) -> dict[str, Any]:
        directory = self._directory(params)
        return {
            "directory": str(directory),
            "flows": [
                {
                    "name": ref.name,
                    "path": ref.address,
                    "relative_path": ref.relpath,
                }
                for ref in workspace.find_flows(directory)
            ],
        }

    def sync_agents(self) -> list[dict[str, Any]]:
        return self._harnesses.sync()

    async def agents_harnesses(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"harnesses": self._harnesses.list_harnesses()}

    async def agents_setup(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._harnesses.setup(
            str(params.get("harness") or params.get("id") or ""),
            consent=bool(params.get("consent")),
        )

    async def agents_remove(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._harnesses.remove(
            str(params.get("harness") or params.get("id") or "")
        )

    async def flow_init(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "")
        session = self.hub.init_flow(self._directory(params), name)
        return await self._flow_brief(session) | {
            "warnings": list(session.store.warnings)
        }

    async def flow_open(self, params: dict[str, Any]) -> dict[str, Any]:
        """Open a flow, checking it out unless the caller keeps no worktree.

        The first non-MCP open is a full checkout: bind the root to a branch
        and project its slice, never a bare bind. `worktree: false` is the
        MCP path — cells live in the store there, and materializing a checkout
        under a session that only calls the API would invent a file plane
        nobody asked for.
        """
        ref = self.resolve(_flow_name(params), directory=self._directory(params))
        session = self.hub.open(ref, actor=_actor(params))
        session.experiment_states.clear()
        if params.get("worktree", True):
            await self.hub.quiesce(session, actor=_actor(params))
            if session.worktree.bound() is None:
                session.worktree.checkout(actor=_actor(params))
        return await self._flow_status(ref, actor=_actor(params))

    async def flow_checkout(self, params: dict[str, Any]) -> dict[str, Any]:
        """Bind the flow root to a branch and project it — what `init` adds."""
        actor = _actor(params)
        session = self._session(params, actor=actor)
        await self.hub.quiesce(session, actor=actor)
        projection = session.worktree.checkout(
            params.get("branch"),
            actor=actor,
            intent=params.get("intent"),
        )
        return await self._flow_brief(session) | _projection(projection)

    async def flow_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        ref = self.resolve(_flow_name(params), directory=self._directory(params))
        await self.hub.delete_flow(ref)
        return {"deleted": ref.name, "path": ref.address}

    async def flow_rename(self, params: dict[str, Any]) -> dict[str, Any]:
        """Rename the flow's directory. Its store, history and cells move with it."""
        ref = self.resolve(_flow_name(params), directory=self._directory(params))
        renamed = await self.hub.rename_flow(ref, str(params.get("name") or ""))
        return {"renamed": renamed.name, "path": renamed.address, "from": ref.address}

    async def flow_duplicate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Copy a flow under a new name. Its store, cells and history come with it.

        Quiesced first, so the copy carries whatever the source's files hold
        right now rather than what its store last reconciled.
        """
        actor = _actor(params)
        session = self._session(params, actor=actor)
        await self.hub.quiesce(session, actor=actor)
        duplicated = await self.hub.duplicate_flow(
            session.ref, str(params.get("name") or "")
        )
        return {"flow": duplicated.name, "path": duplicated.address}

    async def cells_list(self, params: dict[str, Any]) -> dict[str, Any]:
        session, branch = await self._read(params)
        return queries.cells(
            session,
            branch,
            unsynced=bool(params.get("unsynced")),
            include_uid=True,
        )

    async def cells_show(self, params: dict[str, Any]) -> dict[str, Any]:
        session, branch = await self._read(params)
        return queries.show(session, branch, str(params.get("slug") or ""))

    async def cells_logs(self, params: dict[str, Any]) -> dict[str, Any]:
        """The console of the run this branch observed — that one, not the newest.

        Kept off `cells show`, which agents read whole: a run's capped artifact
        is large next to a cell's declarations, and only a reader who opened
        the logs asked for it.
        """
        session, branch = await self._read(params)
        return queries.logs(session, branch, str(params.get("slug") or ""))

    async def cells_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        """Drop the cell from this branch. Every other branch keeps its own."""
        session, branch = await self._read(params)
        actor = _actor(params)
        result = session.store.branches.delete(
            str(params.get("slug") or ""),
            branch=branch,
            actor=actor,
            intent=params.get("intent"),
        )
        if result.dangling:
            session.acceptance.reaccept(result.dangling, branch=branch, actor=actor)
        session.store.save_manifest()
        return {
            "slug": result.slug,
            "branch": branch,
            "dangling": result.dangling,
        } | _projection(self._reproject(session, branch))

    async def cells_eager(self, params: dict[str, Any]) -> dict[str, Any]:
        """Opt one cell in or out of eager materialization.

        Eager is per-asset by design: reactivity's default already runs a cheap
        closure without being asked, and the opt-in is for the one cell whose
        cost is worth paying on every change. It lives in `flow.yaml` beside the
        threshold it overrides, keyed by uid so renaming the cell keeps it.
        """
        session, branch = await self._read(params)
        here = queries.read(session, branch)
        slug = str(params.get("slug") or "")
        uid = here.uid_of(slug)
        on = bool(params.get("eager"))
        settings = session.store.manifest.settings
        kept = [other for other in settings.eager if other != uid]
        settings.eager = [*kept, uid] if on else kept
        session.store.save_manifest()
        # Ticking it is not a run, but it is the answer to "would this refresh
        # itself" changing — so if the cell is already unsynced, it refreshes now.
        session.reactor.arm()
        return {"flow": session.ref.name, "branch": branch, "slug": slug, "eager": on}

    async def cells_new(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add a cell. Never blocks on a name.

        An unnamed cell is scaffolded under a placeholder slug and flagged
        softly; once its class is written the flag carries the derived name to
        rename it to. The version is written to the store, so this is valid
        whether or not the branch is checked out.

        A name another cell already answers to is moved aside and flagged — no
        filesystem refuses a collision on this path, and adding a cell is never
        an edit to the one that was there.
        """
        session, branch = await self._read(params)
        raw_slug = params.get("slug")
        if raw_slug is None:
            slug = _placeholder_slug(session)
        else:
            slug = portable.cell_name(str(raw_slug))
        output_mode = params.get("outputs")
        if output_mode not in (None, "all"):
            raise FlowError("`outputs` must be `all` when given")
        provided_source = params.get("source")
        anchor_name = str(params.get("after") or params.get("anchor") or "")
        if not anchor_name and provided_source:
            copied_uid = loader.parse(str(provided_source)).uid
            branch_id = session.store.branches.get(branch).branch_id
            original = session.store.index.slice_versions(branch_id).get(
                copied_uid or ""
            )
            if original is not None:
                anchor_name = original.slug
        anchor = queries.head(session, branch, anchor_name) if anchor_name else None
        uid = new_ulid() if anchor is not None else None
        order_key = (
            session.store.order_after(anchor.uid) if anchor is not None else None
        )
        source = provided_source or _scaffold(session, params, slug=slug, branch=branch)
        previous_order = session.store.manifest.order
        if order_key is not None and uid is not None:
            order = dict(previous_order or {})
            order[uid] = order_key
            session.store.manifest.order = order
        try:
            accepted = session.acceptance.accept_source(
                slug,
                str(source),
                branch=branch,
                actor=_actor(params),
                intent=params.get("intent") or f"added {slug}",
                uid=uid,
                fresh=True,
            )
        except BaseException:
            session.store.manifest.order = previous_order
            raise
        return self._edited(session, accepted, branch=branch)

    async def cells_reorder(self, params: dict[str, Any]) -> dict[str, Any]:
        """Move one flow-wide presentation key, constrained by this lane's wiring."""
        session, branch = await self._read(params)
        before = str(params.get("before") or "").strip()
        after = str(params.get("after") or "").strip()
        if bool(before) == bool(after):
            raise FlowError("moving a cell needs exactly one of `before` or `after`")

        moved = queries.head(session, branch, str(params.get("slug") or ""))
        neighbour = queries.head(session, branch, before or after)
        if moved.uid == neighbour.uid:
            raise FlowError(f"`{moved.slug}` cannot be moved beside itself")

        if before:
            order_key = session.store.order_before(
                neighbour.uid, excluding_uid=moved.uid
            )
        else:
            order_key = session.store.order_after(
                neighbour.uid, excluding_uid=moved.uid
            )
        branch_id = session.store.branches.get(branch).branch_id
        versions = session.store.index.slice_versions(branch_id)
        _validate_reorder_topology(
            versions,
            moved,
            Decimal(order_key),
            session.store.effective_order(),
            branch,
        )

        previous_order = session.store.manifest.order
        session.store.manifest.order = {
            **(previous_order or {}),
            moved.uid: order_key,
        }
        try:
            session.store.save_manifest()
        except BaseException:
            session.store.manifest.order = previous_order
            raise
        self.hub.push_state(session, "order_changed")
        return {
            "slug": moved.slug,
            "uid": moved.uid,
            "branch": branch,
            "order": order_key,
        }

    async def cells_edit(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write an edit the daemon was handed, under per-cell optimistic locking.

        `base` is the `definition_hash` the editor started from. A head that
        moved past it is not overwritten silently — the caller is handed both
        versions and picks: overwrite, or fork the edit onto a branch of its
        own.
        """
        slug = str(params.get("slug") or "")
        source = str(params.get("source") or "")
        if not source.strip():
            raise FlowError(f"`{slug}` cannot be edited with empty source")
        session = self._session(params, actor=_actor(params))
        await self.hub.quiesce(session, actor=_actor(params))
        branch = _branch(session, params)
        head = queries.head(session, branch, slug)
        base = params.get("base")
        if base and base != head.definition_hash and not params.get("force"):
            raise EditConflict(
                f"`{slug}` has a newer version than this edit started from. "
                "overwrite it, or save this edit to a new lane",
                slug=slug,
                branch=branch,
                base=str(base),
                head=head.definition_hash,
                head_author=head.author,
            )
        accepted = session.acceptance.accept_source(
            slug,
            source,
            branch=branch,
            actor=_actor(params),
            intent=params.get("intent") or f"edited {slug}",
            uid=head.uid,
        )
        return self._edited(
            session,
            accepted,
            branch=branch,
        )

    async def asset_preview(self, params: dict[str, Any]) -> dict[str, Any]:
        """An output as the store holds it — verdict, kind, and stored preview."""
        session, branch = await self._read(params)
        return queries.asset(session, branch, _target(params))

    async def asset_page(self, params: dict[str, Any]) -> dict[str, Any]:
        """Read into a value. This is the gesture that starts a kernel."""
        session, _, slug, output, record = await self.stored_output(params)
        value_ref = record.value_ref
        assert value_ref is not None
        page = await session.kernel.page(
            value_ref, record.kind, dict(params.get("query") or {})
        )
        return {"slug": slug, "output": output, "kind": record.kind, "page": page}

    async def asset_download(self, params: dict[str, Any]) -> dict[str, Any]:
        """Copy a stored value out of the flow, under a name of the caller's."""
        session, _, slug, output, record = await self.stored_output(params)
        destination = Path(str(params.get("to") or "")).expanduser()
        if not destination.is_absolute():
            raise FlowError("`to` must be an absolute path for `asset.download`")
        if destination.is_dir():
            destination = destination / f"{slug}.{output}"
        force = params.get("force") is True
        if (destination.exists() or destination.is_symlink()) and not force:
            raise FlowError(
                f"`{destination}` already exists. use `--force` to overwrite it"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        value_ref = record.value_ref
        assert value_ref is not None
        shutil.copyfile(session.store.values.path(value_ref), destination)
        return {
            "slug": slug,
            "output": output,
            "kind": record.kind,
            "size": record.size,
            "path": str(destination),
        }

    async def stored_output(
        self, params: dict[str, Any]
    ) -> tuple[FlowSession, str, str, str, OutputRecord]:
        session, branch = await self._read(params)
        here = queries.read(session, branch)
        slug, output, record = queries.locate(here, _target(params))
        if record is None or record.value_ref is None:
            raise ValueNotStored(_unstored(slug, output, record is not None))
        return session, branch, slug, output, record

    async def export(self, params: dict[str, Any]) -> dict[str, Any]:
        """A branch's cells as one file. A read: nothing is written anywhere."""
        session, branch = await self._read(params)
        return queries.export(session, branch)

    async def import_cells(self, params: dict[str, Any]) -> dict[str, Any]:
        """Read an exported file back into a branch, as one transaction.

        The cells land as versions, so this is valid whether or not the branch
        is checked out; where it is, the files follow. Identity comes out of the
        file — a cell this flow already knows is edited rather than duplicated,
        and one it does not is taken up under the identity it arrived with, so
        an export and its import name the same cells afterwards.
        """
        session, branch = await self._read(params)
        actor = _actor(params)
        carried = portable.read(str(params.get("source") or ""))
        _one_cell_per_identity(carried)
        batch = Batch()
        accepted = _accept_carried(session, carried, batch, branch=branch, actor=actor)
        if batch.ops:
            session.store.commit(
                batch.ops,
                intent=params.get("intent")
                or f"imported {portable.counted(len(carried))}",
                actor=actor,
                branch=session.store.branches.get(branch).branch_id,
            )
            session.store.save_manifest()
            rewire = sorted(
                {
                    uid
                    for accepted_cell in batch.accepted
                    for uid in accepted_cell.rewire
                }
            )
            if rewire:
                self._rewire(session, rewire, branch=branch, actor=actor)
        return {
            "flow": session.ref.name,
            "branch": branch,
            "cells": [{"slug": cell.slug, "flags": _flags(cell)} for cell in accepted],
        } | _projection(self._reproject(session, branch))

    async def fork(self, params: dict[str, Any]) -> dict[str, Any]:
        """A new branch off this one: one row, and no value is copied."""
        session, branch = await self._read(params)
        parent = str(params.get("from_branch") or branch)
        created = session.store.branches.fork(
            str(params.get("name") or ""),
            from_branch=parent,
            actor=_actor(params),
            intent=params.get("intent"),
        )
        parent_record = session.store.branches.get(parent)
        found = session.store.index.last_step_on(
            parent_record.branch_id, at_or_before=created.fork_step
        )
        return {
            "branch": created.name,
            "from_branch": parent,
            "forked_at_step": created.fork_step,
            "parent_step": created.fork_step if found is None else found,
            "cells": len(session.store.index.selections(created.branch_id)),
        }

    async def archive(self, params: dict[str, Any]) -> dict[str, Any]:
        session, branch = await self._read(params)
        archived = session.store.branches.archive(
            str(params.get("branch") or branch),
            actor=_actor(params),
            intent=params.get("intent"),
        )
        return {"branch": archived.name, "archived": archived.archived}

    async def rename(self, params: dict[str, Any]) -> dict[str, Any]:
        """Give a cell another name. References bind to identity, so this costs
        nothing: no consumer's definition moves, and no cache is lost.

        The version is re-accepted from the source the store holds, under the new
        name — the same path an agent's `mv` arrives on — and the consumers whose
        files still spell the old one are rewritten to match.
        """
        session, branch = await self._read(params)
        actor = _actor(params)
        old = portable.cell_name(str(params.get("slug") or "")).casefold()
        new = portable.cell_name(str(params.get("to") or ""))
        head = queries.head(session, branch, old)
        branch_id = session.store.branches.get(branch).branch_id
        canonical = new.casefold()
        if any(
            uid != head.uid and version.slug.casefold() == canonical
            for uid, version in session.store.index.slice_versions(branch_id).items()
        ):
            raise FlowError(f"a cell named `{canonical}` already exists on `{branch}`")
        accepted = session.acceptance.accept_source(
            new,
            session.store.objects.get(head.raw_source_ref).decode("utf-8"),
            branch=branch,
            actor=actor,
            intent=params.get("intent") or f"renamed {old} to {new}",
            # Named, not read off the source: a cell whose file never parsed
            # carries no uid line, and renaming it must move that cell rather
            # than mint a second one beside it.
            uid=head.uid,
        )
        rewired = self._rewire(session, accepted.rewire, branch=branch, actor=actor)
        return {
            "slug": accepted.slug,
            "renamed_from": old,
            "branch": branch,
            "rewired": rewired,
        } | _projection(self._reproject(session, branch))

    async def env_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """What the workspace pins, and which kernels are running behind it."""
        return await self._env()

    async def switch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check a branch out: rebind the worktree and project its slice."""
        actor = _actor(params)
        session = self._session(params, actor=actor)
        await self.hub.quiesce(session, actor=actor)
        projection = session.worktree.checkout(
            str(params.get("branch") or ""),
            actor=actor,
            intent=params.get("intent"),
        )
        return await self._flow_brief(session) | _projection(projection)

    async def rewind(self, params: dict[str, Any]) -> dict[str, Any]:
        """Restore a branch to a step. Instant, and the files follow."""
        actor = _actor(params)
        session = self._session(params, actor=actor)
        await self.hub.quiesce(session, actor=actor)
        branch = _branch(session, params)
        result = session.store.branches.rewind(
            branch,
            to_step=_number(params.get("to_step") or 0, int, name="to_step"),
            actor=actor,
            intent=params.get("intent"),
        )
        session.store.save_manifest()
        return (
            await self._flow_brief(session)
            | {
                "rewound_branch": result.branch,
                "to_step": result.to_step,
                "cells": len(result.selections),
            }
            | _projection(self._reproject(session, branch))
        )

    async def checkpoint(self, params: dict[str, Any]) -> dict[str, Any]:
        """Mark this point in a branch's history. Nothing is copied or frozen.

        The journal already records every change; what it cannot record on its
        own is that one of those points is the one to come back to. This
        journals that, and it becomes the branch's `checkpoint` in the brief.
        """
        session, branch = await self._read(params)
        intent = str(params.get("intent") or "").strip()
        if not intent:
            raise FlowError("a checkpoint needs a one-line intent")
        marked = session.store.branches.checkpoint(
            branch, actor=_actor(params), intent=intent
        )
        return {
            "branch": branch,
            "step": marked.step,
            "intent": marked.intent,
            "ts": marked.ts,
            "settled": marked.settled,
        }

    async def adopt(self, params: dict[str, Any]) -> dict[str, Any]:
        """Take one asset's version from another branch onto this one."""
        actor = _actor(params)
        session = self._session(params, actor=actor)
        await self.hub.quiesce(session, actor=actor)
        branch = _branch(session, params)
        force = bool(params.get("force"))
        result = session.store.branches.adopt(
            str(params.get("slug") or ""),
            from_branch=str(params.get("from_branch") or ""),
            to_branch=branch,
            force=force,
            actor=actor,
            intent=params.get("intent"),
        )
        reaccepted = session.acceptance.reaccept(
            uids=result.reaccept, branch=branch, actor=actor
        )
        rewired = self._rewire(session, result.rewire, branch=branch, actor=actor)
        landed_slug = reaccepted[0].slug if reaccepted else result.slug
        return {
            "slug": landed_slug,
            "branch": branch,
            "rebound": [accepted.slug for accepted in reaccepted] + rewired,
        } | _projection(self._reproject(session, branch))

    async def agent_begin(self, params: dict[str, Any]) -> dict[str, Any]:
        """Register an agent session for attribution until it ends.

        Detected, never wrapped: the journal entry is what the pair panel reads
        and what file-plane edits attribute to until it ends.

        `lease` says the caller's connection carries this session: it ends when
        that connection does, whether or not anybody got to say so. A caller
        that connects per call — every CLI verb — must not ask for one.
        """
        session = self._session(params)
        label = str(params.get("label") or params.get("actor") or "agent")
        actor = str(params.get("actor") or label)
        # Open the bracket over a settled file plane: edits made before the
        # session began belong to whoever was there before it.
        await self.hub.quiesce(session)
        session.store.commit(
            [AgentBegin(actor=actor, label=label)],
            intent=params.get("intent") or f"{label} started working",
            actor=actor,
        )
        return {
            "flow": session.ref.address,
            "actor": actor,
            "label": label,
            "leased": bool(params.get("lease")),
        }

    async def agent_end(self, params: dict[str, Any]) -> dict[str, Any]:
        """Close the bracket — and with it the transaction its edits group into."""
        actor = str(params.get("actor") or "")
        session = self._session(
            params,
            actor=actor if actor not in {"", "user"} else None,
        )
        sessions = session.store.index.agent_sessions()
        registered = next(
            (found for found in sessions if found.actor == actor),
            sessions[0] if actor in {"", "user"} and len(sessions) == 1 else None,
        )
        if registered is None:
            raise FlowError("no agent session is registered here")
        await self.hub.quiesce(session, tier="live", actor=registered.actor)
        session.store.commit(
            [AgentEnd(actor=registered.actor, label=registered.label)],
            intent=params.get("intent") or f"{registered.label} finished",
            actor=registered.actor,
        )
        return {
            "flow": session.ref.address,
            "actor": registered.actor,
            "label": registered.label,
        }

    async def agent_payload(self, params: dict[str, Any]) -> dict[str, Any]:
        """The stored context copied from one cell card."""
        session, branch = await self._read(params)
        return handoff.payload(
            session,
            branch=branch,
            slug=_named(params.get("slug")),
        )

    async def settings_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write the settings a surface renders into `flow.yaml`.

        Config, not history: these decide what the runtime does next, so they
        are journaled nowhere — the same reason `cells eager` is not a
        transaction. Anything absent from the call is left alone.
        """
        session = self._session(params, actor=_actor(params))
        settings = session.store.manifest.settings
        if params.get("reactivity") is not None:
            settings.reactivity = _one_of(
                params["reactivity"], get_args(Reactivity), "reactivity"
            )
        if params.get("eager_cost_threshold_s") is not None:
            settings.eager_cost_threshold_s = _number(
                params["eager_cost_threshold_s"],
                float,
                name="eager_cost_threshold_s",
            )
        session.store.save_manifest()
        # Turning reactivity on, or lifting the threshold, is a decision about
        # the cells that are unsynced right now — not only about the next edit.
        session.reactor.arm()
        return {
            "flow": session.ref.name,
            "settings": {
                "reactivity": settings.reactivity,
                "eager_cost_threshold_s": settings.eager_cost_threshold_s,
            },
        }

    async def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run a target's closure, or every leaf's closure when none is named.

        Forcing is what a surface offers when the recorded result is suspect —
        a cell that reads something the store does not hash — and it is never
        the default: it spends the whole closure's cost again on purpose.
        """
        session, branch = await self._read(params)
        target = _named(params.get("target"))
        if target is None:
            result = await self._run_leaves(session, branch, params)
        else:
            outcome = await session.queue.submit(
                target,
                branch=branch,
                actor=_actor(params),
                force=bool(params.get("force")),
            )
            result = _outcome(outcome)
        # A result the user paid for is what makes the cheap cells under it
        # affordable: running the expensive parent is the gesture that lets
        # reactivity take the plot below it.
        session.reactor.arm()
        return {"path": session.ref.address} | result

    async def _run_leaves(
        self, session: FlowSession, branch: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        targets = _leaves(session, branch)
        executed: list[str] = []
        cached: list[str] = []
        pruned: list[str] = []
        failures: list[str] = []
        unplanned: list[dict[str, str]] = []
        abandoned = False

        for target in targets:
            try:
                plan = session.planner.plan(target, branch=branch)
            except FlowError as failure:
                unplanned.append({"target": target, "error": str(failure)})
                continue
            if failures and any(step.slug in failures for step in plan.steps):
                continue
            try:
                outcome = await session.queue.submit(
                    target,
                    branch=branch,
                    actor=_actor(params),
                    force=bool(params.get("force")),
                )
            except FlowError as failure:
                unplanned.append({"target": target, "error": str(failure)})
                continue
            executed.extend(outcome.executed)
            cached.extend(outcome.cached)
            pruned.extend(outcome.pruned)
            if outcome.failed is not None:
                failures.append(outcome.failed)
            abandoned = abandoned or outcome.abandoned
            if outcome.abandoned:
                break

        return {
            "branch": branch,
            "target": ", ".join(targets),
            "targets": targets,
            "executed": list(dict.fromkeys(executed)),
            "cached": list(dict.fromkeys(cached)),
            "pruned": list(dict.fromkeys(pruned)),
            "failed": failures[0] if failures else None,
            "failures": list(dict.fromkeys(failures)),
            "unplanned": unplanned,
            "abandoned": abandoned,
        }

    async def eval(self, params: dict[str, Any]) -> dict[str, Any]:
        """Scratch code against a branch's values — a read, never a write.

        Names resolve to what this branch observed and hydrate as copies, so no
        version, materialization or journal line comes of it. Checking a branch
        out is not part of it either: any branch evaluates, including one whose
        files are nowhere.
        """
        session, branch = await self._read(params)
        here = queries.read(session, branch)
        result = await session.kernel.eval(
            queries.repl_names(session, here), str(params.get("code") or "")
        )
        return {"flow": session.ref.name, "branch": branch} | result

    async def preflight(self, params: dict[str, Any]) -> dict[str, Any]:
        """What a run would cost, for one target or for several at once.

        `targets` is what "rerun this branch" asks: one closure over every leaf
        rather than one preflight per leaf, so a shared ancestor is counted the
        once it will actually run.
        """
        session, branch = await self._read(params)
        targets = _targets(params)
        return _preflight(session.planner.preflight(*targets, branch=branch))

    async def cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        """Leave the run this branch is waiting on.

        Only the last branch to leave stops the execution: a sweep of twenty
        forks awaiting one training run is not cancelled by one of them
        walking away. The report says which happened rather than letting a
        surface claim the run stopped.
        """
        session = self._session(params, actor=_actor(params))
        branch = _branch(session, params)
        left = session.queue.abandon(branch)
        return {
            "branch": branch,
            "left": left.left,
            "stopped": left.stopped,
            "awaiting": left.awaiting,
        }

    async def kernel_restart(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params, actor=_actor(params))
        handshake = await session.kernel.restart()
        session.kernel_epoch_step = session.store.next_step
        session.reactor.arm()
        return {
            "flow": session.ref.name,
            "kernel": await _kernel(session, handshake),
        }

    async def journal_since(self, params: dict[str, Any]) -> dict[str, Any]:
        """Everything a client missed. The cursor is a step, not a timestamp.

        No quiesce: this reads what was recorded, and reconciling first would
        put an edit into the answer to a question about the past. A client that
        holds no cursor asks from 0 and gets the flow's whole history — which
        is what makes a reconnect indistinguishable from a first load.
        """
        session = self._session(params, actor=_actor(params))
        entries = [
            entry.model_dump(mode="json")
            for entry in session.store.journal.since(
                _number(params.get("cursor") or 0, int, name="cursor")
            )
        ]
        return {
            "flow": session.ref.name,
            "path": session.ref.address,
            "cursor": session.store.next_step - 1,
            "transactions": entries,
        }

    async def shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._stop is not None:
            self._stop()
        return {"stopping": True}

    async def shutdown_if_idle(self, params: dict[str, Any]) -> dict[str, Any]:
        """Stop a daemon a pipeline started only while nobody else needs it."""
        path = str(params.get("path") or "")
        attached = self._attachments(path) if self._attachments is not None else {}
        if any(attached.values()):
            return {"stopping": False, "attached": attached}
        if self._stop is not None:
            self._stop()
        return {"stopping": True, "attached": attached}

    def resolve(self, name: str | None, *, directory: Path | None = None) -> FlowRef:
        return workspace.select_flow(directory or self.directory, name=name)

    def _session(
        self,
        params: dict[str, Any],
        *,
        actor: str | None = None,
    ) -> FlowSession:
        ref = self.resolve(_flow_name(params), directory=self._directory(params))
        return self.hub.open(ref, actor=actor)

    def _directory(self, params: dict[str, Any]) -> Path:
        asked = params.get("directory")
        directory = Path(str(asked)).expanduser().resolve() if asked else self.directory
        if not directory.is_dir():
            raise FlowError(f"there is no directory `{directory}`")
        return directory

    async def _read(self, params: dict[str, Any]) -> tuple[FlowSession, str]:
        """The pre-op contract in one line: no version resolves against a stale
        file plane. Every verb that names a cell or a branch starts here."""
        session = self._session(params, actor=_actor(params))
        await self.hub.quiesce(session, actor=_actor(params))
        return session, _branch(session, params)

    async def _flow_status(self, ref: FlowRef, *, actor: str) -> dict[str, Any]:
        session = self.hub.open(ref, actor=actor)
        await self.hub.quiesce(session, actor=actor)
        return await self._flow_brief(session) | {
            "cells": queries.cells(session, session.branch)["cells"],
            "disk_bytes": gc.disk_bytes(session.store),
            "hygiene": queries.hygiene(session),
        }

    async def _flow_brief(self, session: FlowSession) -> dict[str, Any]:
        sessions = session.store.index.agent_sessions()
        settings = session.store.manifest.settings
        return {
            "flow": session.ref.name,
            "flow_id": session.store.manifest.flow_id,
            "path": session.ref.address,
            "branch": session.branch,
            "checked_out": session.worktree.bound() is not None,
            "agent": sessions[0].label if sessions else None,
            "kernel": await _kernel(session, session.kernel.handshake),
            "settings": {
                "reactivity": settings.reactivity,
                "eager_cost_threshold_s": settings.eager_cost_threshold_s,
            },
        }

    async def _env(self) -> dict[str, Any]:
        """What the lockfile pins, and where each running kernel stands to it."""
        interpreter = envs.describe(self.directory)
        pinned = envs.packages(self.directory)
        return {
            "workspace": str(self.directory),
            "python": {"path": str(interpreter.python), "source": interpreter.source},
            "packages": [
                {"name": name, "version": version}
                for name, version in sorted(pinned.items())
            ],
            "flows": [
                await self._env_flow(session)
                for session in self.hub.opened(here=True, directory=self.directory)
            ],
        }

    async def _env_flow(self, session: FlowSession) -> dict[str, Any]:
        stale = await session.kernel.env_drift()
        return {
            "flow": session.ref.name,
            "kernel": session.kernel.state,
            "restart_required": bool(stale),
            "behind": stale,
        }

    def _edited(
        self,
        session: FlowSession,
        accepted: AcceptedCell,
        *,
        branch: str,
    ) -> dict[str, Any]:
        """What a daemon-originated edit did, including its file projection."""
        written = session.worktree.project_cell(branch=branch)
        session.reactor.arm()
        return {
            "slug": accepted.slug,
            "branch": branch,
            "definition_hash": accepted.definition_hash,
            "written_to_files": written,
            "flags": _flags(accepted),
        }

    def _rewire(
        self, session: FlowSession, uids: list[str], *, branch: str, actor: str
    ) -> list[str]:
        """Carry a new name into the consumers that still spell the old one."""
        renamed = session.acceptance.rewire(uids, branch=branch, actor=actor)
        return [accepted.slug for accepted in renamed]

    def _reproject(self, session: FlowSession, branch: str) -> Projection | None:
        """Carry a slice change into the files, when it is this branch's files."""
        # Switching, forking, rewinding, adopting and deleting all move which
        # versions the branch selects, which is the other half of what a verdict
        # is derived from. Reactivity has a new answer after every one of them.
        session.reactor.arm()
        if session.worktree.bound() is None or branch != session.branch:
            return None
        return session.worktree.project(branch)


def _flags(accepted: AcceptedCell) -> list[dict[str, str | None]]:
    """What was wrong with a cell and still accepted — the chip's words."""
    return [{"code": flag.code, "detail": flag.detail} for flag in accepted.flags]


def _validate_reorder_topology(
    versions: dict[str, VersionRow],
    moved: VersionRow,
    order: Decimal,
    effective: dict[str, Decimal],
    branch: str,
) -> None:
    producer_uids = {
        ref.uid
        for ref in moved.manifest.consumes.values()
        if ref.uid is not None and ref.uid != moved.uid and ref.uid in versions
    }
    producers = sorted(
        (versions[uid] for uid in producer_uids), key=lambda version: version.slug
    )
    for producer in producers:
        if effective[producer.uid] >= order:
            raise FlowError(
                f"`{moved.slug}` cannot be placed before its producer "
                f"`{producer.slug}` on `{branch}`"
            )

    consumers = sorted(
        (
            version
            for uid, version in versions.items()
            if uid != moved.uid
            and any(ref.uid == moved.uid for ref in version.manifest.consumes.values())
        ),
        key=lambda version: version.slug,
    )
    for consumer in consumers:
        if effective[consumer.uid] <= order:
            raise FlowError(
                f"`{moved.slug}` cannot be placed after its consumer "
                f"`{consumer.slug}` on `{branch}`"
            )


def _one_cell_per_identity(carried: Sequence[PortableCell]) -> None:
    """Refuse a file whose blocks are one cell written twice.

    Identity travels in the source, so a block duplicated to make a lane
    still names the cell it was copied from. Accepting both would read the
    second as a rename of the first and leave the file holding a cell that
    never arrived — a count the result would then report wrongly. The remedy
    is the one the format can state: a block with its own name and no `uid`
    line arrives as a cell of its own.
    """
    seen: dict[str, str] = {}
    for cell in carried:
        parsed = loader.parse(cell.source)
        if parsed.uid is None:
            continue
        if parsed.uid in seen:
            written = (
                f"`{cell.slug}` twice"
                if seen[parsed.uid] == cell.slug
                else f"`{seen[parsed.uid]}` and `{cell.slug}` as one cell"
            )
            raise FlowError(
                f"this file holds {written}. a block arrives as a cell of its "
                "own, under its own name, with no `uid` line"
            )
        seen[parsed.uid] = cell.slug


def _accept_carried(
    session: FlowSession,
    carried: Sequence[PortableCell],
    batch: Batch,
    *,
    branch: str,
    actor: str,
) -> list[AcceptedCell]:
    """Accept every cell in an imported file, until a pass moves nothing.

    Two passes, not one: an export writes producers first, so its own round
    trip binds on the first, but a file somebody reordered by hand would leave
    a consumer pointing at a name that only arrives below it. A second pass
    costs a parse per cell and nothing else — an unchanged cell writes no
    version.
    """
    landed: list[AcceptedCell] = []
    branch_id = session.store.branches.get(branch).branch_id
    selected = session.store.index.slice_versions(branch_id)
    for _ in range(_IMPORT_PASSES):
        landed, moved = [], False
        for cell in carried:
            source = cell.source
            here = batch.slice_over(selected)
            parsed = loader.parse(source)
            previous = (
                here.get(parsed.uid)
                if parsed.uid is not None
                else next(
                    (version for version in here.values() if version.slug == cell.slug),
                    None,
                )
            )
            if previous is not None:
                stored = session.store.objects.get(previous.raw_source_ref).decode(
                    "utf-8"
                )
                # Block separators normalize endings; keep the stored bytes
                # when that formatting is the only difference.
                if stored.rstrip("\n") == source.rstrip("\n"):
                    source = stored
            accepted = session.acceptance.accept_source(
                cell.slug,
                source,
                branch=branch,
                actor=actor,
                batch=batch,
            )
            landed.append(accepted)
            moved = moved or not accepted.unchanged
        if not moved:
            break
    return landed


async def _kernel(
    session: FlowSession, handshake: dict[str, Any] | None
) -> dict[str, Any]:
    """Plumbing is invisible: the only fact a surface needs is running or not.

    The one kernel control that does surface is an env that moved under a
    running process, which is what the restart banner is for.
    """
    behind = await session.kernel.env_drift()
    state = {
        "state": session.kernel.state,
        "restart_required": bool(behind),
        "behind": behind,
    }
    if handshake is None:
        return state
    return state | {
        "python": handshake.get("python"),
        "kinds": [kind.get("kind") for kind in handshake.get("kinds") or []],
    }


def _outcome(outcome: RunOutcome) -> dict[str, Any]:
    return {
        "branch": outcome.branch,
        "target": outcome.target,
        "executed": list(outcome.executed),
        "cached": list(outcome.cached),
        "pruned": list(outcome.pruned),
        "failed": outcome.failed,
        "abandoned": outcome.abandoned,
    }


def _one_of(value: Any, allowed: Sequence[str], called: str) -> Any:
    """A setting only takes the words it has. Naming them beats a silent write."""
    if str(value) not in allowed:
        raise FlowError(
            f"`{value}` is not a {called}. it is "
            + " or ".join(f"`{word}`" for word in allowed)
        )
    return str(value)


def _number[Number: (int, float)](
    value: Any, kind: type[Number], *, name: str
) -> Number:
    try:
        return kind(value)
    except (TypeError, ValueError, OverflowError) as invalid:
        expected = "an integer" if kind is int else "a number"
        raise FlowError(f"`{name}` must be {expected}") from invalid


def _preflight(preflight: Preflight) -> dict[str, Any]:
    return {
        "branch": preflight.branch,
        "target": preflight.target,
        "cached": list(preflight.cached),
        "recompute": list(preflight.recompute),
        "unknown": list(preflight.unknown),
        "estimate_seconds": preflight.estimate_seconds,
        "reasons": list(preflight.reasons),
    }


def _projection(projection: Projection | None) -> dict[str, Any]:
    if projection is None:
        return {"projected": None}
    return {
        "projected": {
            "written": list(projection.written),
            "removed": list(projection.removed),
        }
    }


def _placeholder_slug(session: FlowSession) -> str:
    """The next free `untitled_N`. Adding a cell never waits for a name."""
    prefix = f"{PLACEHOLDER_SLUG}_"
    assigned = [
        int(suffix)
        for slug in session.store.index.version_slugs()
        if slug.startswith(prefix) and (suffix := slug[len(prefix) :]).isdigit()
    ]
    return f"{prefix}{max(assigned, default=0) + 1}"


def _scaffold(
    session: FlowSession, params: dict[str, Any], *, slug: str, branch: str
) -> str:
    """The file a new cell starts as, wired to what it comes after when told."""
    after = params.get("after")
    producer = queries.head(session, branch, str(after)) if after else None
    materialization = None
    if producer is not None:
        branch_id = session.store.branches.get(branch).branch_id
        mat_id = session.store.index.baselines(branch_id).get(producer.uid)
        materialization = (
            session.store.index.materialization(mat_id) if mat_id else None
        )
    docstring = params.get("docstring")
    return scaffold.cell_source(
        slug,
        docstring=str(docstring) if docstring else None,
        producer=producer.slug if producer is not None else None,
        outputs=(
            queries.downstream_outputs(
                producer,
                materialization,
                include_all=params.get("outputs") == "all",
            )
            if producer is not None
            else ()
        ),
    )


def _unstored(slug: str, output: str, materialized: bool) -> str:
    if not materialized:
        return f"nothing is stored for `{slug}.{output}` yet. run `{slug}` first"
    return (
        f"`{slug}.{output}` is declared not to persist, so lumlflow never "
        f"stored its value. run `{slug}` again to materialize it"
    )


def _flow_name(params: dict[str, Any]) -> str | None:
    name = params.get("flow")
    return str(name) if name else None


def _named(value: Any) -> str | None:
    return str(value) if value else None


def _actor(params: dict[str, Any]) -> str:
    return str(params.get("actor") or "user")


def _branch(session: FlowSession, params: dict[str, Any]) -> str:
    branch = params.get("branch")
    return str(branch) if branch else session.branch


def _leaves(session: FlowSession, branch: str) -> list[str]:
    here = queries.read(session, branch)
    consumed = {
        ref.uid
        for version in here.versions.values()
        for ref in version.manifest.consumes.values()
        if ref.uid in here.versions
    }
    return [
        here.versions[uid].slug
        for uid in reading_order(here.versions)
        if uid not in consumed and here.versions[uid].manifest.classification != "note"
    ]


def _target(params: dict[str, Any]) -> str:
    target = params.get("target")
    if not target:
        raise FlowError("name a cell to run, as `slug` or `slug.output`")
    return str(target)


def _targets(params: dict[str, Any]) -> list[str]:
    named = [str(name) for name in params.get("targets") or [] if str(name).strip()]
    return named or [_target(params)]
