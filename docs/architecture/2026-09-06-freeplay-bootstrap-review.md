# Freeplay bootstrap validation

Fresh benchmark freeplay sessions now use the base game's freeplay defaults
and crash-site generator through `initialize_freeplay`. The agent character
receives the normal starter equipment; ship and debris loot stay in their
containers. This headless initialization does not run the player cutscene.
Checkpoint restores do not repeat fresh-world initialization.

Native validation uncovered three defects in the bootstrap tool boundary:

- Harvesting selected neighboring entities outside mining reach and treated
  the number of ore entities as the number of mined items. It now selects an
  in-range entity explicitly and reports actual inventory gains. Stalled
  mining is cancelled after 30 simulated seconds without progress.
- Walking skipped obstacle corners, steered directly toward sparse targets,
  and counted oscillation as progress. It now follows short segment targets,
  preserves corner clearance, and detects failure to approach a waypoint.
  Native path requests use normal resolution and cannot cross owned entities.
  The previous coarse request produced a final segment through a dead tree.
- Missing entities and integer directions produced misleading Python errors.
  They now produce actionable lookup and argument errors.

The bundled runtime exposes a source fingerprint. Connecting with changed or
unversioned runtime code fails before loading tools, so updating the archive
without restarting Factorio cannot silently leave old Lua active.

Run `uv run python scripts/validate_freeplay_bootstrap.py` on the dedicated
reference cluster described in [reference-factory.md](reference-factory.md).
It resets only ports 27010/27011 and leaves the test world paused.

The 2026-09-06 native Factorio 2.0.77 run at 10x speed passed: one crashed
ship, starter drill and furnace, eight wood from a five-wood request (whole
trees), five stone, five iron ore, ten coal, crafting, furnace and drill
placement, fuel insertion, and five smelted plates. The drill mined coal;
this bootstrap test does not establish autonomous factory throughput.
The related focused suite passed 80 tests, with two deselected by the
`no_factorio` marker. The local result is recorded in
`.runtime/reference-factory/freeplay-bootstrap-validation.json`.
