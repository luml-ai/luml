---
sidebar_label: '.luml model format'
sidebar_position: 3
title: .luml Model Format
---

# .luml Model Format


The `.luml` file is the standard artifact format used throughout LUML. Every model trained via Express Tasks, exported from Notebooks, or uploaded externally is stored and operated as a `.luml` package. This format serves as the foundation for the platform's deployment, versioning, and experiment tracking capabilities.


## Design Principles


The `.luml` format is built on [FNNX](https://github.com/BeastByteAI/FNNX), an open specification for portable machine learning packages. Rather than storing just model weights, a `.luml` file is a self-contained archive that bundles everything needed to execute a model: the trained weights, inference code, environment specifications, input/output schemas, and metadata.


This architecture reflects a core principle in LUML: a model is not just a set of weights, but an executable unit with a defined contract. By capturing the full execution context at training time, the format eliminates the ambiguity that typically plagues ML deployments.


## Self-Contained Execution


Traditional ML workflows often separate model weights from the code and environment needed to run them. This separation creates friction during deployment—engineers must reconstruct the original environment, locate compatible preprocessing code, and ensure dependencies align. Version mismatches between training and serving environments are a common source of production failures.


A `.luml` package sidesteps these issues by design. When a model is saved, the package captures the Python environment with pinned dependency versions, any custom preprocessing or postprocessing logic, and the exact runtime configuration. The Satellite executing the model does not need prior knowledge of the framework or architecture used during training; it simply unpacks the `.luml` file and runs it.


This self-contained nature is what enables one-click deployments in LUML. When you deploy a model from the Registry to a Satellite, the platform does not need to coordinate environment setup or dependency resolution. The `.luml` package already contains everything required, making the deployment process deterministic and fast.


## Input and Output Contracts


Each `.luml` package declares a typed schema for its inputs and outputs. The manifest specifies the expected data types, shapes, and content formats for every input the model accepts and every output it produces. This schema acts as a contract between the model and any system that consumes it.


At inference time, the runtime validates incoming requests against this contract before passing data to the model. Invalid inputs are rejected early with clear error messages, rather than causing cryptic failures deep in the inference code. Similarly, outputs are validated before being returned to the caller.


## Metadata and Lineage


Beyond execution artifacts, a `.luml` package carries metadata that establishes the model's provenance. The manifest records when the model was created, which tool produced it, and any tags or attributes assigned during training. This metadata flows through the platform—when you view a model in the Registry, the Overview tab displays information extracted directly from the `.luml` package.


Experiment Snapshots take this further by linking training history to the saved artifact. Because the snapshot is intrinsically bound to a specific `.luml` file, you can trace any model back to the exact experimental run that produced it. Metrics, hyperparameters, and training logs are tied to the artifact rather than stored separately. This tight coupling between artifacts and metadata supports reproducibility. If you need to verify results from a previous experiment or retrain a model with the same configuration, the `.luml` package contains the information needed to do so.


## Framework Independence


LUML supports models from a wide range of ML frameworks: scikit-learn, XGBoost, PyTorch, TensorFlow, and others. The `.luml` format accommodates this diversity through its variant system. Traditional models can be packaged with their native serialization, while models requiring custom inference logic use the pyfunc variant, which wraps arbitrary Python code in a standardized interface.


From the platform's perspective, all `.luml` packages look the same. The Registry, Runtime, and Deployment modules do not need framework-specific handling because the format abstracts those details away. A scikit-learn classifier and a PyTorch neural network are both stored, versioned, and deployed using the same mechanisms.


This uniformity simplifies infrastructure. Teams can work with multiple frameworks without maintaining separate deployment pipelines for each. The Satellite runtime handles all `.luml` packages identically, regardless of the underlying implementation.


## Portability


Because a `.luml` package is a standard archive containing declarative specifications, it can be moved between environments without modification. A model trained on a local workstation can be uploaded to the Registry and deployed to a cloud-based Satellite without any changes. The package carries its own environment definition, so the target infrastructure does not need to match the source.


This portability extends to export and import workflows. You can download a `.luml` file from the platform, share it with colleagues, or store it in external systems. When the file is uploaded again—whether to the same organization or a different one—it retains all its metadata and execution capabilities.


## Relationship to Platform Modules


The `.luml` format integrates with every major module in LUML.


**Express Tasks** produces `.luml` files as the output of automated training. When training completes, the resulting model is immediately available as a downloadable `.luml` package or can be saved directly to a Registry.


**Notebooks** allow manual construction and export of `.luml` packages using the LUML SDK. This gives full control over what goes into the package, including custom preprocessing steps and dynamic attributes.


**Registry** stores `.luml` files and exposes their metadata through the Model Registry interface. The Overview, Model Card, and Experiment Snapshots tabs all read information embedded in the `.luml` package.


**Runtime** accepts `.luml` files for immediate inference. The module parses the manifest to display the model's performance metrics and provides an interface matching the declared input schema.


**Deployments** bind `.luml` packages to Satellites for production serving. The deployment process extracts the environment specification from the package and provisions the Satellite accordingly.


