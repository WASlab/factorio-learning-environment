# Live Play Findings — 2026-09-10

Live session: canonical agent surface (`envd` lease + `factorio_execute_program`)
against the local Docker pair, fresh freeplay (`progression_task_spec("rocket_launch")`),
observer window connected as `fle-observer`, all seven objectives enabled.

Local session tooling (gitignored): `.runtime/play/` — `create_lease.py`,
`play_mcp.py` (stdio driver for `scripts/factorio_codex_mcp.py`), repro scripts.

## Incidents

### 1. Camera image crash and generic alert icons (fixed)

`GET /camera` returned `image_error: "2"` while the rest of the observation was
healthy, and every machine alert rendered as the generic yellow exclamation
triangle instead of a real icon. Two chained defects:

1. `flatten_entities` (`fle/env/tools/admin/render/utils.py`) inferred an
   "8-direction blueprint" whenever any dict entity had direction > 6 and then
   divided **every** dict entity direction by 2 in place. A west-facing
   character (12) halved an east-facing drill (4 -> 2), which is not a key in
   the renderers' `DIRECTIONS` maps, raising `KeyError`; the in-place mutation
   also corrupted the directions seen in the camera receipt itself (the
   `2.0`/`6.0` values observed).
2. `_render_alert_overlays` only coerced string statuses for dict entities.
   Camera entities become `EntityCore` objects via `flatten_entities`, so
   `"no_fuel"` never matched `EntityStatus.NO_FUEL` and fell back to
   `alert-warning` for every machine.

Fixes:
- `fle/commons/directions.py::normalize_render_direction` is now the single
  normalization helper (cardinals preserved; diagonals snap to the nearest
  cardinal; legacy index-style lists detected per batch by odd values).
  `flatten_entities` uses it and no longer mutates its inputs.
- `_render_alert_overlays` coerces string statuses on the object path too.
- `fle/envd/camera.py` normalizes camera entity directions before rendering and
  reports `type(exc).__name__` in `image_error`.

Result: real alert assets now render per status (`no_fuel` -> red fuel-pump
alert, `no_ingredients` -> yellow gear alert, power/fluid/storage alerts
available). Unit coverage in `tests/test_render_direction_normalization.py`
and `tests/envd/test_camera.py`; live verification via
`.runtime/play/verify_camera_fix.py`.

Open follow-up: Lua-rendered entities still carry raw integer `status` codes,
which do not match the string-valued `EntityStatus` enum; those keep the
generic warning until a code mapping (or a status string in the render
payload) exists.

#### Consideration: integer-status mapping for `factorio_render_factory`

Arguments in favour of adding it:

- The standalone render tool is an agent-facing primitive; an unfueled drill
  should read as a red fuel alert there too, not just in the persistent camera.
- One behaviour everywhere: agents that call `factorio_render_factory` directly
  (including non-camera profiles) currently get lower-fidelity alerts than
  camera consumers.
- The mapping is small and deterministic; it can be unit-tested against the
  same status names the camera path already produces, keeping both paths in
  sync.

Arguments against (or for a different fix):

- `EntityStatus.from_int` enumerates enum order, not Factorio's
  `defines.entity_status` codes; a hand-maintained numeric table silently
  mis-maps when Factorio reorders or extends statuses — a wrong icon is worse
  than the generic fallback.
- The render Lua already has the status entity; emitting the status *name*
  (as `public_view` does via `entity_status_names`) removes the need for a
  Python-side code table and is testable at the boundary.
- A warnings-string fallback ("out of fuel", "no ingredients", ...) would
  cover unknown statuses without coupling to engine constants.
- Cost: every Lua entity payload grows slightly (status name vs int), and the
  renderer change is in a hot path for large factories.

Suggested direction: prefer teaching the render payload to emit status names
(or a shared code->name map generated from game data) over a hand-written
integer table; whichever is chosen, cover it with a unit test that enumerates
all statuses so drift is caught.

### 2. Direct `FactorioInstance` attach resets the live world (open)

Constructing `FactorioInstance` calls `initialise(..., clear_entities=True)` in
its constructor (`fle/env/instance.py:261`). A "read-only" probe against the live
lease server (tcp 27000) wiped all entities, cleared `storage.agent_characters`,
reset inventory, and respawned the character at the origin — while the game kept
ticking. There is no attach-without-initialize mode.

