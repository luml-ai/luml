---
sidebar_position: 3
---

# Runtime

Runtime is an inference environment designed for the execution, testing, and validation of [.dfs](../Core-Concepts/dfs_model.md) format models. 
It serves as a universal entry point for verifying artifacts created anywhere on the platform (Express Tasks, Notebooks, or externally uploaded).

The module functions as an isolated prediction engine, allowing users to assess model behavior 
on new data without the need for full infrastructure deployment.

## Key Features
**1. Model Inspection**
Upon uploading a .dfs file, the system automatically parses metadata and displays the Performance Dashboard. 
These metrics are immutable and reflect the model's state at the time training was completed. This allows for quick verification of the artifact's quality before use.
**2. Inference**
Runtime provides an interface for feeding input data to the model. Two modes of operation are supported:
- Manual Entry (Single Sample): A mode for manually inputting values for individual fields. Used for quick hypothesis testing or sanity checks.
- Batch Processing (File Upload): A batch processing mode for large volumes of records. Allows uploading a data file for mass prediction generation.

## Data Specifications
### Inputs
To ensure correct prediction execution, input data must meet strict schema validation criteria:
	File Formats: .csv, .xlsx.
	Feature Consistency: The set of columns in the input data must exactly match the feature set 
	used during model training (in both name and data type).
	Exclusions: The Target column must be omitted.

### Outputs
The result format depends on the chosen input method:
- For Manual Entry: The result (class or numerical value) is displayed as text directly within the module interface.
- For Batch Processing: The system generates a file (in the same format as the input) containing the original data 
plus an additional column with the predicted values. This file is available for download to a local device.