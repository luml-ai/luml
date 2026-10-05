# Proposals

The branch under review adds a flow engine to lumlflow. A flow is a directory of cells. Each cell is a Python class that consumes other cells' outputs and produces its own. A daemon holds flows open, runs cells one at a time in a kernel process, and records every run's result in the flow's store. The store's history is a journal: an append-only list of transactions, numbered in steps. A lane is a named line of history over the cells; the code calls it a branch. For each cell a lane selects one version and holds an observed result, the last run result the lane saw for that cell. A person can fork a lane, switch between lanes, and rewind a lane to an earlier step, which restores what the lane pointed at then and recomputes nothing. Whether a cell has to run again is derived from its memo key: a hash of the cell's own code, the shared workspace code, the content of its inputs and, for cells that opt in, the workspace's pinned package environment. The planner picks the cells a run must visit, and staleness is the verdict on whether a cell's observed result is current. A step whose key matches a result already recorded is served as a memo hit rather than executed, and a step whose key the lane has already run is pruned by early cutoff. Two browser surfaces (the workbench and the notebook), a command line and an MCP server for agents sit on top of the daemon.

A review of the branch found seven correctness defects. Each one is a place where a surface stops honouring a contract the rest of the engine already states.

- The notebook editor saves without the version it started from, so the daemon's per-cell conflict check never fires. A person editing while a paired agent updates the same cell silently overwrites the agent's newer source.
- A run keeps going after its lane was rewound, and its result lands on the lane when it finishes. The lane moves forward again and the restored result is replaced by one for the version the person left.
- Staleness is judged against the environment a cell last ran under rather than the one the workspace has now. An environment-sensitive cell reads as current after the lockfile changes, the planner skips it, and a consumer can be served its stale cached result.
- A cell can declare an output as not persisted. The kernel then throws the value away, and any cell that consumes it fails every time with a message saying the value is not stored. Running the producer again cannot help.
- The notebook's output, code and logs panels load once when opened. The per-cell card they sit in stays mounted while its cell reruns or the lane switches, so an open panel keeps showing the previous result, or the previous lane's source, under an up-to-date header.
- Duplicating a flow copies the kernel's live Unix socket. On Linux and macOS the copy fails and leaves a partial destination behind, which blocks a retry under the same name.
- The environment status verb ignores the directory the command line sends and reports the daemon's launch directory. Asked from another project, it describes the wrong one.

The proposal is to fix all seven as targeted changes, each with a regression test, and nothing else. Six of them need no new mechanism. The conflict lock, the rewind promise, the memo key, the planner's demand for unpersisted values and the directory resolution every other verb uses all exist; the fixes make the failing surface use what is there. The seventh adds one small piece: the kernel keeps unpersisted values in memory so a consumer can read them. Redesigning the pieces involved, such as a different conflict model or a different notion of transient values, is out of proportion for defects that each have a one-contract cause.

# Design

The workbench, the notebook, the command line and the MCP server all talk to the daemon through the same verbs and see the same store: the journal, each lane's selections and observed results, and the verdicts the daemon's run queue and staleness derive from them. The seven fixes are independent of one another except where noted.

## Edit context in the notebook code editor

The daemon's edit verb takes an optional base: the definition hash the editor read the source under. When the cell's head, its newest version on the lane, has moved past that base, the daemon refuses with an edit conflict, unless the caller forces the write. The cell detail verb already returns the definition hash. The workbench carries it into its next edit; the notebook drops it, sends no base, and reads the flow and lane to save on from the store at save time rather than from when the source was loaded.

The notebook code panel keeps an edit context from the moment it loads a source: the definition hash, and the flow and lane the source was read on. Save sends that hash as the base and targets that flow and lane, whatever the store shows at save time. The client's cell detail type gains the definition hash so the context has something to keep. After a successful save, forced or not, the panel leaves editing and reloads for the lane on screen, which rebuilds the edit context; that is why a second save from the same open panel does not conflict with the first. The saved source appears when the lane on screen is the lane the edit was saved to.

