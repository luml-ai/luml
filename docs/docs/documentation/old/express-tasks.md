---
sidebar_label: 'Express Tasks'
sidebar_position: 2
title: Express Tasks
---


# Express Tasks

## What Are Express Tasks?

**Express Tasks** are streamlined, pre-configured workflows that allow users to quickly build machine learning models without needing in-depth technical knowledge. They are designed for simplicity, speed, and accessibility—ideal for business analysts, domain experts, or beginners in ML who want results without getting into complex model tuning or coding.

These tasks abstract away the technical complexity of typical ML pipelines by offering:

- Guided interfaces
- Default settings that work well out of the box
- Minimal data preparation requirements
- Quick turnaround from data upload to model download

Whether you're working with classification, regression, or llm workflow builder, Express Tasks help you go from raw data to usable model in minutes.

---

## Available Express Tasks

### 1. Tabular Classification

**Description:**  
Tabular Classification allows you to predict predefined categories from structured data, where each row represents an individual observation (e.g., a customer, transaction, or product).  
The model uses the input features (columns) to learn patterns and classify new observations into target categories. Built-in preprocessing and sensible defaults make it easy to get started even without prior ML experience.

**Use Cases:**

- Customer segmentation
- Product classification
- Fraud detection

---

### 2. Tabular Regression

**Description:**  
Tabular Regression focuses on predicting continuous numerical values from structured data.  
This task trains a model that maps input features to a continuous target variable. It supports automatic feature selection, scaling, and a simple interface for training high-quality predictive models with minimal configuration.

**Use Cases:**

- Price prediction
- Demand forecasting
- Financial estimation

---

### 3. Prompt Optimization

**Description:**  
Prompt Optimization is a no-code environment for constructing and refining workflows powered by large language models (LLMs).  
Rather than manually crafting prompts and chaining responses, users can visually design and optimize how prompts interact within their specific domain.

**Use Cases:**

- Text classification & labeling
- Data processing automation
- Data extraction from unstructured text

---

## Express Workflow

Follow these steps to complete an Express Task:

1. **Upload your data**  
   Prepare your dataset in a supported format and upload it to the platform.

2. **Configure basic settings (or use defaults)**  
   Either adjust the model settings to fit your needs or continue with the optimized defaults.

3. **Train your model**  
   Let the system analyze your data and build a predictive model automatically.

4. **Download the result**  
   Get your trained model packaged with documentation and metadata.

---

## Supported File Formats

You can upload your data in the following formats:

- **CSV (.csv)**
- **Excel (.xlsx)**

> Make sure your files include clear headers and follow proper formatting conventions to ensure successful model training.

---

## Output Model Format & Structure

Once training is complete, the model is available for download as a `.dfs` file. You can use this file in the Runtime section to run predictions on new data.

---