- Workaround: read-only inspection must use raw RCON `/sc` queries.
- Desired: an explicit read-only/observe-only attach (or a hard guard refusing
  construction against a server owned by an active lease).

### 3. `get_entities` cannot see neutral entities (open)

`fle/env/tools/agent/get_entities/server.lua:27-29` filters by
`force = player.force`, so crash-site wreck, trees, cliffs, and rocks are
invisible. The client docstring documents `player_only` ("otherwise terrain
features too") but never sends it.

- Workarounds: `nearest(Resource.X)` for resource patches; the public camera
  `terrain_layers` (trees/obstacles/resources) for local geography; raw RCON for
  ground truth.
- Desired: honor `player_only=False` (no force filter) and include neutral types.

### 4. Minor API asymmetries (open)

- `Prototype.Tree` does not exist (use `Resource.Wood`).
- `Prototype.Character` does not exist and characters are skipped by
  `get_entities`/`get_entity`; no in-band way to query own position/direction.
- `extract_item` on an empty machine raises a transport-flavoured error
  ("Could not find a valid stone-furnace entity containing iron-plate") rather
  than a typed empty-output result.

### 5. Burner drill cannot feed an adjacent stone furnace (FIXED)

The classic early-game layout failed on this build: the drill's drop point
(`vector_to_place_result = {0, -1.296875}` converted to a 1.296875-tile forward
offset) lands 0.0039 tiles outside a 2x2 machine's collision box
(`0.69921875`), so the engine reports `output blocked by item on the ground.
There is no sink entity in place to accept the output.` while the furnace is
visibly adjacent. FLE's rounding of `drop_position` and the `neighbours` list
hid the cause.

Fix (committed `080c7e83`, corrected to the north-facing vector in `e57d8ad8`):
`fle/cluster/runtime_scenario.py` now emits a `data-updates.lua` in the runtime
mod that sets `vector_to_place_result = {0, -1.5}` for the burner mining drill,
so the drop lands on the tile center in front. Verified live: drill at
`(10,-6)` facing east feeds a furnace at `(12,-6)`; the status journal shows
`no_fuel -> no_ingredients -> working` (iron-plate) and a plate was extracted.
Workaround no longer needed: chests at the drop tile still work but are no
longer required.

### 6. Crafting was asynchronous and required a wait (FIXED)

`queue_craft` used `begin_native_crafting`, so the item only appeared after
later game ticks. Fix (committed `30ca1ddb`): `queue_craft` completes the craft
within the intervention by running the audited instant-craft path used by
`craft_item` (forced only for that call, restored immediately). Only existing
ingredients are consumed and the crafting time is still booked, so no item can
be created that the character could not afford. Verified live:
`queue_craft(WoodenChest, 2)` returned `crafted: 2` and the chests were in the
inventory in the same program.

### 7. Placement diagnostics can mislead (FIXED)

Live examples: a drill placement at `(0,-2)` was rejected as `occupied` naming
the crash-site spaceship; a drill at `(3,-70)` was rejected as
`engine_rules_or_route_obstruction` with a clear footprint (there was simply **no
ore** under it — mining drills cannot be placed without resources).

Fix (`2e021cb9`): `spatial_diagnostics` now receives the entity prototype,
counts resources in the mining area, and reports
`reason: "no_minable_resources"` with `mining_area` and `mining_resources` when
a mining drill has nothing to mine. Overlapping entities are ordered by
distance and carry a `distance` field. Verified live: placing a drill on grass
returns the dedicated reason instead of a generic engine rejection.

### 8. `wait()` units are ticks (FIXED)

`wait(75)` advanced 75 ticks (~1.25 s), not 75 seconds. The result now includes
`requested_seconds` and `elapsed_seconds` alongside the tick fields, and the
action reference states "60 ticks = 1 game second". Verified live.

### 9. Mining drill sink warning was spurious (FIXED)

`has_output_space` did not treat a furnace as a sink and trusted a transient
`waiting_for_space_in_destination` status, so a drill happily feeding an
adjacent furnace reported `'furnace at drop position is blocked.'`

Fix (`2e021cb9`): furnaces, assembling machines, and logistic containers are
recognized sinks with input-space checks; drills evaluate the sink itself
instead of the flapping status. Verified live: the new iron pair shows no
drill warnings while the furnace produces plates.

### 10. Steam power fluid connections need exact port alignment (open)

Building the first power plant (offshore pump -> boiler -> engine) exposed
several compounding issues:

- `place_offshore_pump(pos, Direction.DOWN)` placed the pump with engine
  direction north; the FLE direction flip for `offshore-pump` makes the public
  `direction` mean the flow side, but the failure payload's `direction` field
  reports the engine direction (`0`), which reads as "the argument was
  dropped". The tool's serialized `connection_points` also did not match the
  live game `fluidbox.get_pipe_connections()` results. Live probing was the
  only reliable way to find a valid spot.
- `surface.can_place_entity` without `build_check_type=manual` returns `true`
  for offshore pumps on water. Only the manual check rejects all but true
  shoreline tiles. Any tooling that pre-validates pumps should pass manual.
- In Factorio 2.0, boiler water ports are on the boiler's sides while steam
  exits the facing side, so a pump output that meets the boiler's center tile
  does not connect. The FLE `neighbours` list is a bounding-box heuristic and
  reported pump<->boiler as neighbours while the game had no fluid link
  (`no input liquid`, `no fluid present in connections`). Rotating the boiler
  90 degrees so a water port faces the pump output tile fixed it
  (pump `(-15.5,34.5)` output north, boiler `(-15.0,32.5)` facing east,
  engine `(-11.5,32.5)` facing east with its steam port on the boiler's steam
  output). Boiler then held water 200 + steam 200 at 165C and the engine
  status went to `working`.
- `place_entity_next_to(..., spacing=1)` leaves a one-tile gap that silently
  breaks direct fluid adjacency; spacing 0 is required for machine-to-machine
  fluid chains.
- `connect_entities` is planner-assisted-v1 only and raises
  `ProgramPolicyViolation` in the canonical sandbox, so canonical agents must
  route pipes manually with `place_entity(Prototype.Pipe, ...)`. A documented
  canonical pump/boiler/engine example (or a port-aware placement diagnostic)
  would remove a long failure spiral for agents.
- The engine stays `not_plugged_in_electric_network` until a pole covers it;
  pole supply area powers the engine and wire reach links it to the lab.

### 11. Fuel and material supply runs remain manual (observation)

Repeated trips to the iron/copper base for burner fuel and plates dominated
wall-clock time. Burner drills and furnaces both stop silently at `no_fuel`
and the furnaces hold a 44-ore backlog, so a refuel + wait + extract loop is
required. This is a prime target for building the first automated
drill->furnace->assembler line once automation tech and circuits allow.

### 12. Small ergonomics from the science production loop

- The lab dropped to `NO_POWER` when the boiler ran out of coal; the outage
  only surfaced by inspecting the lab/engine. A boiler `no_fuel` condition
  should be reflected as a high-severity alert/journal entry so agents notice
  power loss without polling.
- `harvest_resource` fails on a resource tile occupied by a drill
  (`reason: "occupied"`); harvesting from a free patch tile nearby works
  (e.g. `(39,-83)` instead of the drill tile `(41,-83)`).
- The coal drill's chest was offset from the drill's drop tile (chest at
  `(42.5,-83.5)`, drop at `(42.5,-83.0)`), producing the game warning
  "output blocked by item on the ground". `drop_position` is where items land,
  so paired chests must align to it.

### 13. Trigger technologies break `set_research` with an opaque error (open)

`oil-processing` in 2.0 is a trigger technology
(`prototype.research_trigger = {type = "mine-entity", entity = "crude-oil"}`).
`force.add_research("oil-processing")` returns `false` even though the tech
reports `enabled = true` and an empty `prerequisites` list, so `set_research`
raised only `Failed to start research for oil-processing`.
`chemical-science-pack` fails the same way until `oil-processing` is
researched, silently gating the chemical science milestone on mining crude oil.

Fix (pending restage): `fle/env/tools/agent/set_research/server.lua` now
inspects `tech.prototype.research_trigger` and raises an actionable message
("trigger-gated (mine-entity: crude-oil); complete the trigger in-game"). The
live lease still runs the old runtime until the next cluster restage, so the
fix has not been validated in-game yet.

Nearest crude oil patch on the current map: 20 tiles of `crude-oil` around
`(-280.5,-313.5)`, ~420 tiles from the origin and ~490 from the lab. The oil
phase therefore starts with a long expedition, pumpjack, pipes, refinery, and
chemical plant before chemical science packs can be produced.

### 14. `pickup_entity` destroyed non-chest inventories (FIXED, pending restage)

`pickup_entity` only returned chest contents and transport-belt lines before
destroying the entity. Picking up the lab moved its 24 science packs
(9 automation + 15 logistic) out of the world: they were in
`defines.inventory.lab_input`, which the action never read. The same gap
applies to assembling machine input/output, furnace source/result/fuel, and
module slots.

Fix: `fle/env/tools/agent/pickup_entity/server.lua` now iterates every numeric
entry of `defines.inventory`, reads each inventory the entity has (guarded by
`pcall`), and returns all contents to the player before destroying the entity.
Live validation on the restaged runtime caught a follow-up bug in that first
patch: many names in `defines.inventory` alias the same numeric id, and each
`get_inventory` call returns a fresh Lua handle, so a userdata-keyed dedupe
counted the same inventory once per alias (picking up a fueled furnace turned
1 wood into 19). The loop now dedupes on the numeric inventory id; re-validated
live: picking up a furnace holding 1 wood returns exactly 1 wood plus the
furnace.

### 15. Belt-chain verification and power-coverage regressions (observation)

Building the copper belt surfaced two agent-facing pain points:

- Belt direction names tell you nothing about whether a chain *connects*.
  The east leg ended at a turn facing north while the rest of the leg had
  been placed one row south, so items piled up on the turn tile and every
  downstream belt stayed empty. A trace of belt contents plus engine
  `direction` fields was needed to find it. A per-tile belt-flow diagnostic
  (where does each tile feed, is it backed up) would have made this
  immediately visible.
- Moving one pole to make room for the copper leg silently unpowered the
  science-output inserter. The only symptom was the lab staying at
  `missing_science_packs` while the assembler backed up at `full_output`.
  After moving poles, the agent should re-check nearby inserter/machine power
  status; the camera status feed helps but does not point at the cause.

### 16. Technology enum is missing valid technologies (fixed, needs worker restart)

`Technology` (the enum accepted by `set_research`) lacked
`electric-mining-drill`, even though it is a normal automation-science
technology. Passing a raw string worked ("electric-mining-drill"), but the
typed surface is the documented one. Added
`Technology.ElectricMiningDrill = "electric-mining-drill"` in
`fle/env/game_types.py`; the live envd worker still runs the previously
imported enum, so the enum member is not yet visible in-program until the
worker restarts (raw strings remain the live workaround).

### 17. Blueprint feature drifted off the agent surface (FIXED, pending restage)

Usage audit across 298 trajectories: exactly one `blueprint(...)` call and zero
`place` calls. The cause was surface drift, not disinterest:

- the canonical action reference lost its whole "Blueprint library" block on
  2026-09-09 (`2f31a9ba`), no `agent.md` ever existed, and the MCP execute
  description omitted the call, so every prompt was silent;
- `blueprint.save(...)` method syntax raised `AttributeError`: the namespace
  exposed the hook-wrapper function, not the tool instance
  (`functools.wraps` does not copy class methods);
- `_tick()` read `namespace.get_elapsed_ticks`, which does not exist, so
  `created_tick`/`last_used_tick` were always `None`.

Fixes: restored the blueprint block in `fle/envd/action_reference.py` (bumped to
`reference-v2`), added `fle/env/tools/agent/blueprint/agent.md` so the knowledge
surface can rediscover it, listed the call in the MCP execute description, added
command-dispatching method shims in `fle/env/lua_manager.py` so both
`blueprint('save', ...)` and `blueprint.save(...)` route through hooks, fixed
`_tick()`, made save/place return `{"error": ...}` for store failures, and made
failed revives refund their materials and clear the leftover ghost
(`blueprint/server.lua`). Scoped stores now derive their scope from
`lineage_id` when no explicit scope is set, so blueprints and templates persist
for the map lineage across checkpoints and releases. Known remaining gap:
multi-agent scoped stores attach only to the first namespace.

### 18. New: realtime pacing and program templates (pending restage)

- `factorio_set_realtime(enabled, speed)` plus
  `POST /v1/leases/{id}/realtime` and an observation `realtime` field. Default
  remains paused-while-thinking; realtime keeps the world running between
  interventions at 1x-10x (never below 1), and release/start reset to paused.
- Program templates: `fle/envd/templates.py` store with `{{parameter}}`
  expansion, `PUT/GET/DELETE /v1/leases/{id}/templates` plus
  `POST .../templates/{name}/run`, five MCP tools, `ActionEvent.template`
  metadata, observation `templates` summaries, and `template_scope` on the task
  spec. Templates are expanded with JSON literals, validated by the canonical
  program policy at save and run time, and hash the expanded source, so they
  grant no new powers and replay exactly like hand-written programs.
- Tests: `tests/envd/test_program_templates.py`,
  `tests/envd/test_realtime_pacing.py`, MCP schema/dispatch assertions; default
  suite 628 passed.

### 19. Live validation on the restaged runtime (2026-09-11)

All new surfaces were validated against a freshly restaged cluster + envd:

- Realtime: `factorio_set_realtime(enabled=True, speed=5)` produced
  `paused: false` and 601 native ticks in 2.0s wall time (2s x 5 x 60); ticks
  advanced 568200 -> 568801, and disabling paused immediately. The observation's
  `realtime` block now reports the true pause state (the first patch read
  `instance.is_paused()`, which is not proxied, and always reported paused).
- Program templates: save/list/run roundtrip worked through the MCP tools; an
  `import os` body was rejected with the canonical policy message.
- Blueprint: `blueprint.list()` method syntax works and is recorded as the
  `blueprint` tool call; save/pickup/place-by-name debited the exact bill
  (`items_consumed {'stone-furnace': 1}`), an already-built re-place created no
  ghosts, and pickup recovered the furnace. `times_placed` incremented.
- Trigger-gated research: `set_research('oil-processing')` now raises
  `Technology oil-processing is trigger-gated (mine-entity: crude-oil);
  complete the trigger in-game to unlock it`.
- Pickup preservation: picking up a fueled furnace returned the furnace plus
  exactly the inserted wood.

## Primitive feedback (training/eval relevance)

- The camera (coarse terrain layers + entity tooltips + PNG + status-change
  journal) is the strongest observation primitive; it needs to be unbreakable.
- The status feed (`status_changes` with severity and revision) correctly
  surfaced `no_fuel -> working` transitions during bootstrap.
- Exact-target `move_to` failures carry actionable diagnostics (`stop_distance`
  suggestion); this worked well when walking onto a tree patch.
- `move_to`/placement diagnostics are prescriptive; keep the pattern.
- `nearest(Resource.X)` returns positions and is the reliable starting point for
  resource bootstrap when `get_entities` cannot see neutral entities.
- Fluid-machine feedback (`no fluid present in connections`, `no input liquid`)
  tells an agent that something is wrong but not what to do. Port-aware
  diagnostics (which port faces what) would be the highest-value addition for
  the power bootstrap.

## Session state

The pre-restart world described in findings 1-16 is archived; the cluster was
restaged on 2026-09-11 with every pending change live and validated (finding 19).
Current state:

- Fresh lease `16f730e4...` in mode `rocket_launch` with
  `lineage_id=play-rocket_launch`, so the blueprint and template stores are
  map-lineage scoped (they survive checkpoint restores and lease releases).
- Starter kit only: burner drill, stone furnace, one wood.
- Map-lineage library already holds blueprint `furnace` (times_placed=2) and
  program template `smoke`.
- Observer relaunched; envd on `http://127.0.0.1:8183` with the restaged runtime.
- Milestones 0/7 on this map; the next step is a blueprint/template-assisted
  speedrun of the bootstrap (power, iron/copper, science line) before the oil
  expedition.
- Code changes in the working tree are uncommitted: `set_research` trigger
  message, `pickup_entity` inventory preservation (with alias dedupe),
  `Technology.ElectricMiningDrill`, blueprint surface restore, realtime pacing,
  program templates, lineage-scoped artifacts, and the `realtime_allowed` flag.



