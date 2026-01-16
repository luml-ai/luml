---
sidebar_label: 'Experiment Tracking'
sidebar_position: 2
title: Experiment Tracking
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Experiment Tracking

## Experiment Snapshots
The Experiment Snapshots module enables structured logging and management of machine learning experiment runs, providing a consistent way to capture results, visualize them through interactive graphs and tables, and compare model performance (across the experiment runs).

### Purpose:
1. History Retention  
Persistent storage of metrics, parameters, artifacts, and metadata for every run, allowing users to trace how results evolved over time and revisit past configurations when needed.

2. Interactive Visualizations  
Interactive charts and comparison tables that highlight performance trends, surface differences between configurations, and make it easier to compare model runs.

3. Reproducibility  
Since the experiment snapshot is intrinsically linked to the saved model file (.luml), this allows for the precise reproduction of experimental conditions. Users can revert to any previous model version and re-run it to verify results.

## LLM Tracing 
LLM Tracing provides visibility into the execution flow of systems that use large language models. It records key information such as inputs, outputs, and metadata associated with each step of the LLM call. It makes it easier to inspect, debug, monitor, and optimize generative AI workflows.

The main module components are:

The main module components are:

<Tabs>
  <TabItem value="high-level" label="High-level view" default>
    
    ### Aggregated run summary
    
    Concise overview of each run, showing the main inputs and outputs alongside key metadata and evaluation scores. Useful for quickly comparing results and spotting regressions without diving into execution details.
    
    
  </TabItem>
  
  <TabItem value="traces" label="Traces">
    
    ### Complete interaction history
    
    Full record of every intermediate step that contributes to an output, including prompts, model parameters, tool calls, database lookups, and so on. Traces reveal the end-to-end flow of a request, making it easier to locate bottlenecks and understand how configuration choices affect cost, performance, and output quality.
    
    
  </TabItem>
  
  <TabItem value="metrics" label="Metrics">
    
    ### Usage and performance overview
    
    Aggregated indicators such as model accuracy, average latency, token consumption, and overall cost across runs. Metrics provide operational insight needed for budget control and performance tuning.
    
    
  </TabItem>
</Tabs>