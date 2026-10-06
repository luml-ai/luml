---
sidebar_label: 'Satellite'
sidebar_position: 5
title: Satellite
---

# Satellite
A Satellite is an externally hosted compute node that you connect to LUML using a pairing key. Once paired, it becomes the execution engine for an Orbit: the place where models and other workloads actually run, while configuration, artifacts, and coordination remain in the platform.

Once a Satellite connects, it registers its capabilities with the platform, letting LUML know what types of tasks it can execute.

Execution itself happens through a task queue. The platform places work items into the queue, and the Satellite periodically polls for new tasks, pulls them down, and runs them in its own environment. This pull-based model keeps the Satellite fully under your control (in your own infrastructure, network, and security perimeter), while still allowing LUML to orchestrate and monitor what it does.

In practice, a Satellite turns stored models and configuration into running services, without requiring the platform to host or directly access your compute environment.

A Satellite comes in two kinds, and both are paired, deployed to and monitored the same way:

- **Docker** — runs every deployment as a container on one Docker host. Suited to a single server or a workstation.
- **Kubernetes** — runs every deployment as pods in a namespace of a Kubernetes or OpenShift cluster and is installed with a Helm chart. Suited to replicas, GPU nodes and cluster-level networking and security policies.

Each Satellite also records inference requests and serves a monitoring dashboard that Luml embeds next to the deployment.

For step-by-step instructions, see [How To Connect A Satellite](../../guides/satellite.md) for Docker and [How To Run A Satellite On Kubernetes](../../guides/satellite_kubernetes.md) for Kubernetes.

