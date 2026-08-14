"""What the verbs print. One rule: slugs, lane names, outputs, and seconds.

The Tier-0 contract is a vocabulary contract as much as a verb-count one — a
loop an agent can drive from names alone. So nothing here prints a uid, a
content hash, or a memo key: those exist in `--json`, where a program that wants
them can ask, and nowhere a person reads.

Every function takes what the daemon answered and returns lines. Keeping them
pure is what lets one test sweep every surface for internals at once.
"""

from collections.abc import Iterable
from typing import Any

_SLUG_COLUMN = 22
_STATE_COLUMN = 15
_TABLE_ROWS = 5
# What follows this rule is the cell file itself, echoed byte for byte —
# uid line and all. It is the one place a printed surface shows an
# identifier, because the file the author is about to edit holds it.
SOURCE_RULE = "─" * 60

# The words every surface uses for a verdict. One vocabulary, or a reader
# meets two names for one state and has to work out that they agree.
# The keys are the store's, and they do not move; the words are the reader's.
STATES = {
    "synced": "current",
    "unsynced": "stale",
    "unmaterialized": "never run",
    "failed": "failed",
}


def status(payload: dict[str, Any]) -> list[str]:
    """The workspace, its flows, and where each one stands."""
    lines = [f"workspace {payload['workspace']}"]
    interpreter = payload.get("python") or {}
    if interpreter.get("path"):
        lines.append(f"python    {interpreter['path']}")
    for flow in payload.get("flows") or []:
        lines += ["", *_flow_heading(flow), *cell_lines(flow.get("cells") or [])]
    return lines


def cells(payload: dict[str, Any]) -> list[str]:
    listed = payload.get("cells") or []
    if not listed:
        return [f"no cells on `{payload['branch']}`"]
    return [f"{payload['flow']} · {payload['branch']}", *cell_lines(listed)]


def cell(payload: dict[str, Any]) -> list[str]:
    """One cell in full — what it is, what it produced, and its source."""
    cost = (
        f" · ran in {_seconds(payload['cost_seconds'])}"
        if payload.get("cost_seconds") is not None
        else ""
    )
    older = " · computed under an older env" if payload.get("older_env") else ""
    lines = [
        f"{payload['slug']} · {payload['branch']} · "
        f"{STATES[payload['state']]}{cost}{older}",
        *_indent(_causes(payload)),
        *_indent(_flags(payload)),
    ]
    if payload.get("consumes"):
        lines += ["", "consumes"]
        lines += [f"  {name} ← {ref}" for name, ref in payload["consumes"].items()]
    lines += ["", "produces"]
    for name, spec in (payload.get("produces") or {}).items():
        lines.append(
            f"  {name} ({spec['type']})"
            + ("" if spec["persist"] else " · not persisted")
        )
    for output in payload.get("materialized") or []:
        lines.append(f"  {output['name']}: {output['kind']}, {_size(output['size'])}")
    if payload.get("error"):
        lines += ["", "last failure", *_indent(str(payload["error"]).splitlines())]
    lines += ["", SOURCE_RULE, payload.get("source", "").rstrip()]
    return lines


def env(payload: dict[str, Any]) -> list[str]:
    """The workspace's packages, and any kernel still holding older ones."""
    interpreter = payload.get("python") or {}
    packages = payload.get("packages") or []
    counted = f"{len(packages)} package" + ("" if len(packages) == 1 else "s")
    lines = [
        f"workspace {payload['workspace']}",
        f"python    {interpreter.get('path', '')}",
        "",
        counted if packages else "no packages locked here",
        *_indent(f"{entry['name']} {entry['version']}" for entry in packages),
    ]
    for flow in payload.get("flows") or []:
        if flow.get("restart_required"):
            lines += [
                "",
                f"{flow['flow']} · "
                f"restart the kernel to apply {_names(flow.get('behind') or [])}",
            ]
    return lines


