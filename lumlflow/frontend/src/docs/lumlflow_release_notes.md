# LUMLFlow Release Notes

## v0.1.0

LUMLFlow provides a local UI for managing ML experiments end-to-end. This initial release includes the following features.

**Experiment tracking.** Create and manage experiments with the LUML SDK's `ExperimentTracker`. Log static parameters (hyperparameters, dataset identifiers) and dynamic metrics (accuracy, loss, custom scores) at each training step. All data is stored locally in a SQLite database. Experiments can be organized into groups, edited, tagged, and deleted individually or in bulk.

**Experiment groups.** Group related experiments together for organization and comparison. Groups support their own names, descriptions, and tags. The group detail view aggregates all parameters and metrics across its experiments.

**Traces.** Capture OpenTelemetry-based execution traces for LLM pipelines and agentic workflows. Each trace records parent–child spans with timing, model inputs/outputs, and `gen_ai.*` attributes. Traces are browsable in a span tree view, filterable by state (OK, Error, In Progress), and searchable by trace ID.

**Evaluations.** Run automated evaluations using the `evaluate()` function with custom scorers. Per-sample results — inputs, outputs, reference answers, and scores — are logged as eval samples and linked to their execution traces. Aggregated scores appear in the experiment's metrics view. Evals are searchable by ID and filterable by dataset.

**Annotations.** Add feedback and expectation annotations to eval samples and trace spans. Annotations support multiple value types (integer, boolean, string) and include an optional rationale. Annotation summaries provide count breakdowns per experiment.

**Experiment overview.** The experiment detail view displays parameters, metric charts, logged models, eval results, and traces in a tabbed interface.

**Experiments comparison.** Compare multiple experiments or experiment groups side by side to identify differences in parameters, metric trends, and model snapshots across runs.

**Advanced search.** Filter experiments within groups using a query language that supports attributes (`name`, `status`), timestamps (`created_at`, `duration`), dynamic metrics (`metric.*`), static parameters (`param.*`), and tags — combined with `AND`, `OR`, and parenthetical grouping. The search bar provides real-time validation and autocomplete.

**Model management.** View, rename, tag, and delete models logged to an experiment. Model metadata includes name, size, and creation time.

**Upload to LUML.** Push experiments and packaged models to the LUML platform directly from LUMLFlow using API-key authorization. Select the target organization, orbit, and collection, optionally embed experiment data in the model, and track upload progress in real time.
