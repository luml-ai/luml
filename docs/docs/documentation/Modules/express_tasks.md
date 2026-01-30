---
sidebar_position: 1
---

# Express Tasks
Express Tasks is a module designed for automated machine learning model building (AutoML) and LLM workflow prototyping. By utilizing pre-configured data processing scenarios, this module enables the quick development of high-quality models with minimal effort.

## Task Types
In LUML you can train state-of-the art models for both traditional ML and GenAI use cases.

### Tabular Modelling
Many real-world applications rely on structured information stored in tables—spreadsheets, CSV files, or databases—to solve problems ranging from fraud detection and customer analytics to demand forecasting. These datasets often combine numerical values, text fields, and categorical attributes, making them well-suited for automated learning approaches. The system can handle varied feature types, deal with missing values, transform features, split data, selecting and tune algorithms, all without extensive manual preparation.

#### Classification
This setting targets the prediction of category labels from tabular inputs. Once a dataset is provided and the target column is specified, the workflow proceeds automatically. The system takes care of the heavy lifting of preprocessing and training, producing a ready-to-use model for category prediction.

#### Regression
This mode provides an automated workflow tailored to tasks that require predicting numerical values. Supplying the dataset is enough to trigger a complete automated pipeline that handles all workflow stages—from data preparation to the generation of the final artifact.

### Prompt Optimization
This is a visual no-code environment for constructing LLM workflows. Instead of writing code, the user builds a flowchart that outlines the logic step by step, linking components for data processing and action triggers.

The module supports two usage scenarios:

**Free-form Optimization**: This method optimizes a prompt solely based on the pipeline structure (diagrammed by the user) and the provided task description. No data is used in this optimization process.

**Data-Driven Optimization**: In this scenario,  the prompts are tuned based on an uploaded dataset using quality metrics, such as Exact Match or an LLM-as-a-judge approach.

The flowchart is built using three types of elements. **Input/Output** nodes define the data required for processing and the expected result. **Processor** nodes handle data transformation by receiving an input, modifying it as needed, and returning an output. **Gate** nodes control the flow for branching (implementing if/else logic) without transforming the input data; instead, they route the flow to the appropriate subsequent node based on a defined condition.

The optimization is based on the Teacher-Student concept, where a more powerful model (Teacher) is used to configure and train a lighter model (Student) for a specific task.

**Data Preparation**
Express Tasks support data uploads in .csv format. The module provides an interface for basic dataset manipulation. For example, the user can filter rows by specific conditions, sort data, or exclude unnecessary columns that should not be used for training.

**Outputs**
Successful completion of an Express Task generates a model in [.luml format](../Core-Concepts/luml_model.md).

Along with the model file, the user gains access to the Evaluation Dashboard - an interactive panel with quality metrics allowing assessment of model performance.

The ready model can be saved locally or moved to the [Registry](./Registry/registry.md) for further deployment via [Orbit](../Core-Concepts/orbit.md).

## Runtime
Runtime is a standalone playground designed for the testing of the trained in Express Tasks models.

### Model Inspection
Upon uploading a .luml file, the system automatically parses metadata and displays the Performance Dashboard. These metrics are immutable and reflect the model's state at the time training was completed. This allows for verification of the artifact's quality before use.

### Inference
Runtime provides an interface for feeding input data to the model. Two modes of operation are supported. **Manual Entry** allows the user to enter feature values and generate a prediction for a single sample, with the result (class or numerical value) displayed as text directly within the module interface. **Batch Processing** allows the user to upload a feature file to generate predictions for a larger set of samples. The system generates a file (in the same format as the input) containing the original data plus an additional column with the predicted values, available for download to a local device.
