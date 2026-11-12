# Flows and live sessions

The Flow page of an orbit lists Flow instances that run somewhere else, for
example next to a training job on a cluster, and opens them in the web app
through the orbit's relay. The orbit needs a relay assigned; without one,
these calls raise `ConflictError`.

Start one with the SDK's `RelayedFlow`, which starts Flow, exposes it and ends
it for you: `python -m luml skills show luml-sdk references/relayed-flow.md`.

The client calls underneath:

```python
client.flows.list()          # your flows whose session has not ended
client.flows.get(flow_id)
client.flows.remove(flow_id) # ends its session
```

`client.flows.expose(name)` and `client.live_sessions` start sessions by hand.
`RelayedFlow` already does this; use them only when you run the relay agent
yourself.
