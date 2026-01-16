---
sidebar_position: 2
---

# Notebooks
The Notebooks module provides an in-browser experimentation environment powered by **JupyterLite**. It allows users to run notebooks entirely in the browser, with no cloud resources, no backend execution, and no local installation required. This makes it ideal for quick experimentation, prototyping, and validation directly within the platform UI.

### Notebook Environment
All notebooks execute client-side using a WebAssembly-based Python runtime. The environment behaves like a standard JupyterLab setup, supports .ipynb notebooks, and installation of wide variety of python packages. Because execution happens entirely in the browser, notebooks start instantly and run without any backend compute or persistent cloud services.

### Instance
An **Instance** is the core unit of the module. It represents a local, browser-backed notebook environment where users create and edit notebooks and generate artifacts. Files are stored in a virtual file system managed by JupyterLite and persist only within the browser where they were created. 

**⚠️ Important data persistence warning**  

Notebook instances are fully local. All files, notebooks, and generated artifacts are stored in the browser’s local storage. They are not scoped to a user account or organization, and they do not sync across devices or browsers. Switching users within the platform does not remove or reset existing notebook data. Clearing browser data, using a different browser, or switching machines will result in data loss unless the content has been explicitly backed up or exported.
Automatic Model Discovery (`.luml`)
The module includes automatic discovery of models created in notebooks. When a user saves an object in the .luml format, the platform immediately detects it within the instance’s virtual file system and surfaces it in the platform UI. From there, the model can be inspected, downloaded, or promoted to the global Registry. This allows notebook-generated models to be treated as first-class platform entities without requiring manual export steps.


### Data Management and Lifecycle
The Backup action creates a complete export of the instance, including notebooks, supporting files, and generated models. The resulting archive can be downloaded to preserve work or migrate it to another environment. Instances can be renamed for clarity or deleted when no longer needed. Deleting an instance permanently removes all locally stored data from the browser, but models that were previously downloaded or uploaded to the Registry remain available independently of the notebook instance.


