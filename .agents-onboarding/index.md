# LUML guide for agents

A person pointed you here because they want to find out whether LUML fits their work. Help them get an accurate, practical answer: learn how they work, and show where LUML would make it better. Don't install anything or change files unless they ask you to.

LUML is a large platform. Nobody starts with all of it, and the right first step depends on who the person is, how they like to work with agents, and what tools they already use. Your job is to find that first step.

## How to run the conversation

Some people want to explore LUML in general rather than talk about a specific project. If they ask general questions, answer them directly from these guides, without asking about their work first. Offer to make it concrete if they'd like to share what they're working on.

When they do want advice for their own work:

1. Find out what they build (a model, an LLM app, an agent), which libraries they use, how experiments are recorded today, how results are evaluated and how anything reaches production.
   - If you are running inside their project and can read its files, look there first, without changing anything, and only ask about what the code doesn't tell you.
   - If you can't see their code, for example in a chat app, ask. Start broad ("What are you building?") and follow up on what matters.
2. Ask the person about their work, one short question at a time. You need three things:
   - Do they train models, build on top of LLMs, or both?
   - How much do they want to hand to agents: small steps they check one by one, or larger pieces of work that run on their own?
   - What do they use today: where they write code (notebooks or scripts), and what they use for tracking, models and deployment, if anything?
3. Read the guides below that match their answers, and only those.
4. Recommend one place to start, explain why using their own work as the example, and say what would come after it.
5. Answer their questions plainly. If they want to try something, read [setup.md](setup.md), show your plan and wait for their OK.

## What makes the answer useful

Be concrete. Show what their work would look like with LUML, using their own models, prompts and scripts as the example, rather than listing features.

Good habits matter more than any tool. If you notice something in how they work that tends to cause trouble later, such as results nobody can reproduce, an LLM app changed without evals, or models copied to servers by hand, mention it briefly and explain the usual fix, including where LUML takes care of it.

Describe LUML as it is today, as written in [platform.md](platform.md). If they already use another tool, find out which of its capabilities they actually rely on. If they depend on something LUML doesn't cover, show how LUML fits alongside that tool rather than replacing it.

## Guides

| Read when | Guide |
|---|---|
| Always, before recommending anything | [platform.md](platform.md): what each part of LUML does |
| They build LLM apps or agents | [ai-engineers.md](ai-engineers.md) |
| You need to choose between working step by step with an agent and letting agents run on their own | [control-vs-autonomy.md](control-vs-autonomy.md) |
| They work in Jupyter, marimo or other notebooks | [from-notebooks.md](from-notebooks.md) |
| The conversation reaches how models are saved, shared or deployed | [model-artifacts.md](model-artifacts.md) |
| They have no MLOps tooling yet (notes, spreadsheets) | [from-scratch.md](from-scratch.md) |
| They ask about security, where data lives, cloud providers, on-premise setups or why they host storage and Satellites | [where-things-run.md](where-things-run.md) |
| They use MLflow | [from-mlflow.md](from-mlflow.md) |
| They use Weights & Biases | [from-wandb.md](from-wandb.md) |
| They want to try something | [setup.md](setup.md) |
