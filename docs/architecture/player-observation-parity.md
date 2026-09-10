# Player observation parity implementation

Status: integrated and verified, 2026-09-09.

The agent should receive public information comparable to a player looking at
the factory, map, crafting menu, production statistics, and objective panel.
These surfaces expose game facts, never hidden verifier state or build plans.
This checklist tracks integration and verification, not just tool definitions.

## Completion checklist

- [x] Passive status transitions: bounded lease journal, stable entity identity,
  simulation ticks, observation revisions, severity, reconnect queries, and
  execution receipts. Coalesce repeated samples per entity per simulation second.
- [x] Terrain context: bounded water, cliffs, trees, resources, occupancy, and
  walkability summaries; coarse map detail at large radii.
- [x] Persistent camera: enabled by default, configurable radius and opt-out;
  image context on model turns across supported harnesses and the workbench.
- [x] Nearby entity tooltips: bounded persistent contents, fuel, recipe, status,
  and warnings in camera state. Keep full state separate from transition events.
- [x] Exact placement diagnostics: identify blocking entities and terrain without
  placing ghosts, selecting alternate builds, or changing placement semantics.
- [x] Path diagnostics: explain failure and return alternatives only when their
  reachability is established; never move to an unrequested destination.
- [x] Stateless crafting menu: required/available/missing ingredients, native
  craftability, bounded subrecipes, and the same information on queue failures.
- [x] Public production statistics, with bounded windows and optional rendering.
- [x] Event waits for public machine/production/research/order conditions, with
  explicit tick bounds and auditable termination reasons.
- [x] Persistent objective presentation and completion of the existing selectable
  technology/rocket progression integration and workbench verification.
- [ ] Focused tests, boundary tests, isolated live validation, documentation,
  and coherent commits for each completed feature.

## Design constraints

Simulation time governs sampling and coalescing; observer wall time must not
change replay. A transition feed cannot replace current entity state: reconnects
need explicit retention boundaries and a current keyframe. Missing coverage must
be reported rather than interpreted as a healthy factory. Sampling must scale
with relevant entities and active workloads, without scanning the entire map
every tick. Camera rendering must have bounded dimensions and entity detail.

Failures provide facts and leave the next decision to the agent. A walkable tile
is not necessarily reachable. Crafting arithmetic is a read surface; recursively
planning a factory is outside it. Production and objective views must distinguish
public game facts from evaluation-only evidence.

## Status stream implementation

The engine samples registered player machines every 60 simulation ticks, plus
reads and serialization. Discovery reuses the existing census and new entity
serialization. Its 4,096-sample ring crosses long interventions; envd publishes
immutable, revision-anchored transitions in a 2,048-event journal. A publication
coalesces each entity's changes within a simulation second, preserving observed
statuses and peak severity. Changes shorter than the sampling interval can be
missed. Coverage is explicit; this is not a per-tick event guarantee.

Receipts prioritize up to 16 transitions. Observations and `query_state` with
`kind='alerts'` expose bounded current status and retention/truncation metadata.
An engine overrun replaces the comparison baseline with current state and marks
the gap. New leases skip prior engine history. Checkpoints retain the published
journal but rebaseline engine state because GameState reconstructs entities.
Status ticks are absolute engine ticks; revisions belong to the lease.

Validation: isolated Factorio 2.0.77 furnace transitions during one 300-tick wait,
plus Lua/Python tests for ring overrun, removal, wire arrays, coalescing, immutable
receipts, checkpoint serialization, revision queries, and transport failures.

## Camera, tooltips, crafting, and objectives

The camera is enabled by default for each lease. `factorio_set_camera` persists
`enabled`, `radius` (8–192 tiles), and `entity_limit` (1–128, default 32).
`factorio_get_camera` reads the same view. Checkpoint recovery restores these
settings. Native model requests and MCP results carry the image and a compact
public objective view; retained image artifacts also appear in the Factory
workspace beside that objective. The dashboard identifies the last recorded
image by its game tick, rather than presenting it as a live video stream.

Near views use the factory renderer. Wide views switch to a fixed-size coarse
map, retaining resource patches, water, trees, cliffs, and machine occupancy
without rendering individual terrain sprites. Terrain layers describe presence
within cells, not an exact pathfinding grid. Nearby machine details are bounded
and include contents, fuel, recipe, status, and warnings; full entity inspection
remains a separate read. Missing sprites use visible fallback markers.

`factorio_get_craft_plan` is a stateless crafting-menu read. Product quantities
are converted to recipe batches using native output counts. The response gives
native craftability, ingredients available/required/missing, and bounded
subrecipes. Queue failures expose the same ingredient differences. The tool does
not queue ingredients, choose a factory design, or execute a recursive plan.

Validation includes native request image attachment, MCP image routing, bounded
payloads, settings/checkpoint round trips, and an isolated live HTTP boundary
check with near and wide PNGs. The Factory workspace was visually checked with
those recorded images and a clearly labelled fixture. This validates integration;
it is not evidence of a model completing a full freeplay evaluation. See
[`evaluation-modes.md`](evaluation-modes.md) for the distinct progression goals.

The expected benefit is fewer blind placement, crafting, and machine-state
decisions. Costs include image tokens, bounded rendering work, and additional
public state in context. Coarse maps sacrifice precision; sampled status changes
can miss short transients. Explicit truncation, retention gaps, image ticks,
deeper read tools, and persistent camera opt-out keep those tradeoffs visible.

## Spatial failures

Exact construction uses the engine's manual placement check, including offshore
pumps. Failures preserve the requested position and expose a rotated footprint,
up to 16 overlapping collision entities, up to 16 colliding tiles, and truncation
metadata. Local collision context is evidence; specialized engine rules can
reject a build even without a reported obstacle. Diagnostics do not create ghosts
or consume inventory. The explicit planner-assisted ablation retains its search.

Path requests retain their requested goal and explicit arrival radius. Failure
reports include local start/goal collision context; they do not claim an untested
nearest reachable position. A different pathfinder resolution may retry the same
goal, but a failed path does not move the character. Isolated Factorio 2.0.77
validation covers a belt blocking a furnace, water under a furnace, unchanged
inventory, and an exact water destination with unchanged character position.

## Production and event waits

The public statistics action reads native item/fluid totals and per-minute rates
for bounded product lists and native 5/60/600/3600-second windows. It includes
manual production, matching the player window, and exposes no verifier accounting.
Production history queries also include these statistics; JSON is the authoritative
view and no additional chart rendering cost is incurred by default.

Wait conditions run on simulation ticks and retain the first sampled match.
Machine status, inventory, research, crafting, production, accepted order delivery,
and bounded public events are supported. Decisions stop at the requested deadline;
Python transport latency is separately reported because simulation continues while
the receipt travels. A removed referenced entity or invalid condition errors rather
than appearing to satisfy the condition. Sampling cost scales with active waits.

Isolated 2.0.77 validation covers furnace completion, exact deadline decisions,
transport-latency reporting, and native production/consumption totals and rates.
Lua tests cover transient condition retention and sampling between poll boundaries;
Python tests cover validation, cancellation, and failure-preserving cleanup.
