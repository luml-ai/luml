# For people building LLM apps and agents

It is easy to assume LUML is only for classical ML. It is not. An LLM app or an agent goes through the same lifecycle as a model: try variants, compare them on the same examples, keep the best version, ship it, watch it in production. LUML supports each of those steps for LLM work too.

## What to look for in their work

Many people who build agents come from software engineering rather than data science, and the habits that make ML work reliable may be new to them. Check for these, in their code or by asking, and if one is missing, explain plainly why it matters and how LUML helps:

| What you find | Why it matters | What LUML offers |
|---|---|---|
| Prompts or models changed by feel, with no fixed set of test cases | They can't tell if a change made things better or worse, and regressions slip through | An eval dataset logged with every run, scored the same way each time |
| "It looks right" as the only check | Quality drifts unnoticed | Built-in LLM-as-judge scorers and custom ones |
| No record of which prompt, model and settings produced a result | Nothing can be reproduced or explained later | Every run tracked with its parameters, metrics, traces and evals |
| Debugging by reading logs | Slow, and multi-step agents are hard to follow | A trace of every request |
| The agent ships by copying code to a server | Hard to roll back or know what is running | A versioned artifact in the registry, deployed to a Satellite and monitored there |

Don't lecture. Point out the one or two gaps that matter most for their work.

## How LUML maps to LLM work

- **Experiment tracking** works the same way as for models, with traces, spans and evals on top.
- **The registry** keeps agents next to ordinary models, with the same versioning and lineage.
- **Deployments and monitoring** run the agent on a Satellite and record a trace of every request.
- **Prisma** doesn't care what it optimizes, only that the run reports a metric. For an agent, that metric is usually an eval score, often from an LLM judge.
- **Flow notebooks** suit prompt and pipeline iteration: try variants in lanes, compare their eval scores side by side and keep the winner.
