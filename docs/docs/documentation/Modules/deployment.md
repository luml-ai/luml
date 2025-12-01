---
sidebar_position: 6
---

# Deployments

Deployment is a platform object representing an active model instance running in an execution environment. 
This module is responsible for translating requests from external applications to the model and returning prediction results via API.
Deployment constitutes the final state of the model lifecycle, transitioning it from passive storage (in the Registry) to active operation (Production).

## Prerequisites
Creating and operating a deployment requires the following pre-configured components:
- *Model* - a valid .dfs format model stored in the Registry or a Collection.
- *[Satellite](../Core-Concepts/satellites.md)* - an active compute node connected to the Orbit that will physically execute requests.
- *[Secrets](./secrets.md)* (Optional) - a set of environment variables for model authorization in external services.


## Functionality
Upon initialization, a Deployment provides:
1. **API Endpoint**
Generation of a stable access point for data transmission (JSON/Multipart) and retrieval of predictions.
2. **Autoscaling**
Automated management of Satellite resources to handle the incoming request stream.
3. **Monitoring**
Collection of technical metrics (latency, error rate) and request logging for real-time service health tracking.