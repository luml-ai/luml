# promptopt: Runtime Logic Reference

`promptopt` implements an asynchronous graph runtime for LLM-driven data processing. The graph is composed of nodes connected by typed field edges. Each node consumes state values, optionally calls an LLM, writes new state values, and triggers downstream sockets. Execution continues until the output node has been executed.

## Data Model and Invariants

The runtime state has two independent channels.

The first channel is the value channel. It maps `StateDescriptor` objects to concrete values. A `StateDescriptor` identifies one logical value slot, including its semantic type string and whether the slot is variadic.

The second channel is the readiness channel. It maps `Socket` objects to integer counters. A socket counter indicates whether an input condition for a node has been satisfied. A node is runnable only when all of its input sockets have counters greater than zero.

Each node exposes four interface views used by the scheduler: `listens_to` (input sockets), `reads` (state descriptors to pull values from), `input_names` (argument names used to assemble the input dictionary), and `is_lazy` (scheduling priority class).

An edge does not directly connect one node to another in execution time. Instead, an edge configures the source node’s output routing table. For a given source output field, the table stores two lists: sockets to trigger and state descriptors to write. Runtime execution uses only these compiled tables.

## Graph Construction and Edge Wiring

Node registration assigns a unique graph-local name and stores the node in `Graph.nodes`. At most one input node and one output node are allowed. Duplicate node objects and duplicate names are rejected.

Edge creation takes `(lhs_node, lhs_field, rhs_node, rhs_field)`. The graph resolves the destination field by calling `rhs_node.get_socket_by_field_name(rhs_field)`. That returns the destination socket and destination state descriptor. The graph then calls `lhs_node.add_output_connection(lhs_field, [socket], [state_descriptor])`. This is the core wiring step. After wiring, when the source emits `lhs_field`, the runtime both writes into the destination descriptor and increments the destination socket counter.

Because edges compile into node-local routing tables, the scheduler does not traverse adjacency lists at runtime. It only executes node outputs and applies their emitted writes and triggers.

## Scheduling and Queue Semantics

Execution uses two queues inside `GraphState`: an active queue and a lazy queue.

A node is eligible for scheduling when every socket in `node.listens_to` has counter `> 0`. Eligibility is recomputed in each iteration by scanning all nodes except the input node.

When eligible, nodes are enqueued by `is_lazy`. Non-lazy nodes go to the active queue. Lazy nodes go to the lazy queue. If a node is already present in either queue, it is not enqueued again.

Each loop iteration executes exactly one queue batch.

If active queue is non-empty, it is selected. Otherwise, if lazy queue is non-empty, it is selected. If both queues are empty, the runtime raises an error (`No nodes to run`), which means the graph stalled before reaching output.

All nodes in the selected queue are executed concurrently with `asyncio.gather()`. For each node, inputs are assembled by zipping `input_names` with `reads` and pulling values from state descriptors.

After each node finishes, the runtime resets all socket counters listed in `node.listens_to` to zero, then applies the node output:

1. Apply writes into the state map.
2. Increment each triggered socket counter by one.

After processing the whole selected queue, if the output node was in that queue, execution stops and returns the output node inputs assembled from current state values. Otherwise, both queues are cleared and the next iteration starts.

## Variadic Semantics

Variadic behavior is represented by `VariadicList`, a list subclass used as a marker for append semantics.

Input-side wrapping occurs when a source output field is connected to at least one variadic destination descriptor. In that case, scalar values are wrapped as `VariadicList([value])`; list values become `VariadicList(value)`.

State merge behavior is append-based only when both existing and incoming values for the same descriptor are `VariadicList`. In that case, the existing list is extended in place. In all other cases, the new value overwrites the old value.

Lazy scheduling is coupled to variadic inputs. `Processor` is lazy if any input field is variadic. `Gate` is lazy if its classification input field is variadic. `OutputNode` is lazy if any passthrough field is variadic. This gives non-variadic work priority and defers aggregate-style operations until active work is exhausted.

## Node Execution Contracts

`InputNode` validates external input against its `JsonModel`, then routes each field through its output routing table. It does not call the LLM. It emits writes and triggers only.

`Processor` builds a system message that includes input schema, output schema, and instruction text. It appends few-shot examples if present, then appends user input JSON. It calls `llm.generate(messages, out_schema)` and parses JSON output. For each declared output field, it routes the generated value through the output routing table, wrapping to `VariadicList` when the destination is variadic.

`Gate` builds a classifier prompt with an output schema restricted to `classification` values from `output_classes`. It calls `llm.generate`, parses the selected class, validates membership in declared classes, then forwards the original input value to descriptors mapped under the selected class and triggers only class-specific sockets.

`OutputNode` has no outgoing routing. Its `generate()` returns empty writes and triggers. Graph termination happens when the scheduler executes the output node, not inside the node itself.

## Serialization Model

`Graph.to_dict()` serializes nodes as `{name, type, kwargs}` and edges as `{lhs_node_id, lhs_field_name, rhs_node_id, rhs_field_name}`.

`Graph.from_dict()` recreates supported node types (`InputNode`, `OutputNode`, `Processor`, `Gate`), restores node-local settings via each node’s `from_dict`, and replays all edges through `Graph.connect()`. Replaying connect is required because routing tables are generated during connect, not stored as direct graph-global edge objects for runtime use.

## Optimizer Logic

`ZeroShotOptimizer` requests one instruction proposal per non-IO node and sets each node instruction directly.

`RandomFewShotOptimizer` samples up to `max_training_examples`, runs graph execution with tracing, and assigns captured examples back to nodes.

`JEDIOptimizer` freezes node identities, splits train/validation, collects teacher traces, generates candidate instructions, samples demo sets, and runs Optuna search over categorical choices `(node_id:::demo_set, node_id:::instruction)`. For each trial it deep-copies the graph, applies chosen examples/instructions, evaluates on validation examples with provided metrics, records score, and finally applies best parameters to the original graph.

## Current Runtime Caveats

`InputNode` applies variadic wrapping per source output field, not per edge. If one connection from a field targets a variadic descriptor, all values emitted from that source field in the same execution are wrapped into `VariadicList` before writing to every destination.

`Graph.connect()` only checks that the destination node has at least one input socket. It does not enforce schema compatibility between source and destination field types. Type compatibility is currently a modeling responsibility.
