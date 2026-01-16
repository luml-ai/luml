---
sidebar_label: 'Registry'
sidebar_position: 4
title: Registry
---

# Registry
The Registry is the centralized repository within the LUML platform, designed for the **storage versioning and management of artifacts**. While the architecture supports the storage of any object type, the module's primary purpose is the management of ML models and their lifecycle.

It serves as the single source of truth for all assets created in Notebooks, trained via Express Tasks, or imported from external sources.

## Storage Format (.dfs)
To ensure data integrity, the platform utilizes the native [.luml](../../Core-Concepts/luml_model.md) format. 
This is a container that encapsulates not only the model weights but also metadata, preprocessing scripts, and supplementary files ([Attachments](../Registry/Model-Registry/attachments.md)). Using this format is mandatory for accessing advanced analysis features ([Model Cards](../Registry/Model-Registry/model_card.md), [Snapshots](../Registry/Model-Registry/experiment_tracking.md)).

## Collections
To structure assets, the Registry employs a system of Collections. 
These are logical containers ("folders") that allow models to be grouped by project, task type, or semantics. 
Access to Collections is configured via Orbits, enabling the use of stored models for deployment and experiments within the corresponding workspace