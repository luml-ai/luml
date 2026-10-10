# Coming from MLflow

MLflow and Flow are close in how they work, and moving between them is easy. MLflow often works well for one person on one machine; it gets harder when a team needs to share runs, which usually means running and maintaining a tracking server.

## Moving over

The `luml-mlflow` plugin makes LUML an MLflow backend. The project keeps calling the MLflow API and changes only the tracking URI:

- `luml://local` writes runs to the local store that Flow reads, so they appear in `lumlflow ui`.
- `luml://<org>/<orbit>` also syncs each finished run, models included, to the team's orbit on the platform.

Nothing else in the training code changes, so trying it is low-risk.

## What changes for them

- **No local-or-remote decision.** With MLflow, a project usually logs either to a local store or to a shared server. With LUML they keep working in Flow locally and upload what matters to the team; the two are meant to be used together.
- **Teams out of the box.** Organizations, orbits and roles, without running a tracking server.
- **Beyond tracking.** The same platform registers models as self-contained artifacts, deploys them to their own servers in one step and monitors them there.
- **Agents.** Their MLflow-tracked project can also use Flow notebooks and Prisma.

Guide: https://docs.luml.ai/guides/Integrations/mlflow_tutorial
