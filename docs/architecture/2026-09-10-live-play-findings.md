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

### 5. Drill output / ground-item trap (observed once, unresolved)

A mining drill that dropped one ore before its sink existed reported
`output blocked by item on the ground. There is no sink entity in place to
accept the output.` Replacing the furnace did not clear it immediately, and
walking the tile did not show the item in inventory. Whether a ground item
persisted under the re-placed furnace was not conclusively established. No
primitive exists for picking up ground items.

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

- World wiped by incident 2; re-leased fresh freeplay after the camera fix.
- Camera fix commit: `fle/envd` + tests (see git log for the session).
