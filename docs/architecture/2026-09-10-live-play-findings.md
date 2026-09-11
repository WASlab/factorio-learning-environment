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

### 7. Placement diagnostics can name a non-overlapping entity (open)

A drill placement at `(0,-2)` was rejected with `reason: "occupied"` and
`overlapping_entities` listing the crash-site spaceship at `(-5,-6)` — several
tiles away and not inside the reported footprint. The placement was genuinely
rejected (moving away solved it), but the evidence pointed at the wrong entity.
Worth tightening the collision-context selection to only entities whose
collision boxes intersect the footprint.

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

## Session state

- Camera + alert fixes committed (`e8634dba`, `faf08349`) and verified live.
- Fresh envd + freeplay lease after the last restart; observer connected.
- Progress: reclaimed verification drill; harvested 20 wood; burner drill on
  the iron patch at `(-18,-49)` feeding a chest at `(-16.5,-49.5)`; stone
  furnace at `(-14,-49)` smelting hand-fed ore (iron-plate recipe active).
- Next: coal run (40,-82) for sustained fuel, more drills/furnaces, and a
  burner-inserter hop from chest to furnace; then automation science and the
  technology milestones.

