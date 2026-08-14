"""The Tier-0 release gate: can an agent drive this from the quickstart alone?

The contract the whole CLI is measured against says a Haiku-class agent, given
nothing but the ~20-line quickstart in the generated `AGENTS.md`, completes
edit → run → inspect → fix-a-failure. This harness is the scripted stand-in for
that agent: it reads the quickstart, and may then use only the commands the
quickstart names. Any verb it needs that the quickstart never mentioned is a
gate failure — that is what "three gestures" has to mean to be worth claiming.

Two things are checked as it goes. Whether the loop completes at all, and
whether every word the CLI said back was one the agent could act on: uids,
content hashes and memo keys never appear outside `--json`, so a run that leaks
one fails the gate however well the loop went.

    python dev/tier0_gate/harness.py            # against a temp workspace
    python dev/tier0_gate/harness.py --keep     # …and leave it behind to read

`lumlflow/tests/test_tier0_gate.py` runs the same function in CI.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
SHA256 = re.compile(r"\b[0-9a-f]{64}\b")
COMMAND = re.compile(r"`lumlflow ([a-z]+(?: [a-z]+)?)")

# The one place the printed form shows an identifier: the cell file itself,
# echoed for the agent to edit, uid line and all.
SOURCE_RULE = "─" * 60

BROKEN = '''\
class Score:
    """The headline metric."""

    produces = {"summary": "asset"}

    def materialize(self, ctx):
        return {"summary": {"auc": total / count}}
'''

FIXED = '''\
class Score:
    """The headline metric."""

    produces = {"summary": "asset"}

    def materialize(self, ctx):
        return {"summary": {"auc": 0.91}}
'''


@dataclass
class Step:
    argv: list[str]
    code: int
    output: str


@dataclass
class Report:
    steps: list[Step] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    quickstart_lines: int = 0
    vocabulary: set[str] = field(default_factory=set)

    @property
    def passed(self) -> bool:
        return not self.failures

    def summary(self) -> str:
        lines = [
            f"{len(self.steps)} commands, "
            f"quickstart {self.quickstart_lines} lines, "
            f"{len(self.vocabulary)} verbs used",
            *(f"  FAIL {failure}" for failure in self.failures),
        ]
        return "\n".join([*lines, "PASS" if self.passed else "FAIL"])


class Agent:
    """A scripted agent: it runs verbs, reads answers, and checks the words."""

    def __init__(self, workspace: Path, report: Report) -> None:
        self.workspace = workspace
        self.report = report
        self.allowed: set[str] = set()

    def run(self, *argv: str, expect: int | None = 0) -> Step:
        completed = subprocess.run(
            [sys.executable, "-m", "lumlflow.cli", *argv],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        step = Step(
            argv=list(argv),
            code=completed.returncode,
            output=completed.stdout + completed.stderr,
        )
        self.report.steps.append(step)
        self._check(step, expect)
        return step

    def _check(self, step: Step, expect: int | None) -> None:
        verb = " ".join(word for word in step.argv if not word.startswith("-"))
        if expect is not None and step.code != expect:
            self.report.failures.append(
                f"`lumlflow {verb}` exited {step.code}, expected {expect}:"
                f"\n{step.output}"
            )
        if self.allowed and not self._documented(step.argv):
            self.report.failures.append(
                f"`lumlflow {verb}` is not in the quickstart — Tier-0 is what the "
                "quickstart teaches, and nothing else"
            )
        if "--json" in step.argv:
            return
        spoken = step.output.split(SOURCE_RULE)[0]
        leaked = ULID.findall(spoken) + SHA256.findall(spoken)
        if leaked:
            self.report.failures.append(
                f"`lumlflow {verb}` printed internals: {sorted(set(leaked))}"
            )

    def _documented(self, argv: list[str]) -> bool:
        words = [word for word in argv if not word.startswith("-")]
        return bool(words) and (
            words[0] in self.allowed or " ".join(words[:2]) in self.allowed
        )

    def learn(self, quickstart: str) -> None:
        """Take the verbs from the quickstart. Nothing else may be used after."""
        self.allowed = set(COMMAND.findall(quickstart))
        self.report.vocabulary = self.allowed


def gate(workspace: Path) -> Report:
    """Drive edit → run → inspect → fix → rerun, from the quickstart alone."""
    report = Report()
    agent = Agent(workspace, report)

    # Everything before the agent reads the quickstart is the human's setup.
    agent.run("init", "churn")
    quickstart = _quickstart(workspace / "AGENTS.md")
    report.quickstart_lines = len(quickstart.strip().splitlines())
    if not quickstart:
        report.failures.append("no quickstart in the generated AGENTS.md")
        return report
    agent.learn(quickstart)

    cells = workspace / "churn.flow" / "cells"
    cells.mkdir(parents=True, exist_ok=True)
    (cells / "score.py").write_text(BROKEN, encoding="utf-8")

    failed = agent.run("run", "score", expect=1)
    _expect(report, "the failure names the cell", "score" in failed.output)

    status = agent.run("status")
    _expect(report, "`status` says a cell failed", "failed" in status.output)

    brief = agent.run("context")
    _expect(
        report,
        "the traceback reaches the agent",
        "NameError" in brief.output or "not defined" in brief.output,
    )

    (cells / "score.py").write_text(FIXED, encoding="utf-8")
    fixed = agent.run("run", "score")
    _expect(report, "the fix runs", "score" in fixed.output)

    settled = agent.run("status")
    _expect(report, "the cell is current afterwards", "current" in settled.output)

    checked = agent.run("context", "--json")
    payload = json.loads(checked.output)
    _expect(report, "nothing is left unsynced", payload["unsynced"] == [])
    _expect(report, "the failure is behind us", payload["failures"] == [])
    return report


def _quickstart(agents_md: Path) -> str:
    if not agents_md.exists():
        return ""
    text = agents_md.read_text("utf-8")
    start = text.find("## lumlflow quickstart")
    if start == -1:
        return ""
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def _expect(report: Report, what: str, held: bool) -> None:
    if not held:
        report.failures.append(what)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tier0_gate")
    parser.add_argument("--workspace", default=None, help="where to run the gate")
    parser.add_argument(
        "--keep", action="store_true", help="leave the temp workspace behind"
    )
    args = parser.parse_args(argv)
    workspace = Path(args.workspace) if args.workspace else Path(tempfile.mkdtemp())
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        report = gate(workspace)
        print(report.summary())
        return 0 if report.passed else 1
    finally:
        # The daemon outlives the verbs that started it, so it has to be asked
        # to go before the directory it owns is taken away underneath it.
        stop_daemon(workspace)
        if args.keep or args.workspace is not None:
            print(f"workspace: {workspace}")
        else:
            shutil.rmtree(workspace, ignore_errors=True)


def stop_daemon(workspace: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "lumlflow.cli", "daemon", "stop"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
