"""Read LLM traces and eval results out of the local LUML Flow store.

Bridges the gap left by `luml-inspect`, which exposes metrics/params/evals but
not traces. Meant for humans and for Prisma coding agents diagnosing why the
judge scored an output poorly.

Usage :
    uv run python traces.py summary [-e EXPERIMENT]
    uv run python traces.py worst   [-e EXPERIMENT] [-n 3] [--metric correctness] [--full]
    uv run python traces.py show    -t TRACE_ID [-e EXPERIMENT] [--full]

EXPERIMENT may be a full id or a unique prefix; it defaults to the most recent
experiment in GROUP (falling back to the most recent experiment overall).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from luml.experiments.backends.data_types import SpanRecord
from luml.experiments.tracker import ExperimentTracker

GROUP = "CHANGE-ME"  # set to the experiment group your eval script uses
TRUNCATE = 400


def store_uri() -> str:
    raw = (
        os.environ.get("LUML_BACKEND_STORE_URI")
        or os.environ.get("BACKEND_STORE_URI")
        or f"{Path.home()}/.luml/experiments"
    )
    path = raw.split("://", 1)[-1]
    return f"sqlite://{Path(path).expanduser()}"


def resolve_experiment(
    tracker: ExperimentTracker, ref: str | None, group: str | None = None
) -> str:
    experiments = tracker.list_experiments()
    if ref:
        matches = [e for e in experiments if e.id.startswith(ref)]
        if not matches:
            sys.exit(f"No experiment matching '{ref}' in {store_uri()}")
        if len(matches) > 1:
            sys.exit(f"Ambiguous experiment prefix '{ref}': {[e.id for e in matches]}")
        return matches[0].id
    if not experiments:
        sys.exit(f"No experiments in {store_uri()} yet.")
    group_name = group or GROUP
    groups = {g.id: g.name for g in tracker.list_groups()}
    in_group = [
        e for e in experiments if e.group_id and groups.get(e.group_id) == group_name
    ]
    candidates = in_group or experiments
    return max(candidates, key=lambda e: e.created_at).id


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


def _clip(text: str, full: bool) -> str:
    text = str(text).strip()
    if full or len(text) <= TRUNCATE:
        return text
    return text[:TRUNCATE] + f"... [{len(text)} chars, use --full]"


def _indexed_messages(attrs: dict[str, Any], prefix: str) -> list[tuple[str, str]]:
    """Collect legacy flattened messages: gen_ai.prompt.0.role/.content."""
    messages: dict[int, dict[str, str]] = {}
    for key, value in attrs.items():
        if not key.startswith(prefix + "."):
            continue
        parts = key[len(prefix) + 1 :].split(".", 1)
        if len(parts) == 2 and parts[0].isdigit():
            messages.setdefault(int(parts[0]), {})[parts[1]] = str(value)
    return [
        (m.get("role", "?"), m.get("content", ""))
        for _, m in sorted(messages.items())
        if m.get("content")
    ]


def _structured_messages(attrs: dict[str, Any], key: str) -> list[tuple[str, str]]:
    """Collect new-convention messages: gen_ai.input.messages / gen_ai.output.messages,
    a JSON list of {"role": ..., "parts": [{"content": ..., "type": "text"}]}."""
    raw = attrs.get(key)
    if not raw:
        return []
    try:
        entries = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return []
    messages: list[tuple[str, str]] = []
    for entry in entries:
        content = " ".join(
            str(part.get("content", ""))
            for part in entry.get("parts", [])
            if part.get("content")
        )
        if content:
            messages.append((entry.get("role", "?"), content))
    return messages


def _llm_messages(
    attrs: dict[str, Any],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    inputs = _structured_messages(attrs, "gen_ai.input.messages") or _indexed_messages(
        attrs, "gen_ai.prompt"
    )
    outputs = _structured_messages(attrs, "gen_ai.output.messages") or _indexed_messages(
        attrs, "gen_ai.completion"
    )
    return inputs, outputs


def _duration_ms(span: SpanRecord) -> float:
    return (span.end_time_unix_nano - span.start_time_unix_nano) / 1e6


def print_span_tree(spans: list[SpanRecord], full: bool, indent: str = "") -> None:
    children: dict[str | None, list[SpanRecord]] = {}
    for span in spans:
        children.setdefault(span.parent_span_id, []).append(span)
    for sibling_group in children.values():
        sibling_group.sort(key=lambda s: s.start_time_unix_nano)

    def render(span: SpanRecord, depth: int) -> None:
        attrs = _as_dict(span.attributes)
        pad = indent + "  " * depth
        model = attrs.get("gen_ai.request.model") or attrs.get("gen_ai.response.model")
        label = f" [{model}]" if model else ""
        status = " ERROR" if span.status_code == 2 else ""
        print(f"{pad}{span.name}{label}  {_duration_ms(span):.0f}ms{status}")
        inputs, outputs = _llm_messages(attrs)
        for role, content in inputs:
            print(f"{pad}  {role}> {_clip(content, full)}")
        for _, content in outputs:
            print(f"{pad}  assistant< {_clip(content, full)}")
        for key in sorted(attrs):
            # project-specific span attributes worth surfacing; extend as needed
            if key.startswith(("retrieval.", "eval.score.")):
                print(f"{pad}  {key} = {attrs[key]}")
        usage = {
            k.removeprefix("gen_ai.usage.").removeprefix("llm.usage."): v
            for k, v in attrs.items()
            if k.startswith(("gen_ai.usage.", "llm.usage.")) and v
        }
        if usage:
            print(f"{pad}  tokens: {usage}")
        for child in children.get(span.span_id, []):
            render(child, depth + 1)

    for root in children.get(None, []):
        render(root, 0)


def cmd_summary(tracker: ExperimentTracker, exp_id: str) -> None:
    record = tracker.get_experiment_record(exp_id)
    print(f"Experiment {exp_id}  name={record.name if record else '?'}")
    print(f"Average scores: {tracker.get_experiment_evals_average_scores(exp_id)}")

    durations: dict[str, list[float]] = {}
    traces = tracker.get_experiment_traces_all(exp_id)
    for trace_record in traces:
        details = tracker.get_trace(exp_id, trace_record.trace_id)
        if not details:
            continue
        for span in details.spans:
            durations.setdefault(span.name, []).append(_duration_ms(span))
    print(f"\n{len(traces)} traces. Mean duration per step:")
    for name, values in sorted(durations.items()):
        print(f"  {name:<24} {sum(values) / len(values):>7.0f}ms  (n={len(values)})")


def cmd_worst(
    tracker: ExperimentTracker, exp_id: str, n: int, metric: str, full: bool
) -> None:
    evals = tracker.get_experiment_evals_all(exp_id)
    if not evals:
        sys.exit(f"No evals logged for experiment {exp_id}")
    scored = [e for e in evals if isinstance(_as_dict(e.scores).get(metric), int | float)]
    if not scored:
        available = sorted(_as_dict(evals[0].scores))
        sys.exit(f"No '{metric}' score found. Available: {available}")
    scored.sort(key=lambda e: _as_dict(e.scores)[metric])

    for eval_record in scored[:n]:
        scores = _as_dict(eval_record.scores)
        metadata = _as_dict(eval_record.metadata)
        print("=" * 72)
        print(
            f"{eval_record.id}  "
            + "  ".join(f"{k}={v}" for k, v in sorted(scores.items()))
        )
        inputs = _as_dict(eval_record.inputs)
        print(f"\ninputs: {_clip(json.dumps(inputs), full)}")
        expected = _as_dict(eval_record.refs).get("expected")
        if expected:
            print(f"\nexpected: {json.dumps(expected, indent=2)}")
        reply = _as_dict(eval_record.outputs).get("response", "")
        print(f"\noutput: {_clip(reply, full)}")
        for key, value in sorted(metadata.items()):
            if key.endswith("_reasoning"):
                print(f"\njudge ({key}): {_clip(value, full)}")
        for trace_id in eval_record.trace_ids or []:
            details = tracker.get_trace(exp_id, trace_id)
            if details:
                print(f"\ntrace {trace_id}:")
                print_span_tree(details.spans, full, indent="  ")
        print()


def cmd_show(tracker: ExperimentTracker, exp_id: str, trace_ref: str, full: bool) -> None:
    trace_ids = [t.trace_id for t in tracker.get_experiment_traces_all(exp_id)]
    matches = [t for t in trace_ids if t.startswith(trace_ref)]
    if len(matches) != 1:
        sys.exit(f"Trace '{trace_ref}' matched {len(matches)} traces in {exp_id}")
    details = tracker.get_trace(exp_id, matches[0])
    if details is None:
        sys.exit(f"Trace {matches[0]} not found")
    print(f"trace {matches[0]}:")
    print_span_tree(details.spans, full, indent="  ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["summary", "worst", "show"])
    parser.add_argument("-e", "--experiment", default=None, help="experiment id or prefix")
    parser.add_argument("-g", "--group", default=None, help="experiment group name")
    parser.add_argument("-n", type=int, default=3, help="worst: number of evals")
    parser.add_argument("--metric", default="correctness", help="worst: sort metric")
    parser.add_argument("-t", "--trace", default=None, help="show: trace id or prefix")
    parser.add_argument("--full", action="store_true", help="do not truncate content")
    args = parser.parse_args()

    tracker = ExperimentTracker(store_uri())
    exp_id = resolve_experiment(tracker, args.experiment, args.group)

    if args.command == "summary":
        cmd_summary(tracker, exp_id)
    elif args.command == "worst":
        cmd_worst(tracker, exp_id, args.n, args.metric, args.full)
    else:
        if not args.trace:
            sys.exit("show requires -t TRACE_ID")
        cmd_show(tracker, exp_id, args.trace, args.full)


if __name__ == "__main__":
    main()