def context(payload: dict[str, Any]) -> list[str]:
    """The orientation brief, in the order a reader needs it."""
    lines = [
        f"{payload['flow']} · {payload['branch']}"
        + ("" if payload["checked_out"] else " (not on disk)")
        + (f" · {payload['agent']} is working here" if payload.get("agent") else ""),
        f"workspace {payload['workspace']}",
        f"cells {payload['cells']}",
        "checkpoint "
        + (
            f"step {payload['checkpoint']['step']} · {payload['checkpoint']['intent']}"
            if payload.get("checkpoint")
            else "none yet"
        ),
    ]
    unsynced = payload.get("unsynced") or []
    omitted = payload.get("unsynced_omitted", 0)
    if not unsynced:
        lines += ["", "everything on this lane is current"]
    else:
        lines += ["", f"stale ({len(unsynced) + omitted})"]
        lines += _indent(
            f"{entry['slug']} · {STATES[entry['state']]}"
            + (f": {'; '.join(entry['causes'])}" if entry.get("causes") else "")
            for entry in unsynced
        )
        if omitted:
            lines.append(f"  … and {omitted} more")
    lines += _pending(payload.get("pending") or {})
    for failure in payload.get("failures") or []:
        lines += [
            "",
            f"`{failure['slug']}` failed",
            *_indent((failure.get("error") or "").splitlines()),
        ]
    if payload.get("recent"):
        lines += ["", "recently"]
        lines += _indent(
            f"step {entry['step']} · {entry['actor']} · {entry['intent']}"
            + (" · offline" if entry.get("offline") else "")
            for entry in payload["recent"]
        )
    return lines


def tree(payload: dict[str, Any]) -> list[str]:
    lines = [payload["flow"]]
    for branch in payload.get("branches") or []:
        marker = "*" if branch["checked_out"] else " "
        family = (
            f"started from {branch['parent']} at step {branch['forked_at_step']}"
            if branch.get("parent")
            else "a root lane"
        )
        lines.append(
            f"{marker} {branch['branch']:<{_SLUG_COLUMN}} {family}"
            + (" · archived" if branch["archived"] else "")
            + (f" · {branch['agent']} is working here" if branch.get("agent") else "")
        )
        lines.append(
            f"    {branch['cells']} cells{_states(branch.get('states') or {})}"
        )
        if branch.get("last_intent"):
            last = branch["last_intent"]
            lines.append(f"    last: {last['actor']} · {last['intent']}")
    return lines


def graph(payload: dict[str, Any]) -> list[str]:
    nodes = payload.get("nodes") or []
    if not nodes:
        return [f"no cells on `{payload['branch']}`"]
    lines = [f"{payload['flow']} · {payload['branch']}"]
    if payload.get("around"):
        lines[0] += f" · around `{payload['around']}`"
    lines += cell_lines(nodes)
    edges = payload.get("edges") or []
    lines += ["", "wiring"] if edges else []
    lines += [f"  {edge['from']} → {edge['to']} ({edge['input']})" for edge in edges]
    return lines


def diff(payload: dict[str, Any]) -> list[str]:
    """Definition divergence, then results, then what neither shape covers."""
    lines = [" vs ".join(f"`{name}`" for name in payload["branches"])]
    definition = payload.get("definition") or []
    materialization = payload.get("materialization") or []
    shapeless = payload.get("shapeless") or []
    # First, because it is about whether the rest is worth reading.
    integrity = payload.get("integrity") or []
    if integrity:
        lines += ["", "not comparable"]
        lines += [f"  {warning['message']}" for warning in integrity]
    if definition:
        lines += ["", "edited on one side or the other"]
        for entry in definition:
            lines.append(f"  {entry['slug']}")
            lines += [
                f"    {side['branch']}: {side['author']}, step {side['step']}"
                + (f" · {', '.join(side['flags'])}" if side.get("flags") else "")
                for side in entry["versions"]
            ]
    if materialization:
        lines += ["", "same code, different results"]
        for entry in materialization:
            chips = " · ".join(
                f"{side['branch']}: {STATES[side['state']]}"
                for side in entry["results"]
            )
            lines.append(f"  {entry['slug']:<{_SLUG_COLUMN}} {chips}")
    if shapeless:
        lines += ["", "not on every lane"]
        for entry in shapeless:
            named = " · ".join(
                f"{branch}: {name or 'absent'}"
                for branch, name in entry["branches"].items()
            )
            lines.append(f"  {entry['slug']:<{_SLUG_COLUMN}} {named}")
    if not (definition or materialization or shapeless):
        lines.append("these lanes hold the same cells and the same results")
    return lines


def asset(payload: dict[str, Any]) -> list[str]:
    """An output: what it is, and whatever preview the run stored for it."""
    target = f"{payload['slug']}.{payload['output']}"
    lines = [f"{target} · {payload['branch']} · {STATES[payload['state']]}"]
    if payload.get("kind"):
        lines.append(
            f"{payload['kind']}, {_size(payload.get('size'))}"
            + ("" if payload.get("persisted", True) else " · value not stored")
        )
    preview = payload.get("preview")
    if not preview:
        return [*lines, "nothing stored to preview yet"]
    if preview.get("schema") != 1:
        lines.append("(a newer preview format. showing what is readable)")
    for block in preview.get("blocks") or []:
        lines += ["", *_block(block)]
    if preview.get("truncated"):
        lines.append("… truncated")
    return lines


