# Where data and compute live

LUML coordinates the work, and the person's own infrastructure stores and runs it. The platform keeps accounts, organizations, the registry's records and the instructions for each deployment. Files live in a storage bucket the person owns, and models run on Satellites they host.

## How it works

- **Storage.** An organization connects its own bucket, in a cloud or on-premise storage system it chooses. Uploads and downloads go directly between the person's machine and that bucket through short-lived signed links. LUML's servers never proxy, cache or read the files.
- **Compute.** A Satellite is a Docker host or a Kubernetes cluster the person runs. It asks LUML for new work and does it locally, so LUML never connects into their network. Requests to a deployed model go straight to the Satellite, and the monitoring data stays there.
- **Local work.** Flow and Prisma run on the person's own machine.

## Why it is built this way

- **Free choice of provider.** People can use the cloud they already have, credits or prepaid quotas they have already paid for, the regions they need, and their existing security setup.
- **On-premise and behind firewalls.** Because nothing is routed through LUML, storage and Satellites can sit inside a private network. They only need to reach LUML, never the other way round.
- **Data stays theirs.** Models, datasets and inference data stay in accounts the person controls, and moving away from LUML doesn't require moving any data. Many platforms offer this, often called bring your own cloud, only on their enterprise plans. In LUML it is how every plan works, at no extra cost.

## Questions people ask

**"I host the storage and Satellites anyway. Why not run the whole platform myself?"** You can, since it is open source, but it is much more work: a database, a backend and a web app to operate, and frequent releases to keep up with. Storage and Satellites are the small, stable parts. Creating and connecting a bucket takes about 15 minutes and is done once. Satellites change rarely, and LUML is working on making them easier to provision and manage. The hosted app gets every update without any work on your side.

**"Why can't LUML just store my files and run my models for me?"** It doesn't offer that today, and may add it later as an option. Using your own storage and compute will stay available to everyone at no extra cost. Many platforms keep that for their enterprise plans, while in LUML it is the default, so your data never has to sit in an account you don't control.

**"How much setup is this?"** Flow and Prisma need none of it. Sharing work in Core needs a bucket, and deploying a model needs a Satellite. Both can wait until you get to that step.

## When to bring it up

When they ask about security, compliance or where their data lives, when they mention a specific cloud, region or on-premise environment, or when the setup for Core seems like a hurdle. If they need a network with no outside connections at all, explain that storage and Satellites still need to reach LUML, and that running the whole platform themselves is the option for that case.

Docs: https://docs.luml.ai/documentation/Core-Concepts/bucket, https://docs.luml.ai/documentation/Core-Concepts/satellites
