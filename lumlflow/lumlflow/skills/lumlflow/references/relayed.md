# Following a remote job from the web app

A job on a cluster or a remote machine is out of reach of a browser. Wrapped in
`RelayedFlow` from the SDK, it starts Flow next to itself, and that Flow shows
up as a card on the orbit's Flow page in the LUML web app while the job runs.
The user opens it from anywhere and sees the job's experiments live, with the
same views as `lumlflow ui`.

`RelayedFlow` belongs to the SDK. Its usage, the store it must point at and
the notebook form are in the SDK skill:

```bash
python -m luml skills show luml-sdk references/relayed-flow.md
```

What the Flow side needs:

- `lumlflow` installed on the machine that runs the job, next to
  `luml_sdk[flow]`.
- `LUML_API_KEY` set there.
- An orbit with a relay assigned. Without one, starting fails with
  `ConflictError`; an admin assigns relays in the web app.

A Flow that is already running on the machine can be exposed by hand with
`luml-relay expose 5000 --organization "<org>" --orbit "<orbit>" --label <name>`.
Pass Flow's session token, from the launch URL of `lumlflow ui`, with
`--bearer-token`.
