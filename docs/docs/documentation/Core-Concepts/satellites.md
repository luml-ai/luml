---
sidebar_label: 'Satellites'
sidebar_position: 5
title: Satellites
---

# Satellites
A Satellite is an externally hosted compute node that you connect to LUML using a pairing key. Once paired, it becomes the execution engine for an Orbit: the place where models and other workloads actually run, while configuration, artifacts, and coordination remain in the platform.

When a Satellite comes online, it announces its capabilities to the platform—essentially telling LUML what kinds of tasks it can handle. 

Execution itself happens through a task queue. The platform places work items into the queue, and the Satellite periodically polls for new tasks, pulls them down, and runs them in its own environment. This pull-based model keeps the Satellite fully under your control (in your own infrastructure, network, and security perimeter), while still allowing LUML to orchestrate and monitor what it does.

In practice, a Satellite turns stored models and configuration into running services, without requiring the platform to host or directly access your compute environment.

