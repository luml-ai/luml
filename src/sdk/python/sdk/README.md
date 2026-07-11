# LUML SDK

Python SDK for ML experiment tracking. LUML lets you log metrics, parameters, models, evaluations, and LLM traces as your experiments run — either locally (SQLite) or synced to the LUML cloud platform.

**Main use cases:**
- Track training runs: log hyperparameters, metrics over time, final models
- Run and score evaluations on LLM or classical ML outputs
- Capture LLM traces automatically via OpenTelemetry instrumentation
- Upload experiments and models to the LUML platform for sharing and collaboration

## Installation

```bash
pip install luml-sdk
```

With optional extras:

```bash
pip install luml-sdk[tracing]   # LLM tracing via OpenTelemetry
pip install luml-sdk[datasets]  # pandas / pyarrow support
```

## Getting your API key

To upload experiments to the LUML platform you need an API key.

1. Go to [luml.ai](https://luml.ai) and log in
2. Open **Settings** → **API Keys**
3. Click **Generate new key** and copy it

![API key settings page](https://raw.githubusercontent.com/luml-ai/luml/main/lumlflow/docs/images/api_key.webp)

Set it as an environment variable:

```bash
export LUML_API_KEY=your_api_key_here
```

## Documentation

[https://docs.luml.ai/sdk/experiments/backends/sqlite](https://docs.luml.ai/sdk/experiments/backends/sqlite)