Starting an edit is gated by the notebook's lane-head guard: on a lane standing behind its newest step, the existing fork prompt is shown instead. Save runs the same guard again, against the lane the edit targets, since a draft can outlive a rewind of that lane. A save onto a lane standing behind its head shows the fork prompt and writes nothing until the person answers. The prompt raised by a save forks the edit's lane, not the lane on screen. After the fork the draft stays open with its context moved to the new lane, keeping its base, and the save is sent there; the screen switches to the new lane when the edit's lane was the lane on screen, and stays where it is otherwise. A version difference surfaces as the conflict described below, with the same two choices. Dismissing the prompt keeps the draft open on the original lane and writes nothing. How the panel learns the edit's lane's position when it is not the lane on screen is the implementer's call.

When the daemon refuses with an edit conflict, the panel keeps the draft, says in its own words that the cell has changed since the edit started, and offers two choices. "Overwrite" sends the same edit again with force. "Keep theirs" drops the draft, leaves editing, and reloads for the lane on screen, the same as after a successful save. Nothing is written until the person picks. The notebook's RPC layer currently flattens every daemon refusal to its message; it has to keep the error kind the daemon sends so the panel can tell a conflict apart from any other failure, the way the workbench's client already does.

*Note: the workbench offers "save to a new lane" as its second choice, and the daemon's conflict message mentions it. The notebook does not offer it, to keep the fix to the finding, which is why the panel words the conflict itself; the choice can be added later.*

## Run results on a rewound lane

The queue checks, when a plan step is reached and again just before the kernel starts it, that the lane still selects the version the plan was made for. Nothing is checked when the kernel finishes: the result is journaled on the lane unconditionally. A rewind restores the lane's selections and observed results and stands the lane at the earlier step; it does not touch runs in flight. Any later journal line that counts as a change moves the lane forward to its newest step again. So a result that lands after a rewind replaces the restored result and moves the lane on.

Two decisions close this.

A rewind leaves every run the lane is awaiting, the same way the cancel verb does. The rewind is journaled first and the lane leaves its runs right after it, with nothing in between that yields to the event loop. The kernel stops the run when no other lane awaits it; otherwise it goes on, as when the cancel verb leaves it. A run asked for by another lane lands on that lane as before. A run asked for by the rewound lane can land nowhere, so the lanes still awaiting it run their own once it settles.

The queue journals a result on a lane unless a rewind of the lane was journaled at or after the step the lane asked for the run at. The anchor is the journal step at which the queue created the run on the lane's behalf, before any wait for the kernel, not the step the kernel began it: a run can wait at the queue's serial gate while the rewind lands, pass the check before the kernel starts it because the rewind restored the same version of the cell, and begin after the rewind with another lane keeping it alive. A rewind at or after the anchor drops the result even when the lane has since moved on again from the rewound position, which is why the check cannot read the lane's current position alone. This holds whatever the result's state: a cancelled run's record is a change on the lane too and would move it forward. When the check fails, nothing is written on that lane and the run reports abandoned. Other lanes awaiting the same run then find no shared result and run their own, which is what they do today when a shared run turns out unusable. A run whose result is dropped may have completed an experiment in the experiment tracker, the store runs record experiments into, before returning; that experiment stays in the tracker store, unreferenced by any run, like any experiment whose run was lost, and nothing is removed.

The index keeps no durable record of a lane's rewinds today: it stores no row for a rewind line, the lane row's rewrite column is overwritten by a later use or adopt, and the rewound position is cleared by the next change on the lane. Whether the check scans the journal from the anchor step or the index gains a per-lane last-rewind step that survives later changes and index rebuilds is the implementer's call.

Leaving on rewind stops wasted work and lets the surfaces drop the card's running indicator at once. The completion check is the guarantee: a cancel reaches a kernel busy in a C call only when that call returns, and the result still comes back.

*Note: journaling the orphaned result on behalf of another lane still awaiting it was considered and not done. It is rare, and it would make the rule two sentences instead of one.*

## Staleness of environment-sensitive cells

A cell may declare itself environment-sensitive, meaning its answer depends on the workspace's pinned packages. For such a cell the memo key includes the workspace's current lock hash, so the queue reruns it after the lockfile changes whenever it is the target of a run. Staleness, which the planner uses to decide which ancestors of a target are candidates at all, recomputes the key with the lock hash the cell's last run recorded, not the current one. The two agree for every cell except an environment-sensitive one whose environment moved: the queue would rerun it, staleness calls it synced, and the planner leaves it out.

