---
sidebar_position: 3
---

# Experiment Snapshots

The Experiment Snapshots module implements *Experiment Tracking* functionality. 
It preserves the history of model runs, allowing for performance evolution analysis and configuration benchmarking.

## Functionality:

1. **History**

Retention of results for each individual run.

2. **Visualization**

Graphical representation of metric trends and summary tables.

3. **Reproducibility**

Since the experiment snapshot is intrinsically linked to the saved model file (.dfs), this allows for the precise reproduction of experimental conditions. 
Users can revert to any previous model version and re-run it to verify results.

### LLM Tracing
For Large Language Models (LLMs), an advanced analysis mode—Tracing—is available within Experiment Snapshots. 
It enables a detailed breakdown of the response generation process.

Tracing tools include:
- *Trace View* - visualization of all intermediate execution steps (chain of thought, tool calls, vector database queries).
- *Step Attributes* - detailed technical information on each processing node (input/output tokens, latency, used prompts).
- *Scoring* - generation quality assessment using Expected Result metrics or an automated LLM-judge.