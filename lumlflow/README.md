# Lumlflow

Local ML experiment tracking and model management.

Lumlflow gives you a lightweight, self-hosted dashboard to track machine learning experiments, organize them into groups, and manage associated models — all running locally with zero cloud dependencies.

## Quickstart

```bash
pip install lumlflow
lumlflow ui
```

This starts the web UI at [http://127.0.0.1:5000](http://127.0.0.1:5000) and opens it in your browser automatically.

## Overview

Lumlflow consists of two parts:

- **CLI** — a command-line interface to launch and configure the server
- **Web UI** — a browser-based dashboard for viewing and managing experiments

The server exposes a REST API that the UI consumes, so you can also integrate programmatically.

## CLI Reference

```bash
lumlflow ui                          # Start UI at localhost:5000
lumlflow ui --port 8080              # Custom port
lumlflow ui --host 0.0.0.0          # Bind to all interfaces
lumlflow ui --no-browser             # Don't open browser automatically
lumlflow version                     # Show installed version
```

## Features

### Experiment Tracking

Track ML experiments with rich metadata:

- **Name and description** for human-readable identification
- **Tags** for flexible categorization and filtering
- **Status** tracking — active, completed, or failed
- **Duration** to measure how long experiments run
- **Source** to record where the experiment originated
- **Metrics** — arbitrary key-value numeric metrics (accuracy, loss, F1, etc.)

### Model Management

Associate models with experiments to keep track of which models were produced by which runs.

### Experiment Groups

Organize related experiments into groups for easier navigation and comparison.

### Web Dashboard

- Browse and search experiments in a sortable, filterable table
- View experiment details including metrics and associated models
- Edit experiment metadata (name, description, tags)
- Create and manage experiment groups
- Customizable table columns

## Requirements

- Python 3.12+
