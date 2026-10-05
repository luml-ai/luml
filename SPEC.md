# Proposals

A flow is a directory of cells. Each cell is a Python class that consumes other cells' outputs and produces its own. A daemon, one per user, holds flows open, runs cells in a kernel process started in the workspace's own Python environment, and records every version and run result in the flow's store. A lane is a named line of history over the cells. One lane per flow can be checked out: its cells are written to files that the daemon watches and rescans. Every other lane exists only in the store. Two browser surfaces (the workbench and the notebook), a command line and an MCP server for agents sit on top of the daemon, drive it through the same verbs, and follow the same live stream of frames.

A review of the branch found five correctness defects. Each one is a surface or a verb that stops honouring a contract the rest of the engine already states.

- The kernel borrows the daemon's whole install directory to find its own package. That directory ends up ahead of the workspace's packages on the kernel's module path, so cells import the tool's dependency versions rather than the workspace's pins, and a compiled package can fail to load outright when the two Pythons differ.
- A consumer created before its producer stays unresolved on a lane that is not checked out. Adding the producer later records only the producer; running the consumer still fails saying nothing produces its input. The checked-out lane heals because its files are rescanned after every change; the other lanes never are.
- A cell name with a hyphen, a space or a leading digit is accepted everywhere and turned into a class declaration that is not valid Python. Creation reports success and stores a cell that cannot run until someone edits it by hand.
- The notebook drops every state frame, the daemon's hint for changes that have no journal transaction behind them. Moving a cell from the command line, or deleting an experiment a cell's result refers to, leaves the open notebook showing the old order or the old availability until unrelated activity or a reload.
- The workbench's packages panel asks about the environment without naming a workspace, so the daemon answers for the directory it was launched in. A flow opened from another workspace shows that other workspace's interpreter and pins, and its own kernel drift is missing from the answer.

The proposal is to fix all five as targeted changes, each with a regression test, and nothing else. Four of them need no new mechanism: the daemon already re-accepts consumers after a delete, the workbench already reacts to state frames, every other verb already resolves the directory it is asked about, and the scaffold already derives a class name. The fixes make the failing surface use what is there. The kernel fix adds one small piece: a directory the daemon owns that holds the kernel package and nothing else. Redesigning cell naming, the binding model or the environment verb is out of proportion for defects that each have a one-contract cause.

# Design

The five fixes are independent of one another. Each section opens with how the piece works today, then the decision.

## The kernel sees only its own package

The daemon starts a flow's kernel as a child process of the workspace's interpreter: the workspace venv's Python when there is one, the daemon's own otherwise. The kernel package ships inside the tool's install and is never installed into the workspace, so the daemon puts it on the child's module path through the PYTHONPATH variable: first the directory that contains the kernel package, then the workspace root so that helper modules import, then whatever PYTHONPATH the daemon itself inherited. The directory that contains the kernel package is the tool's whole site-packages in a wheel install and the whole source checkout in a development install. Either way it precedes the workspace venv's own site-packages, and the daemon's dependencies shadow the workspace's.

The child interpreter is given exactly one thing from the tool's install: the kernel package. The daemon exposes it through a staging directory it owns, whose only entry is a copy of the installed kernel package, and puts that directory where the install directory is today: first on PYTHONPATH, followed by the workspace root and the inherited value as before. The staging directory lives under the daemon's state directory. It is brought up to date from the installed package whenever a kernel is about to start and the staged copy differs from the install, so a reinstalled or upgraded tool is picked up by the next kernel start without a daemon restart; how the difference is detected is the implementer's call. A kernel that starts while the copy is being refreshed must never see a half-written package.

A copy rather than a link, because the staging directory has to work where symbolic links are unavailable, and the package is a handful of files.

The typing stubs package that ships beside the kernel is not exposed. A cell file imports it under type checking only, by design, and a workspace that wants it for its editor installs it as a dev dependency.

## Consumers rebind when a daemon-originated change moves a lane's namespace

A cell's `consumes` names other cells' outputs, as `producer.output` or as a bare output name. Acceptance resolves each reference against the lane's namespace, the names and outputs of the lane's other cells, and records the binding in the new version. A reference nothing produces is flagged dangling, and a cell with one cannot run. The namespace moves whenever a cell is added, edited, renamed or deleted on the lane. For the checked-out lane this is covered: the files are projected and the next reconciliation re-accepts every file after any commit, which rebinds the consumers. Delete covers itself on every lane by re-accepting the consumers it left dangling. Adding or editing a cell through the daemon's verbs covers nothing: the lane gets the one new version, and on a lane that is not checked out its consumers keep the binding they had.