Staleness gains an environment comparison for environment-sensitive cells. The environment cause is raised when the lock hash the run recorded differs from the workspace's current lock hash, in either direction, including a run that recorded none when the workspace has since observed one; two absences are no cause. It is independent of whether the shared code moved, and when both the shared code and the environment moved, both causes are listed. It does not depend on a workspace tree having been recorded.

The environment cause has a new kind, `env-changed`, with the detail "the workspace's packages changed". The existing workspace-code cause keeps naming changed files and is not used for this. The kind is a staleness-level fact, asserted in staleness tests; surfaces receive only the detail sentence, as they do for every cause today. The workbench client's closed list of cause kinds gains the new one as a consistency tidy, not as a wire contract. Cells that are not environment-sensitive are unchanged: for them the environment is provenance, shown by the existing older-environment badge, and never a cause. For an environment-sensitive cell whose environment moved, the badge stays as provenance and the cause is the verdict.

## Unpersisted outputs

An output declared with `persist` set to false is previewed, given a content hash unique to the run so that no consumer ever memo-hits across a rematerialization, and then dropped: no bytes are stored and its record has no value reference. The planner handles the demand side already: a consumer that needs the bytes forces the producer to run again, whatever staleness says. The kernel, though, loads inputs only from stored values, so the consumer fails every time, and the producer's rerun yields another unreadable record.

The kernel keeps the value of every unpersisted output in its own memory, held by its run-unique reference until the kernel stops, and serves a consumer's input from there. The implementer may bound the memory this takes, as long as a plan in progress always finds the values its producers made. Keeping only the latest value per cell does not meet that bar: two lanes running the same producer interleave at step granularity, so one lane's consumer can run after the other lane's producer and ask for its own run's value. Nor does the kernel's existing count-bounded cache of deserialized stored values, which evicts silently. The output record carries a reference to that in-memory value, distinct from the stored value reference, which stays empty. Every existing "is this value stored" check keeps its meaning: memo hits never serve an unpersisted output to a consumer, the planner keeps forcing the producer, and the expand, page and download gestures keep refusing such a value. Whether the reference is a new field on the record or is derived from the run-unique content hash the record already carries is the implementer's call, as is how the daemon hands it to the kernel alongside the stored reference.

An unpersisted output whose value is a file path needs one more step, because the run's scratch directory is removed when the run ends and the path would point at nothing. For it the kernel keeps a copy of the file's bytes outside the scratch directory and serves the consumer a path to that copy; where the copy lives is the implementer's call. The copies do not outlive the kernel: they are removed when it stops, and whatever a dead kernel left behind is cleared when the next kernel starts.

A consumer whose producer's value is gone, after a kernel restart or an eviction, gets the existing "run the cell that produces it" error.

The scheduler's stub executor in the flow test harness already models unpersisted records, and that part of it needs no change. The regression lives where the real executor is involved: at the kernel and the daemon level.

## Notebook panels follow the lane and the cell

The notebook's output, code and logs panels fetch their payload once when mounted. Cards are keyed by slug, the cell's name used as its key, and stay mounted across a rerun, a rewind or a lane switch; the header and footer read the refreshed cell list, the panel body does not.

An open panel shows the payload for the lane on screen and for the cell's current version and observed result. The code panel reloads when the lane on screen or the cell's version changes; the output and logs panels reload when the lane on screen or the result the lane observed for the cell changes. A run never changes the source, so the code panel does not reload on a result change. The daemon's cell summary already carries the step the version was created at, though the notebook client type does not read it yet. The summary gains the identity of the observed result, as `mat_id`, null for a cell the lane has never observed, so that a memo hit, a rewind and a rerun all read as a change. A refresh that arrives while nothing changed for a cell does not reload its panels. A panel keeps only the payload of its latest reload and drops the response of a reload a later trigger superseded.

The code panel is the exception while a person is editing: the draft and its edit context are kept, the read-only source underneath is refreshed, and a changed version surfaces on save as the conflict described in Edit context in the notebook code editor. That section also fixes what the panel shows after a successful save.

Whether a reloading panel keeps its previous payload on screen until the new one arrives or shows the loading state is left to the implementer.

## Duplicating a flow

Duplicate copies the flow directory wholesale after quiescing the source. The store's kernel directory holds the running kernel's Unix socket and, on the loopback transport, its token file. Quiescing reconciles files and does not stop the kernel, so the socket is there to be copied, and copying it fails.

