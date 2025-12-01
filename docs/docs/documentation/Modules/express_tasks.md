---
sidebar_position: 1
---

# Express Tasks

Express Tasks is a module of the LUML platform designed for automated machine learning model building (AutoML) 
and LLM workflow prototyping. This tool abstracts the technical complexity of pipeline configuration, allowing users to create working artifacts 
(.dfs format models) with minimal user intervention.

The module focuses on speed and simplicity: it utilizes pre-configured data processing scenarios, 
making it an effective tool for quickly obtaining results <u>without writing any code</u>.

## Task Types
The system offers three specialized environments depending on the problem type.

### 1. Tabular Classification
This mode fully automates the process of creating classification models. 
Users are not required to configure algorithms or manually process features—simply uploading a training dataset and specifying the Target column is sufficient. 
The system independently performs preprocessing and training, returning a ready-to-use model for category prediction.

### 2. Tabular Regression
Similar to classification, this mode is designed for the automatic construction of regression models (predicting numerical values). 
The user only needs to provide data, and the module handles all workflow stages—from value normalization to the generation of the final artifact.

### 3. Prompt Optimization
This is a visual no-code environment for constructing the logic of Large Language Models (LLMs). 
Instead of writing code, the user creates a scheme (flowchart) that defines how data is processed, transformed, and filtered before generating the final response.

The module supports two usage scenarios:

1. **Free-form Optimization**: 
Creating a workflow structure "from scratch" using a task description, where the generative model itself suggests the processing architecture.

2. **Data-Driven Optimization**: 
Configuring and tuning prompts based on an uploaded dataset using quality metrics (Exact match or LLM-as-a-judge).

The following elements are used to build the scheme:
- *Input/Output*: Mandatory nodes defining the data entry point and the final result format.
- *Processor*: A transformation node containing instructions for text processing.
- *Gate*: A logical node for flow branching (if/else conditions).

The optimization is based on the Teacher-Student concept, where a more powerful model (Teacher) is used to 
configure and train a lighter, faster model (Student) for a specific task.

## Data Preparation
Express Tasks support data uploads in **.csv** and **.xlsx** formats. 
It is critical to adhere to table structuring rules (headers, delimiters) for correct algorithm operation.

*Detailed recommendations on data cleaning, formatting, and quality checks before uploading can be found in the [Advices] section.*

#### Built-in Preprocessing
Before training begins, the module provides an interface for basic dataset manipulation. 
The user can filter rows by specific conditions, sort data, or exclude unnecessary columns that should not influence training.

## Outputs
Successful completion of an Express Task generates a model in .dfs format. 
This is the native binary format of the LUML platform, encapsulating trained weights, metadata, and preprocessing instructions.

Along with the model file, the user gains access to:
- **Evaluation Dashboard** -- an interactive panel with quality metrics allowing assessment of model reliability before use.
- **Prediction Interface** -- a built-in tool for model testing, allowing predictions for single records (manual) or data batches (via file upload).

The ready model can be saved locally or moved to the [Registry](./Registry/registry.md) for further deployment via [Orbits](../Core-Concepts/orbit.md).