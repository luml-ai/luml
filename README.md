<div align="center">

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-hero-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-hero-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-hero-light.png?raw=true">
</picture>

</div>
<br>
<div align="center">
    <a href="https://luml.ai">Home Page</a> |
    <a href="https://discord.com/invite/qVPPstSv9R">Discord</a> |
    <a href="https://app.luml.ai">App</a> |
    <a href="https://docs.luml.ai/getting-started">Documentation</a>
</div>
<br>


LUML is a platform for managing the complete machine learning lifecycle, from initial experiments to production deployment. It provides experiment tracking, model registry, and deployment capabilities while maintaining separation between the control plane and the data and compute resources that teams bring to the platform.

The platform operates on a principle of resource isolation. Storage and compute remain under user control in their own infrastructure, while LUML handles coordination, orchestration, and access control. File transfers occur directly between local machines and cloud storage without passing through the platform's servers. Model execution happens on externally hosted compute nodes that users connect and manage, not within the platform itself.

<div align="center">
<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-cta-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-cta-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-cta-light.png?raw=true">
</picture>

</div>

<br>
<h3 align="center">──────── ✨ Key Features ────────</h3>

<div align="center">
<table>
<tr>
<td width="50%" valign="top">

**🔬 Experiment Tracking**
- Comprehensive metric and parameter logging
- Interactive visualizations and comparisons
- LLM tracing with full execution flow

</td>
<td width="50%" valign="top">

**📦 Model Registry**
- Centralized model versioning
- Metadata and configuration storage
- Direct experiment linkage
- Cross-context model reuse

</td>
</tr>
<tr>
<td width="50%" valign="top">

**🚀 Flexible Deployments**
- Direct-to-satellite inference
- Dynamic secret injection
- Cached authorization
- Zero-downtime updates

</td>
<td width="50%" valign="top">

**🔒 Data Privacy First**
- Client-side data transfers
- No platform-mediated storage access
- External compute execution
- Full resource autonomy

</td>
</tr>
</table>
</div>

<br>
<h3 align="center">──────── 🏗️ Core Concepts ────────</h3>

The platform structures work around four foundational concepts that determine how resources are organized, how projects are isolated, and how models progress from development to production.

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-aiops-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-aiops-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-aiops-light.png?raw=true">
</picture>


LUML is built around the concept of **AIOps**—a unified approach to AI operations that treats LLMOps (large language model operations) and AgentOps (autonomous agent operations) as natural extensions of MLOps. Rather than separate toolchains for traditional ML, LLMs, and agents, the platform provides a single operational framework that scales across all AI workload types.

### 🏢 Organizations

An Organization is the primary logical boundary within LUML. It serves as the root context for platform operations and provides a top-level namespace for creating and governing resources. Usage quotas are enforced per Organization, and all invited users operate within the limits of the Organization they currently work in.

Once created, Organizations support user invitations with assigned permissions, project workspaces (Orbits), and attached storage (Buckets) that function as shared backends for those projects. Users access data through their assigned Orbits, while storage configuration remains centralized at the Organization level.

---

### 🌍 Orbits

An Orbit is a project workspace within an Organization that brings work together without owning the underlying resources. The name reflects its operational model: the Orbit functions as the center of a project while data storage and compute resources remain external and are linked as needed.

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-orbits-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-orbits-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-orbits-light.png?raw=true">
</picture>


Each Orbit maintains its own artifact collections, connected compute nodes, secrets, and deployments, providing isolation between projects and teams within the same Organization.

---

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-satellites-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-satellites-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-satellites-light.png?raw=true">
</picture>

A Satellite is an externally hosted compute node connected to LUML through a pairing key. Once paired, it becomes the execution engine for an Orbit, handling workloads while configuration, artifacts, and coordination remain in the platform.

When a Satellite comes online, it announces its capabilities to the platform. Execution follows a task queue model: the platform places work items in a queue, and the Satellite polls for new tasks, retrieves them, and runs them in its own environment. This pull-based approach keeps the Satellite under user control within their own infrastructure and security perimeter, while LUML orchestrates and monitors execution.

*Note: inference requests are sent directly to the Satellite, not through the LUML platform. The Satellite validates API keys with the backend through a cached authorization mechanism, ensuring that inference traffic and data never pass through the platform.*