The copy excludes the contents of the store's kernel directory; the copy has that directory empty, as a freshly initialised store does. If the copy fails at any point, the partial destination is removed before the error is raised, so a retry under the same name is not refused for a name the person never got.

The source's index is a live SQLite database in write-ahead mode, and copying its files while the daemon's open session on the store still holds it is not guaranteed to produce a consistent database. The invariant is that the copy opens with an index that matches its journal, and that the source session stays open and undisturbed throughout, as it does today. The mechanism is the implementer's call; not copying the index files at all and letting the copy rebuild its index from the journal on first open, which the store already does for an index that is missing, behind or ahead of its journal, is an acceptable choice.

## Environment status for the requested workspace

Every verb resolves its workspace from the `directory` parameter, which the command line always sends, and falls back to the daemon's launch directory when it is absent. The environment status verb ignores the parameter and reads the launch directory for the interpreter, the pinned packages and the open flows whose kernels it reports on.

Environment status resolves the directory like every other verb and reports that workspace: its interpreter, its lockfile's pins, and the kernels of the open flows the existing filter selects for the resolved directory; which flows count does not change. The `workspace` field of the response names the resolved directory. A directory that does not exist is refused the same way other verbs refuse it.

# Scenarios

The scenarios are the regression tests, grouped per fix in the order of the Design; lanes are named `main` and `sweep` throughout.

## Scenario: a notebook save carries the version it started from
**Given** the notebook code panel loaded a cell's source and its definition hash on lane `main`
**When** the person saves an edit
**Then** the edit verb receives that hash as the base, and `main` as the lane

## Scenario: a second save from the same panel does not conflict with the first
**Given** the notebook code panel saved an edit and stayed open
**When** the person edits again and saves
**Then** the edit verb receives as the base the hash the reload after the first save read, and the save goes through without a conflict

## Scenario: a paired agent's newer source is not overwritten silently
**Given** the notebook code panel loaded a cell and the person is editing it
**And** a paired agent has since edited the same cell on the same lane
**When** the person saves
**Then** the daemon refuses with an edit conflict, the draft stays on screen, and the panel offers "Overwrite" and "Keep theirs"

## Scenario: overwriting after a conflict
**Given** the panel shows a conflict for a draft
**When** the person chooses "Overwrite"
**Then** the same edit is sent again with force and the saved source is shown

## Scenario: keeping theirs after a conflict
**Given** the panel shows a conflict for a draft
**When** the person chooses "Keep theirs"
**Then** the draft is dropped, editing ends, and the panel reloads for the lane on screen

## Scenario: a refusal that is not a conflict shows as a plain error
**Given** the notebook code panel holds a draft
**When** the person saves and the daemon refuses with an error that is not an edit conflict
**Then** the panel shows the error as a plain failure, the draft stays on screen, and neither "Overwrite" nor "Keep theirs" is offered

## Scenario: the save lands on the lane the edit began on
**Given** the notebook code panel loaded a cell's source on lane `main` and the person began editing
**And** the lane on screen was switched to `sweep` meanwhile
**When** the person saves
**Then** the edit is sent for lane `main`, and the panel then shows `sweep`'s source

## Scenario: a save after the edit's lane was rewound forks that lane
**Given** the notebook code panel loaded a cell's source on lane `main` and the person began editing
**And** `main` was rewound to an earlier step meanwhile
**When** the person saves and names a new lane `sweep` in the fork prompt
**Then** nothing is written before the person answers, `sweep` is forked from `main`, the draft stays open with its context on `sweep`, the screen switches from `main` to `sweep` since `main` was the lane on screen, and the edit is sent for `sweep` with the base the draft began from

## Scenario: dismissing the fork prompt on save keeps the draft
**Given** the fork prompt was shown for a save onto lane `main`, which stands behind its head
**When** the person dismisses the prompt
**Then** nothing is written and the draft stays open with its context on `main`

## Scenario: a rewind leaves the run the lane awaits
**Given** a long-running cell is executing for lane `main` and no other lane awaits it
**When** `main` is rewound to an earlier step
**Then** the run is cancelled, the run reports abandoned, and no result is journaled on `main`

## Scenario: a result that lands after a rewind does not move the lane
**Given** a cell is executing for lane `main` and the kernel cannot be interrupted until it finishes
**When** `main` is rewound to an earlier step and the kernel then returns a successful result
**Then** nothing is journaled on `main`, the lane still stands at the earlier step, and its observed result for the cell is the restored one

