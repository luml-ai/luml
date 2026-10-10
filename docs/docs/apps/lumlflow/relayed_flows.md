---
sidebar_label: 'Relayed Flows'
sidebar_position: 5
title: Relayed Flows
---

# Relayed Flows

A relayed flow is a Flow instance that runs on a remote machine and is opened from the LUML app. It serves to look into an experiment while it runs inside a job on a cluster or on another machine that nobody can reach. An agent next to Flow keeps one outgoing connection to a relay, and the relay serves the flow under a hostname of its own.

A relayed flow is not meant for working in Flow remotely, even though nothing in Flow is blocked through the relay.

## Requirements

Flows are exposed into an [Orbit](../../documentation/Core-Concepts/orbit.md), and the orbit needs a relay. A relay is assigned in the orbit's settings, in the relay field under the bucket. An admin of the [Organization](../../documentation/Core-Concepts/organizations.md) registers relays in the Relays tab of the organization settings. Each organization can run a limited number of flows at once.

The machine that runs the experiment needs the LUML SDK with the `flow` extra and [Flow](./lumlflow.md) itself.

```bash
pip install "luml_sdk[flow]" lumlflow
```

The flow is exposed with a LUML API key, created in the LUML web interface under account settings. The SDK reads it from the `LUML_API_KEY` environment variable, as described in the [SDK tutorial](../../guides/Integrations/sdk_tutorial.md).

```bash
export LUML_API_KEY="luml_your_api_key"
```

## Exposing a flow

The `RelayedFlow` object from `luml.flow` exposes a flow for as long as it is active. In a script it is used as a block around the training code.

```python
from luml.flow import RelayedFlow

with RelayedFlow(organization="My organization", orbit="Research"):
    train()
```

When it starts, `RelayedFlow` checks whether Flow answers on port 5000 of the local machine. A running Flow is exposed as it is. When nothing answers, `RelayedFlow` starts `lumlflow ui` on the default store and stops it again at the end. When another program answers on the port, starting fails with a message that names the port. The `store_path` and `port` arguments change the store and the port. The organization and the orbit can be left out when the API key reaches only one of each.

A flow has a name, which defaults to the machine's host name. Each user has one flow of a given name in an orbit.

A block cannot span notebook cells, so in a notebook the flow is started and stopped explicitly.

```python
flow = RelayedFlow(name="resnet-sweep")
flow.start()
```

```python
flow.stop()
```

Starting prints the address of the orbit's Flow page in the LUML app. The flow appears there as a card marked as relayed, with a status dot and the time of the last heartbeat from the agent. A live flow opens in a new browser tab. Removing the card ends the flow.

## When a flow ends

Leaving the block or calling `stop` removes the flow from the Flow page. A Flow instance that `RelayedFlow` started is stopped, and one it found running is left alone. The same happens when the interpreter exits or the process receives a termination signal.

A run that crashes or is killed cannot remove its flow. The card turns to disconnected and stays until an hour has passed without a heartbeat. Until then the flow counts toward the organization's limit. A rerun under the same name replaces the flow at once.

A flow that nobody opens for a week is ended, even while the agent is connected.

Only the user who exposed a flow sees it on the Flow page and can open it. Whoever opens a flow sees exactly what its owner sees: every experiment in the exposed store and every function of Flow.

## Running a relay

A relay is registered in the Relays tab with a label, a base domain and an agent address. Each flow gets a hostname under the base domain. The agent address is the `wss` address agents connect to, such as `wss://relay.example.net/connect`. Registering shows the relay's token once.

The relay is the container image `ghcr.io/luml-ai/luml-relay`. It reads the address of LUML from `LUML_BASE_URL` and its token from `LUML_RELAY_TOKEN`, and it listens on port 8080.

```bash
docker run -d -p 8080:8080 \
  -e LUML_BASE_URL=https://api.luml.ai \
  -e LUML_RELAY_TOKEN=dfsrelay_your_relay_token \
  ghcr.io/luml-ai/luml-relay:latest
```

The relay serves plain HTTP, so TLS is terminated in front of it. The base domain needs a wildcard DNS record and a wildcard certificate, for example for `*.flows.example.net`. The base domain must not share a registered domain with the LUML app, because pages served through the relay would otherwise count as the same site as the app.

*Note:* Without `LUML_RELAY_COOKIE_SECRET`, a restarted relay forgets the browser sessions of viewers, who then open their flows again from the LUML app.
