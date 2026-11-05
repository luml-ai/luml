# LUML Prisma

Prisma orchestrates coding agents on long-horizon tasks against a local Git repository. It runs as a local engine on your machine and pairs with a browser UI that tracks progress, streams live terminal output and merges the resulting branches back into the repository. All agent activity, intermediate files and Git operations stay on the local machine.

The main use case is automating multi-step machine learning experiments: an agent edits the code, runs the training script, captures metrics, and either retries on failure or forks the experiment with alternative ideas. The same engine runs single-step tasks for ad-hoc code changes.

A [LUML](https://luml.ai) account is not required. It is only needed to upload the produced models and experiment data to a LUML collection.

## Installation

```bash
pip install luml-prisma
```

Prisma drives external coding CLIs rather than calling LLM APIs directly. At least one supported CLI, such as [Claude Code](https://www.anthropic.com/claude-code) or [Codex](https://github.com/openai/codex), must be installed and available on `PATH`, with its own authentication and quota.

## Usage

Start the engine. It listens on `http://localhost:8420`:

```bash
luml-prisma
```

Then open the UI at [app.luml.ai/prisma](https://app.luml.ai/prisma). It connects to the local engine over HTTP and WebSockets; the engine's address can be changed from the offline screen or the indicator in the page header.

In the UI:

1. Add a repository: a local Git repository, with or without a remote.
2. Create a **workflow** to optimize a metric over many iterations, or a **task** for a single change. Each run works in its own Git worktree on a `prisma/` branch.
3. Follow the runs on the board and merge the branches you want to keep.

## Configuration

The engine keeps its database, sessions and custom agents in `~/.luml/prisma`. `LUML_PRISMA_DATA_DIR` points it at another directory, and `config.toml` in that directory overrides the defaults. `LUML_PRISMA_CORS_ORIGINS` sets the origins allowed to reach the engine, separated by commas.

## Documentation

- [Overview](https://docs.luml.ai/apps/prisma/overview)
- [Repositories](https://docs.luml.ai/apps/prisma/repositories)
- [Workflows](https://docs.luml.ai/apps/prisma/workflows)
- [Tasks](https://docs.luml.ai/apps/prisma/tasks)
- [Sessions](https://docs.luml.ai/apps/prisma/sessions)
- [Board](https://docs.luml.ai/apps/prisma/board)
