---
sidebar_position: 2
---

# Orbit

If the Organization is your team's global headquarters, the Orbit is the specific workshop or 
laboratory dedicated to a particular task. It is a logical unit that structures work within an Organization, segregating different ML projects, 
experiments, or their versions.

Architecturally, an Orbit is the environment where compute resources meet the model pipeline. 

It fulfills **three primary roles**:

### 1. Compute Context 
Unlike the Organization, which holds static data (in Buckets), the Orbit is responsible for 
*dynamic computation*. This is where Satellites—compute nodes—are connected and launched. 
This allows for flexible resource allocation: one Orbit might use lightweight CPU instances for testing, while another 
utilizes powerful GPU clusters for training, without any interference. The Orbit also ensures execution security by storing *Secrets* required for 
services running within this specific space.

### 2. Model Lifecycle Hub 
The Orbit is home to your Registry. It acts not merely as an archive, but as an active workspace 
for managing artifacts. Within an Orbit, you gain full control over development outcomes:
- **Analysis**: Reviewing Model Cards and Attachments to understand training context.
- **Experiment History**: Utilizing Snapshots to review training outcomes. This allows you to inspect the metrics and parameters of an experiment retrospectively, once the model has been trained and saved to the registry.
- **Selection**: Comparing models against each other to identify the best candidate.
- **Organization**: Grouping models into Collections, which function analogously to folders, helping to organize large numbers of experiments.

### 3. Deployment Launchpad 
The Orbit serves as the final staging area before a model goes live. 
Since the Orbit already possesses connected compute resources (Satellites) and access to artifacts, 
*Deployments* are launched from here—often with a single click!