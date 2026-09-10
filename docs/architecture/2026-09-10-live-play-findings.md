# Live Play Findings — 2026-09-10

Live session: canonical agent surface (`envd` lease + `factorio_execute_program`)
against the local Docker pair, fresh freeplay (`progression_task_spec("rocket_launch")`),
observer window connected as `fle-observer`, all seven objectives enabled.

Local session tooling (gitignored): `.runtime/play/` — `create_lease.py`,
`play_mcp.py` (stdio driver for `scripts/factorio_codex_mcp.py`), repro scripts.

## Incidents

### 1. Camera image crash on non-cardinal directions (fixed)

`GET /camera` returned `image_error: "2"` while the rest of the observation was
healthy. Root cause: the public camera view feeds `_public_view` entities into
the sprite renderers, whose `DIRECTIONS` maps contain only Factorio 2.0 cardinals
(`0/4/8/12`); any other direction value (legacy 8-direction or diagonal 16-direction)
raised `KeyError`, and the handler collapsed it to `str(exc)`.

- Evidence: repro in `.runtime/play/repro_camera.py`; `burner_mining_drill.py:24`.
- Fix: `fle/envd/camera.py::normalize_render_direction`, applied in
  `FLEWorker.camera()` before `render_factory`; handler now reports
  `type(exc).__name__` too. Unit coverage in `tests/envd/test_camera.py`.

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