## Scenario: a rewind on one lane keeps a shared run going for another
**Given** lanes `main` and `sweep` await the same run, asked for by `sweep`
**When** `main` is rewound
**Then** the run goes on, its result is journaled on `sweep`, and nothing is journaled on `main`

## Scenario: a result from a lane that was rewound is not reused by a lane that joined late
**Given** a run asked for by `main` finishes after `main` was rewound, and `sweep` was awaiting it
**When** `sweep` resumes
**Then** `sweep` finds no shared result and runs the cell itself

## Scenario: a run waiting at the gate when its lane is rewound is dropped
**Given** a run asked for by `main` is waiting at the queue's serial gate behind another lane's run, and `sweep` has joined it
**When** `main` is rewound to a step where the cell's version is unchanged, and the gate then frees and the run finishes
**Then** nothing is journaled on `main`, and `sweep` runs the cell itself

## Scenario: a run asked for after a rewind lands normally
**Given** lane `main` was rewound to an earlier step
**When** a cell is run on `main` afterwards and finishes
**Then** its result is journaled on `main` and the lane moves to its newest step again

## Scenario: an environment-sensitive ancestor reruns after the lockfile moves
**Given** an environment-sensitive producer whose output depends on the pinned version, and its consumer, both ran under one lockfile
**When** the lockfile is rewritten with different pins and the consumer is run
**Then** the producer is unsynced with the environment cause, the plan includes it, and both cells execute

## Scenario: an unchanged producer output after the lockfile moves prunes the consumer
**Given** an environment-sensitive producer whose output does not depend on the pinned version, and its consumer, both ran under one lockfile
**When** the lockfile is rewritten with different pins and the consumer is run
**Then** the producer executes, its bytes come out unchanged, and the consumer is pruned by early cutoff

## Scenario: a cell that did not opt in is untouched by an environment change
**Given** a cell that is not environment-sensitive ran under one lockfile
**When** the lockfile is rewritten with different pins
**Then** the cell stays synced, shows no cause, and is marked as computed under an older environment

## Scenario: an environment change shows as its own cause, not as a code change
**Given** an environment-sensitive cell ran, and neither its code nor the shared workspace code changed since
**When** the lockfile is rewritten with different pins
**Then** the cell's only cause is the environment cause, with the detail "the workspace's packages changed"

## Scenario: an environment-sensitive cell in a workspace without a lockfile stays synced
**Given** a workspace with no lockfile, so the flow has observed no environment
**And** an environment-sensitive cell ran there
**When** staleness is derived
**Then** the cell is synced and shows no cause

## Scenario: an environment-sensitive cell that ran before the workspace had a lockfile
**Given** an environment-sensitive cell ran in a workspace with no lockfile, so its run recorded no lock hash
**When** a lockfile appears and the workspace observes it
**Then** the cell is unsynced with the environment cause

## Scenario: a consumer reads an unpersisted output
**Given** a producer declares an output not to persist and a consumer reads it
**When** the consumer is run
**Then** the producer executes, the consumer executes with the producer's value, and the producer's record still has no stored value reference and is marked unpersisted

## Scenario: the unpersisted value is never served from the store
**Given** a producer with an unpersisted output has run and its consumer has run
**When** the consumer is run again
**Then** the producer executes again before the consumer, and expanding or downloading the unpersisted output is still refused as not stored

## Scenario: the kernel lost the value
**Given** a producer with an unpersisted output has run
**When** the kernel is restarted and its consumer is executed without the producer running first
**Then** the consumer fails with the existing message that the value is not stored and the cell that produces it must run

## Scenario: a consumer reads an unpersisted file output
**Given** a producer declares a file output not to persist and a consumer reads it
**When** the consumer is run
**Then** the consumer receives a path that still exists after the producer's scratch directory is gone, and the file holds the producer's bytes

## Scenario: copies of unpersisted file outputs do not outlive the kernel
**Given** a producer with an unpersisted file output has run, so the kernel holds a copy of the file
**When** the kernel stops, or dies and the next kernel starts
**Then** the copy is gone

## Scenario: an open output panel follows a rerun
**Given** a cell's output panel is open and showing its result
**When** the cell reruns and the cell list reports a new observed result
**Then** the panel reloads and shows the new result

