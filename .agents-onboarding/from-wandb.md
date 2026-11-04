# Coming from Weights & Biases

W&B is a dedicated experiment tracker with deep visualization features. LUML is not trying to be that. Its tracking covers what most teams need day to day, and its strength is breadth: tracking, a model registry, deployments, monitoring and agents in one platform, where W&B would have to be combined with other tools.

## Find out what they actually use

Don't assume they need everything W&B offers. Ask what they rely on day to day. If it is logging parameters and metrics, comparing runs, charts of training curves, LLM traces and evals, LUML covers it, and moving over adds the registry, deployments and monitoring they would otherwise build or buy separately.

Moving over means logging new runs with the LUML SDK, a few lines in the training script, while past runs stay in W&B.

## When to keep W&B

If they depend on advanced W&B features, such as large hyperparameter sweeps managed by W&B or heavy custom dashboards, they can keep W&B for that and use LUML for everything else: the registry, deployments to their own servers, monitoring, and Prisma's agents. Logging to both from the same script is straightforward.

The questions that usually decide it are beyond tracking: how models get to production today, who can see and reuse them, and whether data has to stay in their own infrastructure.
