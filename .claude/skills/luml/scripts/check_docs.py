#!/usr/bin/env python3
"""Check this skill's references against the LUML source: do the documented
symbols, methods and keyword arguments still exist?

The references quote a lot of API surface, and the surface moves. This is the
check that catches silent rot - a renamed method or a dropped keyword argument
that the skill would otherwise keep recommending.

    python .claude/skills/luml/scripts/check_docs.py          # from the repo root
    python check_docs.py --repo /path/to/dataforce.studio

Exit code 0 when everything in the docs resolves, 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import re
import sys
from pathlib import Path

# Which object each `foo.bar(...)` example in the docs is talking about.
# Per file, because `luml` is the SDK module in one set of docs and the client
# instance in the other.
ROOTS: dict[str, dict[str, str]] = {
    "flow-tracking.md": {
        "tracker": "luml.experiments.tracker:ExperimentTracker",
    },
    "evals-tracing.md": {
        "tracker": "luml.experiments.tracker:ExperimentTracker",
    },
    "artifacts.md": {
        "tracker": "luml.experiments.tracker:ExperimentTracker",
        "ds": "luml.artifacts.dataset:MaterializedDataset",
        "card": "luml.card.builder:CardBuilder",
        "model_ref": "luml.artifacts.model:ModelReference",
        "dataset_ref": "luml.artifacts.dataset:DatasetReference",
    },
    "core-api.md": {
        "luml.artifacts": "luml_api.resources.artifacts:ArtifactResource",
        "luml.collections": "luml_api.resources.collections:CollectionResource",
        "luml.tracks": "luml_api.resources.tracks:TrackResource",
        "luml.deployments": "luml_api.resources.deployments:DeploymentResource",
        "luml.organizations": "luml_api.resources.organizations:OrganizationResource",
        "luml.orbits": "luml_api.resources.orbits:OrbitResource",
        "luml.bucket_secrets": "luml_api.resources.bucket_secrets:BucketSecretResource",
        "monitoring": "luml_api.resources.monitoring:DeploymentMonitoring",
        # the async client mirrors the sync one and adds setup_config; the docs
        # use the name `luml` for whichever is in scope
        "luml": "luml_api:LumlClient|luml_api:AsyncLumlClient",
    },
    "repro.md": {},
}

# Module-level functions documented as bare calls.
BARE_FUNCTIONS = {
    "save_tabular_dataset": "luml",
    "save_hf_dataset": "luml",
    "load_dataset": "luml",
    "save_experiment": "luml",
    "evaluate": "luml.experiments.evaluation.evaluate",
}

CALL_RE = re.compile(r"\b((?:\w+\.)*\w+)\(")
IMPORT_RE = re.compile(
    r"^\s*from\s+([\w.]+)\s+import\s+(?:\(([^)]*)\)|([^(\n]+))", re.M
)
KWARG_RE = re.compile(r"(?:^|[,(])\s*(\w+)\s*=")

failures: list[str] = []
checked = {"imports": 0, "calls": 0, "kwargs": 0}


def fail(doc: str, message: str) -> None:
    failures.append(f"{doc}: {message}")


def resolve(target: str) -> list:
    """One target may list several acceptable owners, separated by '|'."""
    owners = []
    for part in target.split("|"):
        module_name, _, attr = part.partition(":")
        module = importlib.import_module(module_name)
        owners.append(getattr(module, attr) if attr else module)
    return owners


def _imported_names(names: str) -> list[str]:
    """Names out of an import list, minus the trailing `# ...` comments."""
    cleaned = "\n".join(line.split("#")[0] for line in names.splitlines())
    return [n.strip() for n in cleaned.split(",") if n.strip()]


def args_of(text: str, start: int) -> str | None:
    """Return the argument text of a call whose '(' is at `start`."""
    depth = 0
    for i in range(start, min(len(text), start + 4000)):
        if text[i] in "([{":
            depth += 1
        elif text[i] in ")]}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return None


def check_kwargs(doc: str, owner: object, name: str, arg_text: str) -> None:
    func = getattr(owner, name, None)
    if func is None or not callable(func):
        return
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return
    if any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values()):
        return  # **kwargs swallows anything
    known = set(sig.parameters)
    for kwarg in KWARG_RE.findall(arg_text):
        checked["kwargs"] += 1
        if kwarg not in known:
            fail(doc, f"{name}(...) has no parameter '{kwarg}' "
                      f"(has: {', '.join(sorted(known - {'self'}))})")


def check_file(path: Path) -> None:
    doc = path.name
    text = path.read_text()
    roots = ROOTS.get(doc, {})

    for module_name, parenthesised, inline in IMPORT_RE.findall(text):
        names = parenthesised or inline
        if not module_name.startswith(("luml", "luml_api")):
            continue
        checked["imports"] += 1
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            fail(doc, f"cannot import {module_name}: {exc}")
            continue
        for name in _imported_names(names):
            if not hasattr(module, name):
                fail(doc, f"{module_name} has no '{name}'")

    for match in CALL_RE.finditer(text):
        dotted = match.group(1)
        owner_path, _, name = dotted.rpartition(".")
        arg_text = args_of(text, match.end() - 1) or ""

        if not owner_path:
            module_name = BARE_FUNCTIONS.get(name)
            if module_name is None:
                continue
            checked["calls"] += 1
            module = importlib.import_module(module_name)
            if not hasattr(module, name):
                fail(doc, f"{module_name} has no function '{name}'")
            else:
                check_kwargs(doc, module, name, arg_text)
            continue

        target = roots.get(owner_path)
        if target is None:
            continue
        checked["calls"] += 1
        owners = resolve(target)
        match_ = next((o for o in owners if hasattr(o, name)), None)
        if match_ is None:
            fail(doc, f"{target} has no attribute '{name}'")
        else:
            check_kwargs(doc, match_, name, arg_text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=None, help="repo root (default: inferred)")
    args = parser.parse_args()

    here = Path(__file__).resolve()
    repo = Path(args.repo) if args.repo else next(
        (p for p in here.parents if (p / "sdk" / "python" / "api").is_dir()), None
    )
    if repo is None:
        print("could not find the repo root; pass --repo", file=sys.stderr)
        return 2
    sys.path.insert(0, str(repo / "sdk" / "python" / "api"))
    sys.path.insert(0, str(repo / "sdk" / "python" / "sdk"))

    references = here.parent.parent / "references"
    for path in sorted(references.glob("*.md")):
        check_file(path)

    print(f"checked {checked['imports']} imports, {checked['calls']} calls, "
          f"{checked['kwargs']} keyword arguments")
    if failures:
        print(f"\n{len(failures)} problem(s):", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("references match the source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