## Scenario: an open code panel follows a lane switch
**Given** a cell's code panel is open and showing lane `main`'s source
**When** the lane on screen switches to `sweep`, where the cell's version differs
**Then** the panel shows `sweep`'s source

## Scenario: an open logs panel follows a rewind
**Given** a cell's logs panel is open
**When** the lane is rewound to a step where the cell's observed result differs
**Then** the panel shows the logs of the restored result

## Scenario: a refresh with nothing changed does not reload panels
**Given** a cell's output panel is open
**When** the cell list is refetched and the cell's version and observed result are unchanged
**Then** the panel makes no new request

## Scenario: a draft survives a refresh
**Given** a person is editing a cell's source in the code panel
**When** the cell list reports a newer version of that cell
**Then** the draft and its edit context are kept, and the conflict surfaces on save

## Scenario: duplicating a flow with a running kernel
**Given** a flow whose store's kernel directory holds a socket-type file, planted or bound there by the test, or left by a kernel the daemon launched under a short path
**When** the flow is duplicated
**Then** the copy exists with the source's cells, store and history, its kernel directory is empty, and the source is untouched

## Scenario: a failed duplication leaves no partial copy
**Given** copying a flow fails part-way
**When** the error is raised
**Then** the destination does not exist and duplicating under the same name again is not refused as already existing

## Scenario: the copy's index holds every committed step
**Given** a flow has been run and edited while its session stayed open, so its index has writes not yet folded back into the main database file
**When** the flow is duplicated and the copy is opened
**Then** the copy's journal and cells match the source's at the moment of duplication, and the source session is still open and unchanged

## Scenario: environment status from another project
**Given** the daemon was started in project A, and project B has its own lockfile and an open flow
**When** environment status is asked with project B's directory
**Then** the response names B as the workspace, lists B's pins, and lists B's open flows and their kernels, not A's

## Scenario: environment status without a directory
**Given** the daemon was started in project A
**When** environment status is asked without a directory
**Then** the response describes A

# Tasks

Each task is one agent session with its tests; the engine fixes come first and the two notebook tasks last.

- [x] fix: drop run results that land on a rewound lane
  - [x] In `lumlflow/lumlflow/flow/scheduler/queue.py`, before journaling a result in `_run`, check that no rewind of the lane was journaled at or after the step the lane asked for the run at, captured when `_start` creates the run rather than taken from the run request; otherwise journal nothing and report the run abandoned
  - [x] If the check reads a per-lane last-rewind step from the index rather than scanning the journal, add it in `lumlflow/lumlflow/flow/store/index.py` with a test in `lumlflow/tests/flow/test_index.py`
  - [x] In `lumlflow/lumlflow/flow/daemon/api.py`, make `rewind` leave every run the lane awaits through the queue's `abandon` after the rewind is journaled
  - [x] Add queue tests in `lumlflow/tests/flow/test_queue.py` for the cancelled, late-landing, shared-run and gate-waiting cases and for a run asked for after a rewind, using the harness's holding executor; the late-landing case needs the stub to ignore cancel for a named cell and finish on release, which the harness does not do yet
  - [x] Add a daemon test in `lumlflow/tests/daemon/` covering rewind during a run end to end

- [x] fix: judge env-sensitive staleness against the current lockfile
  - [x] In `lumlflow/lumlflow/flow/scheduler/staleness.py`, add the environment comparison with the workspace's current lock hash for environment-sensitive cells, add the `env-changed` cause kind, and keep the workspace-code cause for code changes only
  - [x] Add the kind to the workbench's cause-kind union in `lumlflow/frontend/src/flow/workbench/model/types.ts`
  - [x] Add staleness tests in `lumlflow/tests/flow/test_staleness.py`, including the workspace without a lockfile and a run that recorded no lock hash once the workspace observes one, and extend the environment tests in `lumlflow/tests/daemon/test_envs.py` with the producer-and-consumer cases; narrow the module docstring of `lumlflow/tests/daemon/test_envs.py` and the quiesce comment in `lumlflow/lumlflow/flow/daemon/hub.py` to cells that did not opt in

