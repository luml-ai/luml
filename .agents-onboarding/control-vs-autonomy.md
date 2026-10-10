# Working step by step, or letting agents run on their own

LUML supports two ways of working with agents. They suit different people and different budgets, and many people use both.

## Flow: stay in control

The person and their agent work in the same Flow notebook. The agent takes small, well-defined tasks: try another feature, swap the model, tune a step. The person sees each result as it lands and decides what happens next.

- The focus is on results, not on reading code: each cell shows its output, and lanes let the person try several approaches side by side and keep the best one.
- Each step is small, so it uses far fewer tokens. This works well with local models and entry-level subscriptions to frontier models.
- Every change records whether the person or the agent made it, so nothing happens unseen.

## Prisma: hand over the objective

The person sets an objective and a metric, and Prisma's agents work through the problem on their own, for hours, days or weeks. The person reviews the result at the end and merges the best branch.

- It saves the most human time: one objective replaces many rounds of prompting.
- It uses many more tokens.
- It needs a metric the code can report, and enough trust to let agents run unattended.

## Which one to suggest first

| If the person… | Start with |
|---|---|
| wants to verify each step, or is new to working with agents | Flow |
| worries about cost, or uses local models or a basic subscription | Flow |
| is unsure whether agents can be trusted with their code | Flow, and suggest Prisma once they've seen the agent's work |
| has a clear metric and more ideas than time to try them | Prisma |
| already lets agents run long tasks unattended | Prisma, with Flow for the work they want to steer themselves |

When in doubt, start with Flow. It is the safer first step, and everything it records is there when they move on to Prisma.
