# Following a remote job in the web app

A training job on a cluster or a remote machine is usually out of reach: you
cannot open its Flow in a browser. `RelayedFlow` starts Flow next to the job and
shows it on the orbit's Flow page in the LUML web app, through the orbit's relay.
The user follows metrics, evals and traces live from anywhere, and the page
closes when the job ends.

Install `luml_sdk[flow]` and `lumlflow` on the machine that runs the job, and
set `LUML_API_KEY` there. The orbit needs a relay assigned; ask the user if
`ConflictError` says it has none.

```python
from luml.experiments.tracker import ExperimentTracker
from luml.flow import RelayedFlow

with RelayedFlow(
    "resnet-sweep",
    organization="My org",
    orbit="Research",
    store_path="./experiments",
) as flow, ExperimentTracker("sqlite://./experiments") as tracker:
    tracker.start_experiment(name="resnet50-lr3e-4")
    train(tracker)
```

- The name is the card on the Flow page. It defaults to the machine's host
  name. Starting the same name again replaces the old card.
- `store_path` must be the tracker's store. Without it, Flow shows its own
  default store (`~/.luml/experiments`), not the job's experiments.
- On start it prints the address in the web app; `flow.app_url` holds it.
- `organization` and `orbit` are needed when the API key reaches more than one.
- Stopping ends the session, also on an exception, at exit and on `SIGTERM`.
- A Flow already running on `port` (default 5000) is shown as it is. If it was
  started with a session token, pass that token as `session_token`.

Across notebook cells, where one `with` block cannot cover the work, call
`start()` and `stop()`:

```python
flow = RelayedFlow("eda", store_path="./experiments")
flow.start()
# ... later cells ...
flow.stop()
```
