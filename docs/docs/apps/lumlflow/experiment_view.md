---
sidebar_label: 'Experiment View'
sidebar_position: 2
title: Experiment View
---

# Experiment View

The Experiment View presents the full record of a single run across a series of tabs. It is reached by selecting an experiment from the [experiments list](./lumlflow.md#experiments-list).

The set of tabs depends on the experiment type. LUMLFlow distinguishes between Classical ML and Generative AI experiments and exposes only the surfaces relevant to each.

## Overview

The Overview tab is shared by both experiment types and consolidates the run's structured summary.

![](/img/lumlflow_exp_overview.webp)

Three tables list the run's recorded values. **Parameters** holds the static values defined before the run, such as hyperparameters and configuration settings. **Metrics** holds the dynamic values recorded during the run, captured at one or more steps. **Logged Models** lists models that were trained during the experiment and registered against it; the table is empty when no model was logged.

An information card alongside the tables consolidates the run's identifying metadata: the experiment ID, current status, creation time, user-supplied description and tags, total duration, and the source `.py` file. The card also exposes the **Upload to LUML** action, which promotes the experiment to the Registry. See [Uploading to LUML](./uploading.md).

## Classical ML Experiments

Classical ML runs expose two additional tabs alongside the Overview. The **Traces** and **Evals** tabs are not shown for this category, as they apply to generative workflows only.

The Metrics tab renders each logged metric as an individual interactive plot. Plots support inspection of values at specific steps and zooming into ranges of interest, which makes it practical to follow how a metric evolved over the course of training.

![](/img/lumlflow_metrics.webp)

The Attachments tab exposes files of any format that were logged to the experiment by the user. Common formats — `.docs`, `.pdf`, `.png`, `.csv`, `.img`, and `.svg` — are previewed inline. Other formats remain attached to the experiment and can be downloaded for local inspection.

## Generative AI Experiments

Generative AI runs share the Overview and Attachments tabs with Classical ML and add two surfaces specific to LLM-based workflows. The Metrics tab is not shown for this category, as classical training-curve metrics do not apply.

The Traces tab captures the execution flow of the generative system. Each operation within the system, including model calls, tool invocations, and intermediate steps, is recorded as a span, and related spans are grouped into a trace. This view makes it possible to inspect how prompts, model parameters, and tool calls combine to produce a given output, and to locate bottlenecks or unexpected behavior in the workflow.

*Note: traces are captured using [OpenTelemetry](https://opentelemetry.io/), an open standard for distributed tracing. Any instrumentation compatible with OpenTelemetry can be ingested by LUMLFlow.*

![](/img/lumlflow_trace.webp)

The Evals tab provides a structured way to assess the quality of a model or agent against a fixed set of inputs. Each evaluation is driven by an `eval_set` in which every sample represents a question or prompt for the model. Scoring can be configured by supplying a user-defined scoring system directly, or by building scorers with the LUML SDK and applying them to the run. Aggregated scores and per-sample results are surfaced inside the tab.

![](/img/lumlflow_evals.webp)