After a daemon-originated acceptance on a lane, that is a new cell, an edit or an import, the daemon re-accepts on the same lane every other cell whose binding could have changed, before the verb returns and before the files are projected. Re-accepting a cell whose binding did not change writes nothing, by the existing unchanged check, so the implementer may re-accept more cells than strictly necessary, including every other cell on the lane. A consumer whose binding did change gets a new version, with the staleness that follows from a changed definition, as re-acceptance after a delete gives it today. This holds whether or not the lane is checked out, and only on the lane the verb targets: every other lane keeps its own namespace and its own versions.

A rebound consumer's new binding resolves a dangling reference the accepted cell now satisfies, drops a binding to an output the edit removed, and turns a bare name into an ambiguous one when the accepted cell is a second producer of it. Whether an import's rebinding joins the import's one transaction or follows it as its own is the implementer's call.

*Note: the verbs' responses do not list the rebound consumers, and the command line's human output is unchanged.*

## A scaffold's class name is a valid identifier

A cell's name is its file name without the suffix. The daemon accepts any name that is safe as a file name: no path separators, no control characters, no `..`, no leading dot. Case is folded on acceptance. The scaffold for a new cell derives the class name by splitting the name on underscores, capitalising each part and dropping parts that are only digits, which keeps a placeholder's number out of the class. A name with a hyphen, a space or a leading digit produces a class declaration that does not parse. The file is still accepted, as any unparseable file is, and reported as created.

The scaffold derives a valid Python identifier from every name the daemon accepts. Words are split at underscores and at every run of characters that are neither letters nor digits; each word's first letter is upper-cased; digit-only words are dropped as today. A result that is not a valid identifier, because it starts with a digit, or that is a Python keyword such as `None`, is prefixed with `Cell`. An empty result falls back to `Untitled` as today. Letters outside ASCII are kept, since Python accepts them in identifiers.

The names a cell may have do not change. A name is referenced by consumers as text and names a file, so a hyphen or a space in it never reaches Python. Only the class declaration did, and nothing requires the class name to match the cell's name.

*Note: rejecting such names in the dialog and the verbs was considered and not done. The command line and agents already use them, and the file-name rule is the one every other place enforces.*

## The notebook follows state frames

The notebook store subscribes to its flow's journal stream. A transaction or a kernel frame schedules a refetch of lanes, cells and journal after a quiet moment; agent, claim and activity frames update live state in place. A state frame is the daemon's hint for a change with no transaction behind it. There are three: `order_changed`, when a cell was moved in the flow-wide presentation order; `experiment_removed`, when an experiment a cell's result refers to was deleted from the tracker, naming the lane and the cell; and `refreshing`, when reactivity is about to rerun a cell. The notebook store drops all three. The workbench reloads its cells on the first two.

The notebook store schedules the same refetch a transaction schedules on `order_changed`, and on `experiment_removed` when the frame names the lane on screen. The refetch goes through the same settle delay, so a burst of hints collapses into one round of requests. An `experiment_removed` frame for another lane changes nothing on screen and triggers nothing.

An `experiment_removed` frame for the lane on screen also reloads the open output panel of the cell it names. The panel shows the experiment's availability, and a deletion changes neither the cell's version nor its observed result, which are the two things the panel follows today. How the panel learns of it is the implementer's call.

`refreshing` stays ignored: the run frames that follow it already drive the card's running state, and the notebook has no indicator for the moment before a run starts.

## The packages panel asks about the flow's workspace

Every verb resolves its workspace from the `directory` parameter, which the command line always sends, and falls back to the daemon's launch directory when it is absent. The environment status verb reports that workspace's interpreter, its lockfile's pins, and the kernel drift of the open flows that belong to it. The workbench reads it when a flow opens, after a kernel restart and after an environment transaction, and sends no directory, so a flow opened from another workspace is described against the launch directory.

The flow brief, which the workbench reads to attach, gains a `workspace` field: the absolute path of the directory whose code and environment the flow uses. The daemon already holds this per open flow; it is the flow directory's parent. The workbench sends it as `directory` on every environment status read. The client's typing of the verb admits the parameter. The verb, the command line and the notebook are unchanged.

*Note: letting the environment verb take a flow name and derive the directory from it was considered and not done. The verb stays directory-scoped for every caller.*

# Scenarios

The scenarios are the regression tests, grouped per fix in the order of the Design. Lanes are named `main` and `sweep`.

## Scenario: the kernel's module path carries only the kernel package from the tool
**Given** a workspace directory and an inherited PYTHONPATH of one entry
**When** the kernel's spawn environment is built
**Then** PYTHONPATH is, in order, a directory whose only entry is the kernel package, the workspace root, and the inherited entry
**And** the tool's install directory is not on it

## Scenario: the staged kernel package matches the installed one
**Given** the spawn environment was built once
**When** it is built again
**Then** the staged package holds the same files as the installed kernel package, and nothing was rewritten because nothing differed

