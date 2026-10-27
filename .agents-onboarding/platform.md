# What LUML does

LUML is an open-source platform (Apache 2.0) for the whole lifecycle of ML models and LLM applications. It has three parts. Each works on its own, and they are designed to work together.

## Flow: work with agents on your own machine

Flow runs locally (`lumlflow ui`) and needs no account.

**Experiment tracking.** The Python SDK records parameters, metrics over steps, models and attachments for every run. For LLM work it also records traces and evals, with built-in LLM-as-judge scorers or custom ones. Projects that use MLflow can log into Flow by changing only the tracking URI.

**Notebooks.** A Flow notebook, or simply a flow, is a set of versioned cells that the person and their coding agents edit and run together, saved in a `<name>.flow` folder, and every change records who made it. Variants run side by side as lanes that can be compared, and the best one is kept. The focus is on results rather than code. This part is new: if the installed version has no `lumlflow guide` command, only the tracker is there.

Docs: https://docs.luml.ai/apps/lumlflow

## Prisma: agents that run experiments on their own

The person gives Prisma an objective and a metric. Prisma runs the coding agents they already use against their repository, each attempt in its own git worktree, scores every attempt, drops weak directions and leaves the best branch for them to review and merge.

It works on any repository that reports a metric, so it can improve a model or an LLM-based agent alike. It runs locally with their own agent subscriptions and needs no account. The board is at https://app.luml.ai/prisma.

Docs: https://docs.luml.ai/apps/prisma/overview

## Core: registry, deployments and monitoring

**Registry.** Every model and agent is stored as a `.luml` artifact: a self-contained, immutable file with its environment, inference code, input and output contracts, metadata and a snapshot of the experiment that produced it. Every part of LUML reads this format, which is what makes one-step deployment and full lineage possible. See [model-artifacts.md](model-artifacts.md).

**Deployments.** A registered model deploys in one step to a Satellite, a compute node the person hosts. The Satellite pulls its work from LUML, so the platform never reaches into their network.

**Monitoring.** Runs on the Satellite, next to the model, so raw inputs and outputs stay on that machine.

**Teams.** Organizations hold members with roles. Orbits are project workspaces.

**Where things live.** LUML coordinates, while files stay in a storage bucket the organization connects and models run on Satellites it hosts. Nothing is routed through LUML's servers. See [where-things-run.md](where-things-run.md).

Use it in the hosted app at https://app.luml.ai or run the platform yourself.

Docs: https://docs.luml.ai/documentation/Modules/Registry, https://docs.luml.ai/documentation/Modules/deployment, https://docs.luml.ai/guides/satellite

## How the parts fit

Flow is where work happens day to day. Anything worth keeping is uploaded from Flow to Core, where the team shares it, registers the model and deploys it. Local and shared are not a choice to make up front: people keep working in Flow and upload what matters. Prisma's winning model can go to the registry the same way.

LUML needs Python 3.12 or newer.