- [x] fix: keep unpersisted outputs readable by their consumers
  - [x] In `lumlflow/lumlflow_kernel/executor.py`, retain unpersisted values in memory by their run-unique reference, keep a copy of an unpersisted file output's bytes outside the run's scratch directory and remove the copies when the kernel stops or a new kernel starts, reference them from the output record, and let `_load_inputs` serve an input from that memory
  - [x] Carry the reference from the output record to the kernel payload alongside the stored reference; the hops in between are the implementer's to trace, among them the planner's input binding in `lumlflow/lumlflow/flow/scheduler/planner.py`, `lumlflow/lumlflow/flow/daemon/kernel_proc.py`, and `lumlflow/lumlflow/flow/store/models.py` if a new field is chosen
  - [x] Add kernel tests in `lumlflow/tests/kernel/test_executor.py`, including a file output and the removal of its copy, and a daemon test in `lumlflow/tests/daemon/` running a producer and consumer through the real kernel

- [ ] fix: resolve env status against the requested workspace
  - [ ] In `lumlflow/lumlflow/flow/daemon/api.py`, resolve the directory in `env_status` the way other verbs do and pass it through `_env`
  - [ ] Add a test in `lumlflow/tests/daemon/test_envs.py` with two workspaces and a daemon launched in one of them

- [ ] fix: copy a flow without its kernel files and with a consistent index
  - [ ] In `lumlflow/lumlflow/flow/daemon/hub.py`, make `duplicate_flow` skip the kernel directory's contents, leave the copy with an index that matches its journal, and remove the partial destination on failure
  - [ ] Add tests in `lumlflow/tests/daemon/test_api.py` for duplicating a flow whose kernel directory holds a socket-type file, for a failed copy leaving nothing behind, and for the copy's journal matching the source's after uncheckpointed writes; the socket test plants or binds a socket in the source's kernel directory, or runs the daemon under a short path, because the kernel binds a Unix socket only under a path shorter than 100 bytes and pytest's temporary paths are longer, and it must fail before the fix

- [ ] fix: carry the edit base and lane through the notebook code editor
  - [ ] Add `definition_hash` to `CellDetail` in `lumlflow/frontend/src/api/slices/workspace/workspace.interface.ts`, keep the error kind in `call` in `lumlflow/frontend/src/api/slices/workspace/workspace.api.ts`, and let `editCell` send `base` and `force`
  - [ ] In `lumlflow/frontend/src/store/flow/index.ts`, expose the edit context alongside the source, either from a new function beside `fetchCellSource` or by changing it and updating its other caller in `lumlflow/frontend/src/components/notebooks/cell/NotebookCellHeader.vue`, and accept the context in `editCellSource`
  - [ ] Let `createLane` in `lumlflow/frontend/src/store/flow/index.ts` and `lumlflow/frontend/src/components/notebooks/lanes/CreateLaneDialog.vue` accept the lane to fork from, pass it to the fork verb, and report the lane created, so the prompt raised by a save can fork the edit's lane
  - [ ] In `lumlflow/frontend/src/components/notebooks/cell/NotebookCode.vue`, keep the edit context, send it on save, re-run the lane-head guard on save against the edit's lane and move the context to the lane the prompt forks, switching the screen to it only when the edit's lane was on screen, and render the conflict with "Overwrite" and "Keep theirs"
  - [ ] Add a spec in `lumlflow/frontend/tests/` covering the base sent, a second save from the same panel, the conflict choices, a refusal that is not a conflict, the lane the save lands on, and a save after the edit's lane was rewound with the prompt answered and with it dismissed

- [ ] fix: refresh open notebook panels when the lane or the cell changes
  - [ ] Add `mat_id` to the cell summary in `lumlflow/lumlflow/flow/daemon/queries.py` with a test in `lumlflow/tests/daemon/test_queries.py`
  - [ ] Add `mat_id` and `changed_step` to `CellSummary` in `lumlflow/frontend/src/api/slices/workspace/workspace.interface.ts`
  - [ ] Make `lumlflow/frontend/src/components/notebooks/cell/NotebookOutput.vue` and `lumlflow/frontend/src/components/notebooks/cell/NotebookLogs.vue` reload on lane and observed-result changes, and `lumlflow/frontend/src/components/notebooks/cell/NotebookCode.vue` on lane and version changes, keeping a draft in progress and dropping the response of a superseded reload
  - [ ] Add a spec in `lumlflow/frontend/tests/` covering rerun, lane switch, rewind, a superseded reload, an unchanged refresh and a draft surviving a refresh