## Scenario: a changed install is restaged on the next kernel start
**Given** a staged kernel package from a previous spawn
**And** the installed kernel package has since changed
**When** the spawn environment is built
**Then** the staged package matches the installed one again

## Scenario: a kernel starts from the staged package and runs a cell
**Given** a workspace with a flow and a cell
**When** the cell runs
**Then** the kernel started from the staged package materializes it

## Scenario: a producer added after its consumer binds the consumer on an unchecked-out lane
**Given** lane `sweep` is not checked out and holds a cell `report` consuming `score.result`, flagged dangling
**When** `score`, producing `result`, is added to `sweep` through the daemon
**Then** `report` has a new version on `sweep` bound to `score.result` with no dangling flag
**And** running `report` on `sweep` materializes it

## Scenario: an edit that removes an output leaves its consumer dangling
**Given** lane `sweep` is not checked out, `score` produces `result`, and `report` is bound to `score.result`
**When** `score` is edited on `sweep` to produce `summary` instead
**Then** `report` has a new version on `sweep` flagged dangling for `score.result`

## Scenario: a consumer whose binding did not change gets no new version
**Given** lane `sweep` holds `score`, `report` bound to `score.result`, and `plot` consuming nothing
**When** a cell `audit` is added to `sweep`
**Then** `report` and `plot` keep their versions

## Scenario: rebinding stays on the lane that changed
**Given** `main` and `sweep` both hold `report` consuming `score.result` and neither holds `score`
**When** `score` is added to `sweep`
**Then** `report` on `sweep` is bound and `report` on `main` is unchanged

## Scenario: the checked-out lane's files carry the rebound consumer
**Given** `main` is checked out and holds `report` consuming the bare name `result`, flagged dangling
**When** `score`, producing `result`, is added to `main` through the daemon
**Then** the verb returns with `report` bound to `score.result` and its file on disk matching the stored source

## Scenario: a hyphenated name scaffolds a parseable cell
**Given** no cell named `train-model`
**When** `train-model` is added without a source
**Then** the stored source parses to one class named `TrainModel` and carries no parse flag

## Scenario: names with spaces, leading digits and keywords scaffold valid class names
**Given** the names `my cell`, `2d_plot`, `none` and `résumé`
**When** each is scaffolded
**Then** the class names are `MyCell`, `Cell2dPlot`, `CellNone` and `Résumé`, and each source parses

## Scenario: a placeholder's number still stays out of the class name
**Given** the placeholder name `untitled_3`
**When** it is scaffolded
**Then** the class is named `Untitled`

## Scenario: the notebook reorders cells after a move from elsewhere
**Given** the notebook shows lane `main` with cells `score`, `report`
**When** an `order_changed` state frame arrives
**Then** the cells list is refetched after the settle delay and the notebook shows the daemon's new order

## Scenario: the notebook refreshes a cell whose experiment was removed
**Given** the notebook shows lane `main` with `train` whose output panel is open
**When** an `experiment_removed` state frame for lane `main` and cell `train` arrives
**Then** the cells list is refetched after the settle delay and `train`'s output panel reloads its preview

## Scenario: an experiment removal on another lane changes nothing
**Given** the notebook shows lane `main`
**When** an `experiment_removed` state frame for lane `sweep` arrives
**Then** no refetch is made

## Scenario: a burst of state frames refetches once
**Given** the notebook shows lane `main`
**When** three `order_changed` frames arrive within the settle delay
**Then** the cells list is refetched once

## Scenario: a refreshing hint is ignored by the store
**Given** the notebook shows lane `main`
**When** a `refreshing` state frame arrives
**Then** no refetch is made and no live state changes

## Scenario: the brief names the flow's workspace
**Given** a daemon launched in workspace A and a flow in workspace B
**When** the flow in B is opened
**Then** its brief's `workspace` is B's absolute path, and a flow in A reports A

## Scenario: the packages panel describes the viewed flow's workspace
**Given** the daemon was launched in workspace A and the workbench attaches to a flow in workspace B
**When** the workbench reads the environment status
**Then** the request names B as its directory and the panel shows B's interpreter and pins

## Scenario: a kernel restart re-reads the same workspace
**Given** the workbench shows a flow from workspace B
**When** the person restarts the kernel
**Then** the environment status is read again with B as its directory

# Tasks

