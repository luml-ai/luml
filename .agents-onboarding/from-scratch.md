# Starting without MLOps tooling

Many teams track experiments in Jupyter notebooks, spreadsheets or their heads, and ship models by copying files. Nothing about that is unusual, but it gets expensive once there are more than a handful of experiments or more than one person.

## Common problems at this stage

Results that can't be reproduced, "which version is in production?" questions, a best run nobody can find again, models that only run on one laptop. If some of these apply to them, they are worth fixing early.

## Where to start

Start with Flow's experiment tracking. It runs locally, needs no account or server, and takes a few lines of code in the existing training script. They see value on the first run: every parameter and metric recorded, and runs comparable side by side.

## What comes next

As soon as they want to share results or ship a model, Core takes over from Flow:

- **Share.** Upload runs and models from Flow to an orbit, the team's shared workspace, with roles for each member.
- **Keep.** Registered models are self-contained, immutable `.luml` artifacts, linked to the experiment that produced them.
- **Ship.** Deploy a registered model in one step to a Satellite on their own servers, with monitoring included.

Compared with assembling several tools or adopting a large cloud ML platform, this is one system with one SDK, and the data can stay in their own buckets and on their own machines.

If they also want agents involved, read [control-vs-autonomy.md](control-vs-autonomy.md).