def asset_diff(payload: dict[str, Any]) -> list[str]:
    target = payload["slug"] + (
        f".{payload['output']}" if payload.get("output") else ""
    )
    lines = [
        f"{target} · " + " vs ".join(f"`{name}`" for name in payload["branches"]),
        f"definition {payload['definition']} · result {payload['result']}",
    ]
    for side in payload.get("sides") or []:
        state = STATES.get(side["state"], side["state"])
        cost = (
            f" · {_seconds(side['cost_seconds'])}" if side.get("cost_seconds") else ""
        )
        lines.append(f"  {side['branch']:<{_SLUG_COLUMN}} {state}{cost}")
    return lines


def published(payload: dict[str, Any]) -> list[str]:
    """Where an output stands with the platform — never why the network failed
    in the platform's own words unless it said something worth relaying."""
    target = f"`{payload['slug']}.{payload['output']}`"
    if payload["state"] == "uploaded":
        return [f"{target} is published"]
    if payload["state"] == "failed":
        detail = payload.get("detail")
        return [
            f"{target} did not upload" + (f": {detail}" if detail else ""),
            "it stays queued. the next run or promote tries again",
        ]
    return [f"{target} is queued. it uploads when the platform is reachable"]


def preflight(payload: dict[str, Any]) -> list[str]:
    """What a run would do, before it does it."""
    lines = [f"`{payload['target']}` on `{payload['branch']}`"]
    if payload["recompute"]:
        lines.append(f"  recomputes {_names(payload['recompute'])}")
    if payload["cached"]:
        lines.append(f"  reuses     {_names(payload['cached'])}")
    if payload["unknown"]:
        lines.append(f"  never timed {_names(payload['unknown'])}")
    if not payload["recompute"]:
        lines.append("  nothing to do. everything it needs is current")
    elif payload["estimate_seconds"]:
        lines.append(
            f"  about {_seconds(payload['estimate_seconds'])}"
            + (" for what has been timed" if payload["unknown"] else "")
        )
    else:
        # A total of zero seconds over cells nobody has ever timed is not an
        # estimate of anything; saying so beats printing `0.00s`.
        lines.append("  no timing recorded yet. the cost is unknown")
    return lines


def outcome(payload: dict[str, Any]) -> list[str]:
    """What the run did. A failure is a recorded state, not an exception."""
    lines = []
    if payload["executed"]:
        lines.append(f"ran     {_names(payload['executed'])}")
    if payload["cached"]:
        lines.append(f"reused  {_names(payload['cached'])}")
    if payload["pruned"]:
        lines.append(f"skipped {_names(payload['pruned'])} · already current")
    if payload["failed"]:
        # The pointer stays inside the quickstart's vocabulary: an agent that
        # only read those twenty lines has to be able to follow it.
        lines.append(
            f"failed  `{payload['failed']}` · run `lumlflow context` for the traceback"
        )
    if payload["abandoned"]:
        lines.append("left the run. another lane is still waiting on it")
    return lines or ["nothing to do"]


def abandoned(payload: dict[str, Any]) -> list[str]:
    """Leaving a run, said as what it did — stopping it, or only leaving."""
    branch = payload["branch"]
    if not payload.get("left"):
        return [f"`{branch}` was not waiting on a run"]
    if payload.get("stopped"):
        return [f"stopped the run. `{branch}` was the last lane waiting on it"]
    others = int(payload.get("awaiting") or 0)
    return [
        f"`{branch}` left the run. it keeps going for "
        f"{others} other lane{'' if others == 1 else 's'}"
    ]


def evaluated(payload: dict[str, Any]) -> list[str]:
    """What the scratch code printed, then what it came to.

    A prompt's order, and a prompt's silence: code that printed nothing and
    answered `None` says nothing back.
    """
    lines = (payload.get("output") or "").rstrip("\n").splitlines()
    error = payload.get("error")
    if error:
        return lines + str(error["traceback"]).rstrip().splitlines()
    if payload.get("repr") is not None:
        lines.append(str(payload["repr"]))
    return lines + [
        f"`{name}` moved while that ran. lumlflow dropped its cached value"
        for name in payload.get("mutated") or []
    ]


def cell_lines(listed: Iterable[dict[str, Any]]) -> list[str]:
    lines = []
    for entry in listed:
        detail = "; ".join(entry.get("causes") or []) or _note(entry)
        state = STATES[entry["state"]]
        row = f"  {entry['slug']:<{_SLUG_COLUMN}} {state:<{_STATE_COLUMN}}{detail}"
        lines.append(row.rstrip())
        lines += _indent(_flags(entry))
        if entry.get("upstream") and entry["state"] == "synced":
            lines.append(f"    (below {_names(entry['upstream'])})")
    return lines


