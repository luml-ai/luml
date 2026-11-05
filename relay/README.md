# LUML Relay

Relay and agent that expose local web services through [LUML](https://luml.ai). The agent runs next to a service on a machine nobody can reach, such as a job on a cluster, and keeps one outgoing connection to a relay. The relay serves the service under a hostname of its own, and LUML decides who may open it.

LUML uses it for [relayed flows](https://docs.luml.ai/apps/lumlflow/relayed_flows): a Flow instance that runs next to an experiment and is opened from the LUML app.

## Installation

```bash
pip install "luml-relay[luml]"
```

The `luml` extra lets the agent start sessions at LUML with an API key. The `server` extra is only needed to run a relay.

To expose a flow, install the SDK with the `flow` extra instead. It brings the relay along and starts the agent for you:

```bash
pip install "luml_sdk[flow]" lumlflow
```

## Exposing a service

`luml-relay expose` exposes a service that listens on a loopback port. It reads the LUML API key from `LUML_API_KEY` and starts a session in an orbit that has a relay assigned:

```bash
export LUML_API_KEY="luml_your_api_key"
luml-relay expose 5000 --organization "My organization" --orbit "Research" --label "resnet-sweep"
```

The command prints the session's public address and serves it until it is stopped or LUML ends the session. `--bearer-token` sends a bearer token to the service with every request, such as Flow's session token from the launch URL of `lumlflow ui`.

## Running a relay

A relay is registered in the Relays tab of the organization settings in LUML, with a label, a base domain and the `wss` address agents connect to. Registering shows the relay's token once.

The relay is published as the container image `ghcr.io/luml-ai/luml-relay`. It reads the address of LUML from `LUML_BASE_URL` and its token from `LUML_RELAY_TOKEN`, and it listens on port 8080:

```bash
docker run -d -p 8080:8080 \
  -e LUML_BASE_URL=https://api.luml.ai \
  -e LUML_RELAY_TOKEN=dfsrelay_your_relay_token \
  ghcr.io/luml-ai/luml-relay:latest
```

The same server runs from the package with `pip install "luml-relay[server]"` and `luml-relay serve`. `luml-relay serve --help` lists its limits.

The relay serves plain HTTP, so TLS is terminated in front of it. The base domain needs a wildcard DNS record and a wildcard certificate. Set `LUML_RELAY_COOKIE_SECRET` to keep viewers' browser sessions across restarts.

## Documentation

- [Relayed flows](https://docs.luml.ai/apps/lumlflow/relayed_flows)
- [LUML documentation](https://docs.luml.ai)