---

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-buckets-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-buckets-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-buckets-light.png?raw=true">
</picture>

A Bucket is an integrated cloud storage solution that retains user assets, including trained models and associated artifacts. Buckets connect at the Organization level, creating a unified data space for teams.

LUML uses a client-side data transfer model where file operations occur exclusively between the user's computer and the cloud storage provider. The platform's servers do not act as intermediaries during upload or download operations, and do not cache or read file contents. Users interact with storage directly, using the platform's interface as a control panel while maintaining full autonomy over resource management and security.

<br>
<h3 align="center">──────── 🧩 Modules ────────</h3>

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-orbits-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-registry-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-orbits-light.png?raw=true">
</picture>


The Registry is the centralized repository for storage, versioning, and management of artifacts. While it supports any object type, its primary purpose is managing ML models throughout their lifecycle. It serves as the single source of truth for assets created in Notebooks, trained via Express Tasks, or imported from external sources.

To ensure data integrity, the platform uses the native `.luml` format—a container that encapsulates model weights, metadata, preprocessing scripts, and supplementary files. The Registry organizes assets through Collections, which are logical containers that allow models to be grouped by project, task type, or semantics. Access to Collections is configured via Orbits.

#### Experiment Snapshots

Experiment Snapshots provide structured logging and management of ML experiment runs. Each snapshot captures metrics, parameters, artifacts, and metadata for every run, allowing users to trace how results evolved over time and revisit past configurations. Interactive charts and comparison tables highlight performance trends and surface differences between configurations. Since each snapshot is intrinsically linked to the saved model file, users can revert to any previous version and re-run it to verify results.

---

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-evals-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-evals-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-evals-light.png?raw=true">
</picture>



LLM Tracing provides visibility into the execution flow of systems that use large language models. It records inputs, outputs, and metadata associated with each step of an LLM call. The module surfaces aggregated run summaries for quick comparison, complete interaction histories showing prompts, tool calls, and intermediate steps, and usage metrics such as latency, token consumption, and cost across runs.

---

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-deployments-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-deployments-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-deployments-light.png?raw=true">
</picture>


A Deployment represents a model running as an active service on a connected Satellite. It binds a Registry artifact to execution infrastructure, turning a stored model into a callable endpoint.

Execution happens entirely on the Satellite, not inside the platform. Inference requests are sent directly to the Satellite, which exposes the runtime endpoint and executes the model locally. For each request, the Satellite performs a lightweight callback to validate the API key and check authorization. These checks are cached locally to reduce round trips.

Deployments support secret injection to allow models to access external systems securely. Some secrets are injected as environment variables at creation time and remain static. Others can be configured as dynamic attributes, allowing the Satellite to retrieve updated values at invocation time without recreating the Deployment.

---

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-express-tasks-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-express-tasks-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-express-tasks-light.png?raw=true">
</picture>



Express Tasks is a module for automated machine learning model building (AutoML) and LLM workflow prototyping. It enables quick development of models with minimal manual effort through pre-configured data processing scenarios. 

For tabular modeling, the system handles classification and regression tasks. 

For prompt optimization, a visual no-code environment allows users to build LLM workflows as flowcharts. The module supports free-form optimization based on pipeline structure and task description, as well as data-driven optimization that tunes prompts using quality metrics like Exact Match or LLM-as-a-judge evaluation.

---

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-notebooks-light.png?raw=true" >
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-notebooks-dark.png?raw=true">
  <img alt="Image" src="https://github.com/Dataforce-Solutions/static_assets/blob/main/luml-notebooks-light.png?raw=true">
</picture>



The Notebooks module provides an in-browser experimentation environment powered by JupyterLite. Notebooks execute client-side using a WebAssembly-based Python runtime, requiring no cloud resources, backend execution, or local installation. The environment supports `.ipynb` notebooks and installation of Python packages.


The module includes automatic discovery of models saved in `.luml` format. When a user saves such an object, the platform detects it and surfaces it in the UI. From there, the model can be inspected, downloaded, or promoted to the Registry. Instances can be backed up as complete archives for preservation or migration, and models uploaded to the Registry remain available independently of the notebook instance.