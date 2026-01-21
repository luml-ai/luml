---
sidebar_position: 5
---

# Deployments
A Deployment represents a model running as an active service on a connected Satellite. It is the mechanism that turns a stored model into a live, callable endpoint by binding a Registry artifact to real execution infrastructure. Deployments mark the transition from passive storage to production operation.

## Execution Model
Deployments do not run inside the platform itself. Execution happens entirely on a **Satellite**, which is an externally hosted compute node paired with LUML. Once a Deployment is created, the platform prepares the necessary configuration and tasks, but the Satellite remains fully in control of execution.

Inference requests are sent **directly to the Satellite**, not to the LUML platform. The Satellite exposes the runtime endpoint and executes the model locally in its own environment. This ensures that inference traffic and data never pass through the platform itself.
For each request, the Satellite performs a lightweight callback to the LUML backend to validate the supplied API key and check whether the invocation is authorized. Authorization checks are cached locally on the Satellite for a short period, reducing round trips to the platform and limiting backend load. As a result, permission changes are not applied instantaneously but propagate quickly in practice.

## Secret Injection
Deployments support secret injection to allow models to access external systems securely. Secrets are managed centrally in the platform and delivered to Satellites in one of two ways.
Some secrets are injected as environment variables at Deployment creation time. These values are resolved once and remain static for the lifetime of the Deployment.
Other secrets can be configured as dynamic attributes. In this mode, the Satellite retrieves the secret from LUML at invocation time, making it possible to update sensitive values without recreating the Deployment. Dynamic attributes are also cached briefly on the Satellite.

## Lifecycle
Deployments can be created, updated, paused, or removed without modifying the underlying model artifact. Deleting a Deployment stops execution on the Satellite but leaves the model intact in the Registry, allowing it to be redeployed elsewhere or reused in different contexts.



