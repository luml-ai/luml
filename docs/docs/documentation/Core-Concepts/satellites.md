---
sidebar_position: 5
---

# Satellites


A Satellite is a **compute node** responsible for the physical execution of code and 
request processing within an Orbit.

A model saved in the registry is simply a static set of files. 
It cannot independently make decisions or process data. To bring a model to "life," infrastructure is required. 
The Satellite provides exactly this infrastructure, serving as the bridge between your business logic and the servers.

By connecting to an Orbit, the Satellite assumes the role of the execution engine for all active deployments.

## The Satellite's Role in the Ecosystem
The Satellite abstracts away the complexity of server management and addresses **four critical tasks**:

### 1. Traffic Processing (Serving) 
The primary function of a Satellite in production is to accept incoming requests, 
pass them to the model, and return the result (prediction). It enables scaling, allowing the system to serve a 
large volume of simultaneous requests from users or external systems without compromising stability.

### 2. Execution Isolation 
The Satellite creates a *hermetic environment* for execution. 
This ensures that the model operates under controlled conditions, independent of a developer's local machine settings. 
Such isolation prevents library conflicts and ensures predictable code behavior.

### 3. Data Security 
The Satellite acts as a trusted executor. It has secure access to Secrets—API keys, 
database passwords, and other confidential data configured within the Orbit. This allows the model to utilize sensitive data for 
operations without exposing its content in logs or to the outside world.

### 4. Observability 
The Satellite does not merely execute commands; it provides feedback. 
It automatically generates logs and collects performance metrics. This allows for real-time monitoring of 
service health, visibility into model latency, and rapid response to potential errors.