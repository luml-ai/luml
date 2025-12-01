---
sidebar_position: 2
---

# Notebooks
Notebooks is an integrated development environment (IDE) module that provides users with access to fully functional JupyterLab instances. 
The section is designed for custom model authoring, script writing, pipeline development, and hyperparameter experimentation via code.

The module's key architectural feature is the automatic synchronization of the notebook's file system with the platform interface, 
enabling seamless integration of custom code into MLOps processes.

## Notebook Instance
The basic unit of the module is an Instance. It is an isolated container featuring a Python runtime environment, 
allocated resources, and pre-installed libraries for interacting with LUML.

Each instance possesses the following attributes:
- *Workspace*: A personal workspace in .ipynb format.
- *Direct Link*: A unique URL for accessing the JupyterLab web interface.
- *Local Storage*: Temporary storage within the container for code files and generated artifacts.

## Artifact Integration (.dfs)
The module implements an automatic model detection mechanism. When a user saves an object in the [**.dfs**](../Core-Concepts/dfs_model.md) format 
(LUML's native format) within the JupyterLab environment, the platform automatically:
1. Identifies the new file within the instance's file system.
2. Displays it in the platform's UI sidebar (Info section).
3. Provides a context menu for managing the object.

This allows the model to be treated as an independent entity: viewing metadata, downloading it to a local device, 
or pushing it to the global Registry without leaving the notebook context.

## Data Management and Lifecycle
### Backup
The Backup function initiates a full dump of the instance's content. 
The system archives all code files (.ipynb, .py) and generated models (.dfs) present in the current environment 
and downloads them to the user's device as a single package. This ensures local preservation of work results before instance deletion or for code migration.

### State Management
- *Rename*: Changes the display name of the instance in the list.
- *Delete*: Irreversibly removes the container and all unsaved data within it.

		Note: Models that were previously exported to the Registry or downloaded locally are preserved independently of the notebook's deletion.