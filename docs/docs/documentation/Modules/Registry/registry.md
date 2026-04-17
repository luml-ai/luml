---
sidebar_label: 'Registry'
sidebar_position: 4
title: Registry
---

# Registry

The Registry is the centralized repository within the LUML platform, designed for the storage, versioning, and management of artifacts. While the architecture supports the storage of any object type, the module's primary purpose is the management of machine learning artifacts throughout their lifecycle.

It serves as the single source of truth for all assets created in Notebooks, trained via Express Tasks, or imported from external sources.

## Storage Formats

Models and experiments are stored in the native [.luml](../../Core-Concepts/luml_model.md) format. A `.luml` file is a container that bundles the artifact itself together with metadata, preprocessing scripts, and supplementary files ([Attachments](./attachments.md)). Use of this format is required for access to [Cards](./model_card.md) and [Snapshots](./experiment_tracking.md).

Datasets are stored as `.tar` archives. A dataset archive can contain multiple subsets and splits, which remain individually selectable in the Registry interface.

## Collections

To structure assets, the Registry employs a system of Collections. These are logical containers ("folders") that allow assets to be grouped by project, task type, or semantics. Access to Collections is configured via Orbits, enabling the use of stored assets for deployment and experiments within the corresponding workspace.

The Registry supports four types of Collections, distinguished by the kind of assets they contain.

### Model Collections

Model Collections contain trained models. Selecting a model opens a view with the following tabs.

**Overview.** A structured dictionary of static metadata describing the model's origin and characteristics. This includes general information (name, creation date, file size), the manifest (a technical description of the `.luml` contents), and tags for searchable context.

**Card.** Supplementary information about the model, such as an evaluation dashboard or custom HTML content. See [Cards](./model_card.md).

**Experiment Snapshot.** Metrics, parameters, and logs captured during the training run that produced the model. See [Experiment Tracking](./experiment_tracking.md).

**Attachments.** Files saved alongside the training run, including weights, configs, and reports. See [Attachments](./attachments.md).

Models within a collection can be compared side by side using their Experiment Snapshots.

### Experiment Collections

Experiment Collections contain experiments produced during model training and evaluation. Experiments are added to a collection in the same way as models, and each experiment is stored as a `.luml` file.

An experiment exposes the same tabs as a model: Overview, Card, Experiment Snapshot, and Attachments. The content of these tabs reflects the configuration, metrics, and artifacts of the run rather than a trained model.

Experiments within a collection can be compared side by side using their Experiment Snapshots, in the same way as models.

### Dataset Collections

Dataset Collections contain datasets used as inputs for training, fine-tuning, or evaluation. Each dataset is stored as a `.tar` archive that can hold multiple subsets and splits.

Selecting a dataset opens a view with the following tabs.

**Overview.** Metadata describing the dataset's origin, structure, and tags.

**Data.** A browsable view of the dataset contents. Subsets and splits can be selected individually.

**Card.** Supplementary information about the dataset, presented in the same way as a model or experiment card. See [Cards](./model_card.md).

Unlike models and experiments, datasets cannot be compared against each other.

### Mixed Collections

Mixed Collections can contain any combination of models, experiments, and datasets in a single container. This is useful when artifacts produced or consumed together need to be managed in one place.
