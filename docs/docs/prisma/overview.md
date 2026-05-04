---
sidebar_position: 1
---

# Prisma

Prisma orchestrates coding agents to work on long-horizon tasks against a local Git repository. It runs as a local server on the user's machine and pairs with a browser UI that tracks progress, streams live terminal output, and merges resulting branches back into the source repository. All agent activity, intermediate files, and Git operations stay on the local machine.

The intended use case is automating multi-step machine learning experiments. An agent edits the code, runs the training script, captures metrics, and either retries on failure or forks the experiment with alternative ideas. The same engine also drives single-step tasks for ad-hoc code changes.

*Note: a LUML account is not required to use Prisma. An account is only relevant for uploading produced artifacts (trained models and experiment data) to a [Collection](../documentation/Modules/Registry/registry.md#collections). Without an account, Prisma operates entirely against the local repository.*

## Installation

Prisma is distributed on PyPI as the `luml-prisma` package.

```shell
pip install luml-prisma
```

Starting the engine launches a local server on `http://localhost:8420`:

```shell
luml-prisma
```

The browser UI is hosted at [app.luml.ai/prisma](https://app.luml.ai/prisma) and connects to the local engine over HTTP and WebSockets when opened. If the default port is unavailable or the engine runs on a different host, the connection URL can be changed from the offline screen or via the indicator in the page header.

## Coding Agents

Prisma drives external coding CLIs rather than calling LLM APIs directly. At least one supported CLI must be installed and available on the system `PATH`. The list of agents shown in the creation forms is determined at startup; the engine inspects `PATH` and lists only the CLIs that are actually present.

Supported agents include [Claude Code](https://www.anthropic.com/claude-code) and [Codex](https://github.com/openai/codex). Each agent is used through its own CLI configuration, including authentication and quota; Prisma does not manage agent credentials. A coding CLI typically requires its own subscription or API access with enough quota to cover the run.

When **auto mode** is enabled for a workflow, Prisma starts the agent CLI in its bypass-permissions mode and lets it operate without prompting. Auto mode is intended for sandboxed environments. Coding CLIs do not signal completion explicitly in their interactive form, so Prisma uses an inactivity heuristic: when the visible terminal output stops changing for a configured timeout, the agent is treated as done. Most agent CLIs emit a status indicator (such as a running timer) while active, which makes a stretch of unchanged output a strong signal that the run has finished.