- [x] Expose only the kernel package to the workspace interpreter
  - [x] In `lumlflow/lumlflow/flow/daemon/kernel_proc.py`, make `spawn_environment` stage the installed `lumlflow_kernel` package into a directory under the daemon's state directory (`workspace.state_dir()`) that holds nothing else, refresh it when it differs from the install, and put that directory first on PYTHONPATH ahead of the workspace root and the inherited value
  - [x] Write the refreshed copy so a concurrently starting kernel never sees a partial package
  - [x] Replace `test_the_kernel_is_path_injected_and_the_workspace_rides_along` in `lumlflow/tests/daemon/test_kernel_proc.py` with tests for the path order, the staging directory's sole entry, the no-op rebuild, and the restage after the installed package changes
  - [x] Confirm the tests that start a real kernel through `spawn_environment` still pass, which covers the staged package being importable
  - [x] Run `uv run pytest tests/daemon/test_kernel_proc.py tests/kernel`, `uv run mypy`, `uv run ruff check` from `lumlflow/`

- [ ] Rebind a lane's consumers after a daemon-originated cell change
  - [ ] In `lumlflow/lumlflow/flow/daemon/api.py`, after the acceptance in `cells_new`, `cells_edit` and `import_cells`, re-accept the lane's other cells through `session.acceptance.reaccept` (or an equivalent that selects the affected ones) before `_edited` projects the files
  - [ ] Keep the unchanged check in `Acceptance._accept` as the guarantee that an unaffected cell gets no new version
  - [ ] Add tests in `lumlflow/tests/daemon/test_api.py` for the unchecked-out producer-after-consumer case including a successful run, the edit that removes an output, the unaffected cells, the other lane staying unchanged, and the checked-out file
  - [ ] Add an MCP-level test in `lumlflow/tests/daemon/test_mcp.py` mirroring the review's trigger: `new-cell` consumer, `new-cell` producer, `run` consumer on a lane without files
  - [ ] Run `uv run pytest tests/daemon/test_api.py tests/daemon/test_mcp.py tests/flow/test_accept.py`, `uv run mypy`, `uv run ruff check` from `lumlflow/`

- [ ] Scaffold a valid class name from any cell name
  - [ ] In `lumlflow/lumlflow/flow/dsl/scaffold.py`, make `class_name` split on underscores and non-alphanumeric runs, upper-case each word's first letter, drop digit-only words, prefix `Cell` when the result is not a valid identifier or is a keyword, and keep `Untitled` for an empty result
  - [ ] Extend `lumlflow/tests/flow/test_scaffold.py` with the names from the Scenarios, asserting the class name and that `loader.parse` finds the class with no flags
  - [ ] Add a daemon test in `lumlflow/tests/daemon/test_api.py` that `cells_new` with `train-model` stores a parseable version with no parse flag
  - [ ] Run `uv run pytest tests/flow/test_scaffold.py tests/daemon/test_api.py`, `uv run mypy`, `uv run ruff check` from `lumlflow/`

- [ ] Refresh the notebook on order and experiment state frames
  - [ ] In `lumlflow/frontend/src/store/flow/index.ts`, stop dropping state frames in `receiveLiveFrame`: call the existing settle-delayed refetch on `order_changed`, and on `experiment_removed` when the frame's lane is the current branch; ignore `refreshing`
  - [ ] Give the output panel a way to reload for the cell an `experiment_removed` frame names, alongside what `useCellPanelPayload` already follows in `lumlflow/frontend/src/composables/useCellPanelPayload.ts` and `lumlflow/frontend/src/components/notebooks/cell/NotebookOutput.vue`
  - [ ] Add tests in `lumlflow/frontend/tests/notebook-live-state.spec.ts`, or a new spec beside it, feeding state frames through `store.receiveLiveFrame`: refetch on order change, refetch and panel reload on a matching experiment removal, nothing on another lane, one refetch for a burst, nothing on refreshing
  - [ ] Run `npm run test`, `npm run type-check` and `npm run lint` from `lumlflow/frontend/`

- [ ] Scope the workbench's environment read to the flow's workspace
  - [ ] In `lumlflow/lumlflow/flow/daemon/api.py`, add `workspace` to `_flow_brief` from `session.workspace_dir`
  - [ ] Add `workspace` to `FlowBrief` in `lumlflow/frontend/src/flow/api/types.ts` and let `env.status` in `lumlflow/frontend/src/flow/api/client.ts` take an optional `directory`
  - [ ] In `lumlflow/frontend/src/flow/workbench/live/useWorkbench.ts`, send the brief's workspace as `directory` from `refreshEnv`
  - [ ] Add a daemon test in `lumlflow/tests/daemon/test_api.py` for the brief's workspace across two workspaces, and a workbench test in `lumlflow/frontend/tests/flow-live-workbench.spec.ts` asserting the `env.status` handler receives the status's workspace on attach and after a kernel restart
  - [ ] Run `uv run pytest tests/daemon/test_api.py`, `uv run mypy`, `uv run ruff check` from `lumlflow/`, then `npm run test`, `npm run type-check`, `npm run lint` from `lumlflow/frontend/`