def _flow_heading(flow: dict[str, Any]) -> list[str]:
    kernel = flow.get("kernel") or {}
    heading = f"{flow['flow']} · {flow['branch']}"
    if not flow.get("checked_out", True):
        heading += " (not on disk)"
    if flow.get("agent"):
        heading += f" · {flow['agent']} is working here"
    heading += f" · kernel {kernel.get('state', 'stopped')}"
    lines = [heading]
    lines += _indent(_sandbox(kernel.get("sandbox") or {}))
    lines += _indent(_restart(kernel))
    if flow.get("disk_bytes") is not None:
        lines.append(f"  {_size(flow['disk_bytes'])} on disk")
    if flow.get("unwritten"):
        lines.append(f"  saved, not yet written to files: {_names(flow['unwritten'])}")
    lines += _indent(flow.get("hygiene") or [])
    return lines


def _sandbox(profile: dict[str, Any]) -> list[str]:
    """What confines the kernel, said either way round.

    An unconfined kernel is the line worth printing: a sandbox is only worth
    anything if its absence is as visible as its presence.
    """
    if not profile:
        return []
    if not profile.get("network_denied") and not profile.get("writes_confined"):
        return [f"not sandboxed · {profile.get('reason', 'no profile applied')}"]
    return [f"sandboxed · {profile.get('reason', profile.get('profile'))}"]


def _restart(kernel: dict[str, Any]) -> list[str]:
    """The one kernel control that surfaces: it is holding older packages."""
    if not kernel.get("restart_required"):
        return []
    return [f"restart the kernel to apply {_names(kernel.get('behind') or [])}"]


def _pending(pending: dict[str, Any]) -> list[str]:
    if not pending.get("recompute"):
        return []
    unknown = (
        f" ({_names(pending['unknown'])} never timed)" if pending.get("unknown") else ""
    )
    cost = (
        f"about {_seconds(pending['estimate_seconds'])}"
        if pending["estimate_seconds"]
        else "an unknown time"
    )
    return [
        "",
        f"running all of it recomputes {_names(pending['recompute'])} · "
        f"{cost}{unknown}",
    ]


def _block(block: dict[str, Any]) -> list[str]:
    kind = block.get("block")
    if kind == "markdown":
        return str(block.get("text", "")).splitlines()
    if kind == "kv":
        return [
            f"{name}: {value}" for name, value in (block.get("entries") or {}).items()
        ]
    if kind == "table":
        return _table(block)
    if kind == "series":
        total = block.get("total_points", len(block.get("points") or []))
        return [f"{block.get('name', 'series')}: {total} points"]
    if kind == "image":
        return [f"image ({block.get('mime', 'image')})"]
    if kind == "file":
        return [f"{block.get('name', 'file')} ({_size(block.get('size'))})"]
    return [f"({kind or 'unknown'} block)"]


def _table(block: dict[str, Any]) -> list[str]:
    columns = [str(name) for name in block.get("columns") or []]
    rows = block.get("rows") or []
    lines = [" | ".join(columns)] if columns else []
    lines += [" | ".join(str(value) for value in row) for row in rows[:_TABLE_ROWS]]
    total = block.get("total_rows")
    if total is not None and total > len(rows[:_TABLE_ROWS]):
        lines.append(f"… {total} rows in all")
    return lines


def _states(states: dict[str, int]) -> str:
    named = ", ".join(
        f"{count} {STATES[state]}"
        for state, count in sorted(states.items())
        if state != "synced"
    )
    return f" · {named}" if named else ""


def _causes(payload: dict[str, Any]) -> list[str]:
    return list(payload.get("causes") or [])


def _flags(payload: dict[str, Any]) -> list[str]:
    return [
        flag["detail"] or f"flagged: {flag['code']}"
        for flag in payload.get("flags") or []
    ]


def _note(entry: dict[str, Any]) -> str:
    if entry.get("note"):
        return "note"
    outputs = entry.get("outputs") or []
    return f"{len(outputs)} outputs" if len(outputs) > 1 else ""


def _indent(lines: Iterable[str]) -> list[str]:
    return [f"  {line}" for line in lines]


def _names(names: Iterable[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def _seconds(value: float | None) -> str:
    if value is None:
        return "unknown time"
    if value < 1:
        return f"{value:.2f}s"
    return f"{value:.1f}s"


def _size(value: int | None) -> str:
    if value is None:
        return "unknown size"
    size = float(value)
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
