# Coming from Jupyter, marimo or other notebooks

For people who work in notebooks, Flow notebooks are the natural place to start. They keep what makes notebooks good, working in small steps and seeing results right away, and are built for working with agents.

## What is different

- **Results first.** The canvas shows each cell's output: tables, charts, metrics. The code is one click away instead of being the main view. When an agent writes much of the code, the results are what the person needs to review.
- **Lanes.** A traditional notebook has one line of history, so trying an alternative means duplicating cells or committing and reverting. In a Flow notebook, a lane is a variant of the same notebook: start one instantly, compare lanes side by side, keep the best version and rewind any lane to an earlier step. Agents try ideas much faster than people, and lanes keep every attempt comparable instead of messy.
- **Tracking built in.** A cell can record its run as an experiment, so results don't get lost between sessions.
- **Shared with agents.** The person and their agents edit and run the same notebook, and every change records who made it.

## When it helps most

Signs that lanes and tracked runs would help: many near-duplicate cells, copies like `analysis_final_v2.ipynb`, results copied into notes or spreadsheets, or an agent editing `.ipynb` files directly.

Flow notebooks are new. If the installed version has no `lumlflow guide` command, only experiment tracking is available.
