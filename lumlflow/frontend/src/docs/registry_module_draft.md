## Team Collaboration

`lumlflow` and Luml address two different stages of model development. `lumlflow` is a local-first tool for individual experimentation. It stores experiments, runs, and model artifacts on the machine where training happens, which keeps iteration fast and self-contained during active development. Luml is the platform side: a hosted environment that provides shared storage, versioning, deployment infrastructure, and team workspaces.

Local storage has limits. Experiments live on a single machine and are invisible to teammates. There is no versioning beyond what you manage manually. If the machine is lost or the local database is deleted, the training history goes with it. A locally stored model also cannot be served — it has to reach infrastructure that can run inference.

The Luml Registry is the bridge between these two stages. It is a centralized, versioned store for model artifacts, experiments, and datasets, accessible to everyone in the organization. Uploading an experiment or a model from `lumlflow` to the Registry is often the first step where solo work becomes team work. Once the artifact is in the Registry, teammates can browse it, compare it against other versions, add documentation and evaluation results, and deploy it to a Satellite as a live API endpoint. The Registry becomes the single source of truth for what was trained, how it performed, and which version is currently in production.

Uploading from `lumlflow` preserves the context that was captured locally. Metrics, parameters, evaluation results, and execution traces travel with the artifact as part of the `.luml` package. The Registry makes that context persistent, shared, and actionable.i 

### Uploading to the Registry

Before uploading, lumlflow needs to authenticate with your Luml account. Open the lumlflow UI and enter your API key — the key is stored securely and persists across sessions, so this step is only needed once.

To upload a model or experiment, select it in lumlflow and click **Upload**. The dialog asks you to pick the target Organization, Orbit, and Collection in Luml.

Once uploaded, the model appears in the Registry with its full metadata: the Overview tab shows the manifest, input/output schemas, and tags; the Model Card tab can render custom documentation added via the SDK; and the Experiment Snapshots tab displays the training history that was embedded at upload time. Each subsequent upload of the same model creates a new version, building a complete history of how the model evolved.

*Note: for a detailed look at what the Registry stores and how each tab works, see the [Registry documentation](https://docs.luml.ai/documentation/Modules/Registry/).*