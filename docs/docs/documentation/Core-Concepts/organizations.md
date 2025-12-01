---
sidebar_position: 1
---

# Organizations

The **Organization** is the root object in the LUML platform hierarchy that defines the boundaries of your workspace. It serves as the foundation upon which all subsequent work is built.

It is the existence of an Organization that unlocks access to the platform's key concepts. 
*Orbits, Deployments, and Registries* cannot exist in a vacuum—they become available for creation and configuration only within the context of a specific Organization.

Architecturally, an Organization performs **three critical functions**:

### 1. Functionality Activation 
The Organization acts as the entry point to the most important and advanced LUML tools. 
By creating an organization, the user initializes an environment where it becomes possible to transition 
from configuration to actual tasks. It links the platform's abstract functionality to a specific user account.

### 2. Data Centralization (Storage Context) 
The Organization serves as the global storage manager. 
You connect Buckets at the Organization level. This ensures a unified space for storing datasets and artifacts, 
which can subsequently be used across various projects within that organization. 
(Note: Unlike data, compute resources—Satellites—are connected separately to each Orbit, allowing for flexible resource management tailored to specific tasks.)

### 3. Access Management (IAM) 
The Organization defines the perimeter for security and collaboration. 
All access rights and roles are distributed exclusively within its bounds. Invited users enter the Organization's space, 
enabling collaboration on projects while maintaining complete isolation from your other organizations or external users.

