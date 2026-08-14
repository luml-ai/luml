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
from pathlib import Path
from typing import Any, get_args

from lumlflow.flow.daemon import connect, envs, handoff, queries, secrets, workspace
from lumlflow.flow.daemon.hub import FlowSession, Focus, Hub
from lumlflow.flow.daemon.projections import Projection
from lumlflow.flow.daemon.uploads import Published
from lumlflow.flow.daemon.workspace import FlowRef
from lumlflow.flow.dsl import loader, portable, scaffold
from lumlflow.flow.dsl.accept import PLACEHOLDER_SLUG, AcceptedCell, Batch
from lumlflow.flow.dsl.portable import PortableCell
from lumlflow.flow.errors import (
    EditConflict,
    FlowError,
    ValueNotStored,
)
from lumlflow.flow.scheduler.planner import Preflight
from lumlflow.flow.scheduler.queue import RunOutcome
from lumlflow.flow.store import gc
from lumlflow.flow.store.models import AgentBegin, AgentEnd, EnvPolicy, Reactivity

Method = Callable[[dict[str, Any]], Awaitable[Any]]

# One pass names every cell an imported file holds, a second binds the
# references the first could not see yet. Nothing a third would find.
_IMPORT_PASSES = 2


class Api:
    def __init__(self, hub: Hub, *, stop: Callable[[], None] | None = None) -> None:
        self.hub = hub
        # Where the browser reaches this workspace, once the daemon has bound
        # it. A process serving only the socket leaves it None rather than
        # naming a port nothing answers on.
        self.web: str | None = None
        self._stop = stop
        self.methods: dict[str, Method] = {
            "ping": self.ping,
            "status": self.status,
            "context": self.context,
            "set_focus": self.set_focus,
            "tree": self.tree,
            "graph": self.graph,
            "diff": self.diff,
            "workspace.list": self.workspace_list,
            "flow.init": self.flow_init,
            "flow.open": self.flow_open,
            "flow.checkout": self.flow_checkout,
            "flow.delete": self.flow_delete,
            "cells.list": self.cells_list,
            "cells.show": self.cells_show,
            "cells.logs": self.cells_logs,
            "cells.new": self.cells_new,
            "cells.edit": self.cells_edit,
            "cells.delete": self.cells_delete,
            "cells.eager": self.cells_eager,
            "asset.preview": self.asset_preview,
            "asset.page": self.asset_page,
            "asset.diff": self.asset_diff,
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
            "agent.connect": self.agent_connect,
            "settings.set": self.settings_set,
            "secrets.set": self.secrets_set,
            "secrets.list": self.secrets_list,
            "env.status": self.env_status,
            "env.add": self.env_add,
            "env.remove": self.env_remove,
            "promote": self.promote,
            "run": self.run,
            "eval": self.eval,
            "preflight": self.preflight,
            "cancel": self.cancel,
            "kernel.restart": self.kernel_restart,
            "journal.since": self.journal_since,
            "shutdown": self.shutdown,
        }

    async def ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liveness, cheap enough to ask on every verb — and where the UI is.

        `running` is how `lumlflow ui` decides whether the process holding this
        workspace may be restarted under it: nothing in flight, nothing lost.
        """
        return {
            "workspace": str(self.hub.root),
            "pid": os.getpid(),
            "web": self.web,
            "running": self.hub.running(),
        }

    async def status(self, params: dict[str, Any]) -> dict[str, Any]:
        """The workspace, its flows, and what is unsynced in each."""
        interpreter = envs.describe(self.hub.root)
        refs = (
            [self.hub.select(_flow_name(params))]
            if params.get("flow")
            else self.hub.flows()
        )
        return {
            "workspace": str(self.hub.root),
            "pid": os.getpid(),
            "python": {
                "path": str(interpreter.python),
                "source": interpreter.source,
            },
            "flows": [await self._flow_status(ref) for ref in refs],
        }

    async def context(self, params: dict[str, Any]) -> dict[str, Any]:
        """The orientation brief: where you are, what is unsynced, what broke."""
        session, branch = await self._read(params)
        return queries.context(session, branch)

    async def set_focus(self, params: dict[str, Any]) -> dict[str, Any]:
        """Record what the user is looking at, so the brief can say so.

        No quiesce: this reads nothing and resolves no version — it is a
        report, sent on every selection change, and reconciling the file plane
        for each one would make clicking a cell as expensive as running it.
        """
        session = self.hub.session(_flow_name(params))
        session.focus = Focus(
            branch=_named(params.get("branch")),
            asset=_named(params.get("asset")),
            compare=tuple(
                str(name) for name in params.get("compare") or () if str(name)
            ),
        )
        return {
            "flow": session.ref.name,
            "branch": session.focus.branch,
            "asset": session.focus.asset,
            "compare": list(session.focus.compare),
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
            depth=int(params.get("depth") or queries.DEFAULT_DEPTH),
        )

    async def diff(self, params: dict[str, Any]) -> dict[str, Any]:
        session, _ = await self._read(params)
        return queries.diff(
            session, [str(name) for name in params.get("branches") or []]
        )

    async def workspace_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return workspace.listing(self.hub.root, str(params.get("path") or ""))

    async def flow_init(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name") or params.get("path") or ""
        session = self.hub.init_flow(str(name))
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
        ref = self.hub.select(_flow_name(params))
        if params.get("worktree", True):
            session = self.hub.open(ref)
            await self.hub.quiesce(session)
            if session.worktree.bound() is None:
                session.worktree.checkout(actor=_actor(params), force=True)
        return await self._flow_status(ref)

    async def flow_checkout(self, params: dict[str, Any]) -> dict[str, Any]:
        """Bind the flow root to a branch and project it — what `init` adds."""
        session = self.hub.session(_flow_name(params))
        await self.hub.quiesce(session)
        projection = session.worktree.checkout(
            params.get("branch"),
            actor=_actor(params),
            intent=params.get("intent"),
            force=bool(params.get("force")),
        )
        self.hub.document(session)
        return await self._flow_brief(session) | _projection(projection)

    async def flow_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        ref = self.hub.select(_flow_name(params))
        await self.hub.delete_flow(ref)
        return {"deleted": ref.name, "path": ref.relpath}

    async def cells_list(self, params: dict[str, Any]) -> dict[str, Any]:
        session, branch = await self._read(params)
        return queries.cells(session, branch, unsynced=bool(params.get("unsynced")))

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
        actor, force = _actor(params), bool(params.get("force"))
        if branch == session.branch:
            session.worktree.guard(actor=actor, force=force)
        result = session.store.branches.delete(
            str(params.get("slug") or ""),
            branch=branch,
            actor=actor,
            intent=params.get("intent"),
        )
        return {
            "slug": result.slug,
            "branch": branch,
            "dangling": result.dangling,
        } | _projection(self._reproject(session, branch, actor=actor, force=force))

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
        slug = str(params.get("slug") or "").strip().lower()
        if not slug:
            slug = _placeholder_slug(session, branch)
        source = params.get("source") or _scaffold(
            session, params, slug=slug, branch=branch
        )
        accepted = session.acceptance.accept_source(
            slug,
            str(source),
            branch=branch,
            actor=_actor(params),
            intent=params.get("intent") or f"added {slug}",
            fresh=True,
        )
        return self._edited(session, accepted, branch=branch, actor=_actor(params))

    async def cells_edit(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write an edit the daemon was handed, under per-cell optimistic locking.

        `base` is the `definition_hash` the editor started from. A head that
        moved past it is not overwritten silently — the caller is handed both
        versions and picks: overwrite, or fork the edit onto a branch of its
        own.
        """
        session = self.hub.session(_flow_name(params))
        await self.hub.quiesce(session)
        branch = _branch(session, params)
        slug = str(params.get("slug") or "")
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
            str(params.get("source") or ""),
            branch=branch,
            actor=_actor(params),
            intent=params.get("intent") or f"edited {slug}",
            uid=head.uid,
        )
        return self._edited(
            session,
            accepted,
            branch=branch,
            actor=_actor(params),
            held=head.version_id,
        )

    async def asset_preview(self, params: dict[str, Any]) -> dict[str, Any]:
        """An output as the store holds it — verdict, kind, and stored preview."""
        session, branch = await self._read(params)
        return queries.asset(session, branch, _target(params))

    async def asset_page(self, params: dict[str, Any]) -> dict[str, Any]:
        """Read into a value. This is the gesture that starts a kernel."""
        session, branch = await self._read(params)
        here = queries.read(session, branch)
        slug, output, record = queries.locate(here, _target(params))
        if record is None or record.value_ref is None:
            raise ValueNotStored(_unstored(slug, output, record is not None))
        page = await session.kernel.page(
            record.value_ref, record.kind, dict(params.get("query") or {})
        )
        return {"slug": slug, "output": output, "kind": record.kind, "page": page}

    async def asset_diff(self, params: dict[str, Any]) -> dict[str, Any]:
        """One asset across two branches: did the code move, did the result."""
        session, _ = await self._read(params)
        branches = [str(name) for name in params.get("branches") or []]
        return queries.asset_diff(session, branches, _target(params))

    async def asset_download(self, params: dict[str, Any]) -> dict[str, Any]:
        """Copy a stored value out of the flow, under a name of the caller's."""
        session, branch = await self._read(params)
        here = queries.read(session, branch)
        slug, output, record = queries.locate(here, _target(params))
        if record is None or record.value_ref is None:
            raise ValueNotStored(_unstored(slug, output, record is not None))
        destination = Path(str(params.get("to") or f"{slug}.{output}")).expanduser()
        if destination.is_dir():
            destination = destination / f"{slug}.{output}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(session.store.values.path(record.value_ref), destination)
        return {
            "slug": slug,
            "output": output,
            "kind": record.kind,
            "size": record.size,
            "path": str(destination),
        }

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
        actor, force = _actor(params), bool(params.get("force"))
        if branch == session.branch:
            # Import rewrites `cells/` wholesale, which is the one thing the
            # lock is for: an agent working in there is not interrupted.
            session.worktree.guard(actor=actor, force=force)
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
        return {
            "flow": session.ref.name,
            "branch": branch,
            "cells": [{"slug": cell.slug, "flags": _flags(cell)} for cell in accepted],
        } | _projection(self._reproject(session, branch, actor=actor, force=force))

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
        return {
            "branch": created.name,
            "from_branch": parent,
            "forked_at_step": created.fork_step,
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
        actor, force = _actor(params), bool(params.get("force"))
        if branch == session.branch:
            session.worktree.guard(actor=actor, force=force)
        old, new = str(params.get("slug") or ""), str(params.get("to") or "")
        head = queries.head(session, branch, old)
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
        } | _projection(self._reproject(session, branch, actor=actor, force=force))

    async def secrets_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Store a secret for this flow. The value is never read back."""
        session = self.hub.session(_flow_name(params))
        name = secrets.set_secret(
            session,
            str(params.get("name") or ""),
            str(params.get("value") or ""),
            actor=_actor(params),
        )
        return {"name": name, "names": secrets.names(session)}

    async def secrets_list(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self.hub.session(_flow_name(params))
        return {"names": secrets.names(session)}

    async def env_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """What the workspace pins, and which kernels are running behind it."""
        return await self._env()

    async def env_add(self, params: dict[str, Any]) -> dict[str, Any]:
        """Put packages in the workspace env. Every flow under it shares them."""
        await envs.add(self.hub.root, _packages(params))
        return await self._env_moved(params)

    async def env_remove(self, params: dict[str, Any]) -> dict[str, Any]:
        await envs.remove(self.hub.root, _packages(params))
        return await self._env_moved(params)

    async def switch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check a branch out: rebind the worktree and project its slice."""
        session = self.hub.session(_flow_name(params))
        await self.hub.quiesce(session)
        projection = session.worktree.checkout(
            str(params.get("branch") or ""),
            actor=_actor(params),
            intent=params.get("intent"),
            force=bool(params.get("force")),
        )
        self.hub.document(session)
        return await self._flow_brief(session) | _projection(projection)

    async def rewind(self, params: dict[str, Any]) -> dict[str, Any]:
        """Restore a branch to a step. Instant, and the files follow."""
        session = self.hub.session(_flow_name(params))
        await self.hub.quiesce(session)
        branch = _branch(session, params)
        actor = _actor(params)
        force = bool(params.get("force"))
        if branch == session.branch:
            session.worktree.guard(actor=actor, force=force)
        result = session.store.branches.rewind(
            branch,
            to_step=int(params.get("to_step") or 0),
            actor=actor,
            intent=params.get("intent"),
        )
        return {
            "branch": result.branch,
            "to_step": result.to_step,
            "cells": len(result.selections),
        } | _projection(self._reproject(session, branch, actor=actor, force=force))

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
        session = self.hub.session(_flow_name(params))
        await self.hub.quiesce(session)
        branch = _branch(session, params)
        actor = _actor(params)
        force = bool(params.get("force"))
        if branch == session.branch:
            session.worktree.guard(actor=actor, force=force)
        result = session.store.branches.adopt(
            str(params.get("slug") or ""),
            from_branch=str(params.get("from_branch") or ""),
            to_branch=branch,
            force=force,
            actor=actor,
            intent=params.get("intent"),
        )
        if result.reaccept:
            session.acceptance.reaccept(result.reaccept, branch=branch, actor=actor)
        return {
            "slug": result.slug,
            "branch": branch,
            "rebound": list(result.reaccept),
        } | _projection(self._reproject(session, branch, actor=actor, force=force))

    async def agent_begin(self, params: dict[str, Any]) -> dict[str, Any]:
        """Register an agent session. A worktree one owns the files while it lasts.

        Detected, never wrapped: the journal entry is what the pair panel reads
        and what file-plane edits attribute to until it ends.

        Registering twice under one actor is how a session that started reading
        takes the files when it first changes something — the row is replaced,
        so the upgrade costs one entry and no second session.

        `lease` says the caller's connection carries this session: it ends when
        that connection does, whether or not anybody got to say so. A caller
        that connects per call — every CLI verb — must not ask for one.
        """
        session = self.hub.session(_flow_name(params))
        label = str(params.get("label") or params.get("actor") or "agent")
        actor = str(params.get("actor") or label)
        worktree = bool(params.get("worktree", True))
        # Open the bracket over a settled file plane: edits made before the
        # session began belong to whoever was there before it.
        await self.hub.quiesce(session)
        session.store.commit(
            [AgentBegin(actor=actor, label=label, worktree=worktree)],
            intent=params.get("intent") or _begun(label, worktree),
            actor=actor,
        )
        return {
            "actor": actor,
            "label": label,
            "worktree": worktree,
            "leased": bool(params.get("lease")),
        }

    async def agent_end(self, params: dict[str, Any]) -> dict[str, Any]:
        """Close the bracket — and with it the transaction its edits group into."""
        session = self.hub.session(_flow_name(params))
        actor = str(params.get("actor") or "")
        holder = session.store.index.worktree_holder()
        registered = next(
            (
                found
                for found in session.store.index.agent_sessions()
                if found.actor == actor
            ),
            holder,
        )
        if registered is None:
            raise FlowError("no agent session is registered here")
        await self.hub.quiesce(session, tier="live")
        session.store.commit(
            [AgentEnd(actor=registered.actor, label=registered.label)],
            intent=params.get("intent") or f"{registered.label} finished",
            actor=registered.actor,
        )
        # The files the session held back are owed to whoever waited on it —
        # unless somebody else is still working in them, in which case the
        # deferral simply stands. The session has already ended either way, and
        # refusing to say so over files it no longer holds would be a lie.
        projection = (
            self._reproject(session, session.branch, actor="user", force=False)
            if session.store.index.worktree_holder() is None
            else None
        )
        return {"actor": registered.actor, "label": registered.label} | _projection(
            projection
        )

    async def agent_connect(self, params: dict[str, Any]) -> dict[str, Any]:
        """The prompt that pairs an agent with this flow, whatever harness it is.

        Built here for the same reason a handoff is: the facts are here — the
        workspace's path, the branch the files hold, the interpreter this is
        served by — and a surface that assembled them itself would be guessing
        at the one thing the reader is about to paste into a config.

        No quiesce: nothing in it resolves a version, and reconciling the file
        plane to answer "how do I connect" would make opening a popover cost
        what running a verb costs.
        """
        session = self.hub.session(_flow_name(params))
        return connect.prompt(session, workspace_dir=session.workspace_dir)

    async def agent_payload(self, params: dict[str, Any]) -> dict[str, Any]:
        """The context a send-to-agent gesture hands over.

        Built here because the facts are here: a *fix this* carries the
        traceback of a run no surface opened, and a *summarize this branch*
        carries the intents the timeline is drawn from. Every surface asking
        for the same gesture gets the same payload.
        """
        session, branch = await self._read(params)
        target = params.get("slug") or params.get("target")
        return handoff.payload(
            session,
            gesture=str(params.get("gesture") or ""),
            branch=branch,
            slug=str(target) if target else None,
            branches=[str(name) for name in params.get("branches") or []],
        )

    async def settings_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write the settings a surface renders into `flow.yaml`.

        Config, not history: these decide what the runtime does next, so they
        are journaled nowhere — the same reason `cells eager` is not a
        transaction. Anything absent from the call is left alone.
        """
        session = self.hub.session(_flow_name(params))
        settings = session.store.manifest.settings
        if params.get("reactivity") is not None:
            settings.reactivity = _one_of(
                params["reactivity"], get_args(Reactivity), "reactivity"
            )
        if params.get("eager_cost_threshold_s") is not None:
            settings.eager_cost_threshold_s = float(params["eager_cost_threshold_s"])
        if params.get("env_policy") is not None:
            settings.env_policy = _one_of(
                params["env_policy"], get_args(EnvPolicy), "env policy"
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
                "env_policy": settings.env_policy,
            },
        }

    async def promote(self, params: dict[str, Any]) -> dict[str, Any]:
        """Publish a stored output the cell declared inline.

        The authoring default is `asset`, so promoting is the cheap way out of
        it afterwards: the bytes are already staged, and this only asks the
        platform to keep a copy.
        """
        session, branch = await self._read(params)
        here = queries.read(session, branch)
        slug, output, record = queries.locate(here, _target(params))
        if record is None or record.value_ref is None:
            raise ValueNotStored(_unstored(slug, output, record is not None))
        published = await session.uploads.promote(
            here.mats[here.uid_of(slug)].mat_id,
            output,
            actor=_actor(params),
            intent=params.get("intent"),
        )
        return {"flow": session.ref.name, "branch": branch} | _published(published)

    async def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run a target's closure. `force` drops memoization for this plan.

        Forcing is what a surface offers when the recorded result is suspect —
        a cell that reads something the store does not hash — and it is never
        the default: it spends the whole closure's cost again on purpose.
        """
        session, branch = await self._read(params)
        outcome = await session.queue.submit(
            _target(params),
            branch=branch,
            actor=_actor(params),
            force=bool(params.get("force")),
        )
        # Publishing is downstream of the record and never in the run's way: a
        # native output is journaled as queued here, and uploaded off to one
        # side, so a network that is not there costs a run nothing.
        session.uploads.sync()
        self.hub.document(session)
        # A result the user paid for is what makes the cheap cells under it
        # affordable: running the expensive parent is the gesture that lets
        # reactivity take the plot below it.
        session.reactor.arm()
        return _outcome(outcome)

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
            queries.repl_names(session, here),
            str(params.get("code") or ""),
            paranoid=session.store.manifest.settings.paranoid,
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
        session = self.hub.session(_flow_name(params))
        branch = _branch(session, params)
        left = session.queue.abandon(branch)
        return {
            "branch": branch,
            "left": left.left,
            "stopped": left.stopped,
            "awaiting": left.awaiting,
        }

    async def kernel_restart(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self.hub.session(_flow_name(params))
        handshake = await session.kernel.restart()
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
        session = self.hub.session(_flow_name(params))
        entries = [
            entry.model_dump(mode="json")
            for entry in session.store.journal.since(int(params.get("cursor") or 0))
        ]
        return {
            "flow": session.ref.name,
            "path": session.ref.relpath,
            "cursor": session.store.next_step - 1,
            "transactions": entries,
        }

    async def shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._stop is not None:
            self._stop()
        return {"stopping": True}

    async def _read(self, params: dict[str, Any]) -> tuple[FlowSession, str]:
        """The pre-op contract in one line: no version resolves against a stale
        file plane. Every verb that names a cell or a branch starts here."""
        session = self.hub.session(_flow_name(params))
        await self.hub.quiesce(session)
        return session, _branch(session, params)

    async def _flow_status(self, ref: FlowRef) -> dict[str, Any]:
        session = self.hub.open(ref)
        await self.hub.quiesce(session)
        return await self._flow_brief(session) | {
            "cells": queries.cells(session, session.branch)["cells"],
            "disk_bytes": gc.disk_bytes(session.store),
            "hygiene": queries.hygiene(session),
        }

    async def _flow_brief(self, session: FlowSession) -> dict[str, Any]:
        holder = session.store.index.worktree_holder()
        settings = session.store.manifest.settings
        return {
            "flow": session.ref.name,
            "path": session.ref.relpath,
            "branch": session.branch,
            "checked_out": session.worktree.bound() is not None,
            "agent": holder.label if holder is not None else None,
            "unwritten": session.worktree.pending(),
            "kernel": await _kernel(session, session.kernel.handshake),
            # The three settings a surface renders. The rest of `flow.yaml`'s
            # settings block is the runtime's own (sandbox, the safety modes),
            # and a panel that showed them would be offering toggles for
            # decisions taken at kernel start.
            "settings": {
                "reactivity": settings.reactivity,
                "eager_cost_threshold_s": settings.eager_cost_threshold_s,
                "env_policy": settings.env_policy,
            },
        }

    async def _env(self) -> dict[str, Any]:
        """What the lockfile pins, and where each running kernel stands to it."""
        interpreter = envs.describe(self.hub.root)
        pinned = envs.packages(self.hub.root)
        return {
            "workspace": str(self.hub.root),
            "python": {"path": str(interpreter.python), "source": interpreter.source},
            "packages": [
                {"name": name, "version": version}
                for name, version in sorted(pinned.items())
            ],
            "flows": [
                await self._env_flow(session)
                for session in self.hub.opened(here=True)
            ],
        }

    async def _env_moved(self, params: dict[str, Any]) -> dict[str, Any]:
        """Journal what the install did, then apply each flow's restart policy.

        The banner is the floor under every policy: a kernel left holding the
        old imports is reported as behind whether or not anything restarts it.
        """
        envs.sync(
            self.hub.root,
            self.hub.opened(here=True),
            actor=_actor(params),
            intent=params.get("intent"),
        )
        for session in self.hub.opened(here=True):
            if session.store.manifest.settings.env_policy != "auto":
                continue
            # A restart mid-run kills the run. The policy is about applying an
            # install, not about losing ten minutes of training to one.
            if session.queue.busy or not await session.kernel.env_drift():
                continue
            await session.kernel.restart()
        return await self._env()

    async def _env_flow(self, session: FlowSession) -> dict[str, Any]:
        stale = await session.kernel.env_drift()
        return {
            "flow": session.ref.name,
            "kernel": session.kernel.state,
            "policy": session.store.manifest.settings.env_policy,
            "restart_required": bool(stale),
            "behind": stale,
        }

    def _edited(
        self,
        session: FlowSession,
        accepted: AcceptedCell,
        *,
        branch: str,
        actor: str,
        held: str | None = None,
    ) -> dict[str, Any]:
        """What a daemon-originated edit did, and whether the files know yet."""
        written = session.worktree.project_cell(
            accepted.uid, branch=branch, held=held, actor=actor
        )
        self.hub.document(session)
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

    def _reproject(
        self, session: FlowSession, branch: str, *, actor: str, force: bool
    ) -> Projection | None:
        """Carry a slice change into the files, when it is this branch's files."""
        self.hub.document(session)
        # Switching, forking, rewinding, adopting and deleting all move which
        # versions the branch selects, which is the other half of what a verdict
        # is derived from. Reactivity has a new answer after every one of them.
        session.reactor.arm()
        if session.worktree.bound() is None or branch != session.branch:
            return None
        return session.worktree.project(branch, actor=actor, force=force)


def _begun(label: str, worktree: bool) -> str:
    """What a registration reads as. A session takes the files when it first
    changes something, so connecting and working are two lines, not one."""
    return f"{label} started working" if worktree else f"{label} connected"


def _flags(accepted: AcceptedCell) -> list[dict[str, str | None]]:
    """What was wrong with a cell and still accepted — the chip's words."""
    return [{"code": flag.code, "detail": flag.detail} for flag in accepted.flags]


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
        parsed = loader.parse(cell.source).cell
        if parsed is None or parsed.uid is None:
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
    for _ in range(_IMPORT_PASSES):
        landed, moved = [], False
        for cell in carried:
            accepted = session.acceptance.accept_source(
                cell.slug, cell.source, branch=branch, actor=actor, batch=batch
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

    Plus the one kernel control that does surface — an env that moved under a
    running process is what the restart banner is for — and what the process is
    confined by, which is reported rather than assumed: a sandbox the platform
    would not give us is a fact a user is entitled to read.
    """
    behind = await session.kernel.env_drift()
    state = {
        "state": session.kernel.state,
        "restart_required": bool(behind),
        "behind": behind,
        "sandbox": session.kernel.sandbox_profile.report(),
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


def _published(published: Published) -> dict[str, Any]:
    return {
        "slug": published.slug,
        "output": published.output,
        "state": published.state,
        "reference": (
            published.reference.model_dump(mode="json")
            if published.reference is not None
            else None
        ),
        "detail": published.detail,
    }


def _preflight(preflight: Preflight) -> dict[str, Any]:
    return {
        "branch": preflight.branch,
        "target": preflight.target,
        "cached": list(preflight.cached),
        "recompute": list(preflight.recompute),
        "unknown": list(preflight.unknown),
        "estimate_seconds": preflight.estimate_seconds,
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


def _placeholder_slug(session: FlowSession, branch: str) -> str:
    """The next free `untitled_N`. Adding a cell never waits for a name."""
    branch_id = session.store.branches.get(branch).branch_id
    taken = {
        version.slug
        for version in session.store.index.slice_versions(branch_id).values()
    }
    return next(
        f"{PLACEHOLDER_SLUG}_{number}"
        for number in range(1, len(taken) + 2)
        if f"{PLACEHOLDER_SLUG}_{number}" not in taken
    )


def _scaffold(
    session: FlowSession, params: dict[str, Any], *, slug: str, branch: str
) -> str:
    """The file a new cell starts as, wired to what it comes after when told."""
    after = params.get("after")
    producer = queries.head(session, branch, str(after)) if after else None
    docstring = params.get("docstring")
    return scaffold.cell_source(
        slug,
        docstring=str(docstring) if docstring else None,
        producer=producer.slug if producer is not None else None,
        outputs=list(producer.manifest.produces) if producer is not None else (),
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


def _target(params: dict[str, Any]) -> str:
    target = params.get("target")
    if not target:
        raise FlowError("name a cell to run, as `slug` or `slug.output`")
    return str(target)


def _targets(params: dict[str, Any]) -> list[str]:
    named = [str(name) for name in params.get("targets") or [] if str(name).strip()]
    return named or [_target(params)]


def _packages(params: dict[str, Any]) -> list[str]:
    return [str(name) for name in params.get("packages") or [] if str(name).strip()]
