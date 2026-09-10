# Tool-calling compatibility contract

Status: implemented transport contract, 2026-08-26

This note defines what a modern model harness can rely on when it connects to
Factorio envd. It deliberately separates direct MCP calls, programmatic action
composition, and provider-specific programmatic tool-calling features.

## Direct MCP calls

The lease-bound MCP adapter exposes mutation, live-state, immutable-reference,
durable-result, and optional session-memory tools. The two world-action tools are:

- `factorio_observe_factory` reads the current public observation.
- `factorio_execute_program` submits one Python program as one environment
  intervention.

The adapter uses newline-delimited JSON-RPC with request IDs and negotiates MCP
protocol revisions from `2024-11-05` through `2025-11-25`. Each tool schema has
a `factorio/toolRoute` annotation. Immutable reference, memory-read, and
execution-artifact requests use a bounded read pool and may complete out of
order by JSON-RPC ID. Live reads are ordered with mutations. Mutations remain
exclusive. Use separate MCP sessions and leases for genuinely independent
world rollouts.

The HTTP service underneath the adapter is safe to call concurrently. Requests
for different leases can run in parallel subject to worker capacity. Requests
for the same lease are protected by the lease lock (a `threading.RLock` in the
local backend and an `asyncio.Lock` in the AgentENV gateway). Execution,
observation, finalization, pause/resume, and release therefore do not overlap
on one world. The server assigns `event.sequence` while holding that lock;
clients must use that value rather than infer order from response timing.

MCP has no standard capability bit that means "parallel tool calls supported."
The envd health capability manifest therefore reports the more precise
semantics:

| Feature | Value | Meaning |
| --- | --- | --- |
| `concurrent_request_safe` | `true` | The service can receive concurrent HTTP requests. |
| `per_lease_serial_execution` | `true` | One lease's operations are serialized. |
| `parallel_world_mutations` | `false` | A single Factorio world is never mutated concurrently. |

## Programmatic action composition

The Python submitted to `factorio_execute_program` is the environment's
programmatic composition interface. A program can call public FLE names in
sequence and use loops and conditionals to keep dependent work in one
round-trip. The action profile validates the whole program before execution;
the resulting sequence of FLE calls is recorded as one `ActionEvent`, with the
executed tool names retained for auditing. Calls are synchronous and source
ordered. The program cannot make network/MCP calls or access host files.

This is distinct from provider-native PTC or code-mode protocols. OpenAI,
Anthropic, OpenCode, and other harnesses may have their own mechanisms for
letting a model compose tool calls, but envd does not claim to implement those
provider protocols. They must either submit ordinary code through
`factorio_execute_program` or dispatch the direct MCP tools themselves.
The manifest advertises `programmatic_action_composition=true` and
`provider_native_programmatic_tool_calling=false` to make that boundary
explicit.

## Canonical semantic motor runtime

`semantic-motor-v1` is the canonical action profile. Reasoning remains
turn-based: the world pauses while the model thinks and advances on native
Factorio ticks while semantic options execute. `execution_game_speed` changes
only the ratio of simulation time to observer wall time, so an observer may run
at 1x or faster without changing action semantics, receipts, deadlines, or
scores.

The controller owns character-scale execution: collision-aware walking,
auto-approach for interactions, native mining and crafting duration, and exact
termination receipts. The policy owns factory-scale decisions: entity
locations, path corners, patterns, routing corridors, recipes, and research
sequence. Construction batches are ordered and non-atomic; a failed step
returns the successful prefix and blocker instead of silently rerouting.

The canonical profile therefore rejects `connect_entities`,
`nearest_buildable`, `move_to(..., laying=...)`, and generic non-exact
placement. Those remain available only through the explicit
`planner-assisted-v1` ablation profile. This makes planner assistance a
measurable evaluation variable rather than an accidental capability leak.

Long-running native work can overlap: `queue_craft` and `queue_research`
return immediately, while `wait` accepts bounded semantic conditions. Returned
entities carry stable integer handles for `resolve_entity`; semantic ports are
available through `get_entity_ports`. The agent camera is a default-on public
read surface with persistent opt-out and radius settings; it does not grant
alternative mutation semantics. See [player observation parity](player-observation-parity.md).

`submit_actions` adds a finite persistent command queue above these options.
Submission validates command and technology availability, then execution checks
the evolving inventory and geometry at each step. A failure preserves the
successful prefix and pending suffix. Queues can be inspected, truncated,
extended before a pending index, or resumed after an interrupt. Result
references allow later commands to consume entities returned by earlier ones.
The queue is deliberately not an arbitrary conditional policy: it represents
an open-loop commitment from the model's current information and returns at
declared semantic event boundaries.

## Harness obligations

When a model response contains multiple direct tool calls, a harness may
dispatch them concurrently only when it is prepared for per-lease
serialization. It must preserve each JSON-RPC/tool-call ID, surface
`isError=true` for failed MCP calls, and retain each returned event sequence.
It must not treat parallel submission as permission to mutate one lease in
parallel. A retry after a transport timeout can repeat a mutation; callers
must reuse the same `request_id` for the same logical execute call. Envd caches
the program hash and exact `ExecutionResult` for the lease lifetime. An
identical replay returns that result without advancing the world, consuming an
intervention, or allocating another event sequence. Reusing the key for a
different program returns HTTP 409. The bundled HTTP and MCP clients make one
automatic keyed retry after an ambiguous transport failure; returned HTTP
errors and unkeyed mutations are never retried automatically.

Mutation calls return a compact `factorio-execution-receipt-v1` rather than the
complete raw result. The raw result is written once under the run's
`tool-results` directory and can be paged with
`factorio_read_execution_result`. Other MCP results are bounded as complete
JSON documents. The adapter never cuts serialized JSON mid-token.

After each mutation, evaluation profiles also create an exact environment
checkpoint and atomically replace the run's resume pointer. Runner bundles add
the active contract, rating/history, harness workspace, and OpenCode session ID.
Compaction is therefore a context safety net; it is not the persistence layer.

## RLVR follow-up

The repeated-identical-failure circuit breaker is currently an evaluation
harness protection against wasting a run. It is not a training-loop policy and
must not be copied into RLVR without analysis. **TODO: brainstorm the
three-consecutive-failures behavior for actual training**, including reward and
credit-assignment consequences, whether blocked attempts are observable to the
policy, downstream effects on exploration and recovery, and possible reward
hacking through harmless-looking program variants or deliberate failure loops.
