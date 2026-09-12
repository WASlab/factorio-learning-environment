# Changes from upstream FLE

FactorioAgentBench builds on the [Factorio Learning Environment](https://github.com/JackHopkins/factorio-learning-environment).
FLE supplies the original Factorio runtime, Python/Lua tools, REPL, Gym and agent
infrastructure, rendering, datasets, and evaluation utilities. Those are inherited
work, not features originated by this fork. Upstream history, authorship, and
licensing remain intact.

## Scope and baseline

This inventory covers committed development through `b634604b` (September 12,
2026), compared with the shared FLE base
[`f748ec452dfa79f6a57a12ddcff1ff9102cdb11f`](https://github.com/JackHopkins/factorio-learning-environment/commit/f748ec452dfa79f6a57a12ddcff1ff9102cdb11f)
(`fix(get_path): raise path polling budget`, local branch `fle-base-main`). It
describes the fork's development code, not a published package release or a
comparison against today's upstream main. Uncommitted work is excluded.

The sections below group the behavioral changes. The complete net file inventory
at the end includes code, tests, data, result artifacts, documentation, and
deletions. Architecture documents contain both implemented behavior and design
proposals; their proposals are not automatically implemented features.

## Environment service and verification

- Added `fle.envd`: typed task and action records, task fingerprints, a lease HTTP
  API and client, environment capacity management, per-lease serialized execution,
  pause/resume, snapshots, restoration, finalization, and release.
- Added a local FLE/RCON worker backend and an AgentENV gateway for isolated
  training runtimes. AgentENV deployment and compatibility files live separately
  from the local runtime.
- Added restricted program execution and explicit action profiles, intervention
  accounting, durable execution artifacts, bounded state reads, native
  verification, and signed receipts. Public observations are separated from
  hidden task generation, scoring, audit evidence, and privileged teacher data.
- Added persistent-state quality comparisons, native objective telemetry, task
  construction, deterministic task catalogs, and benchmark result validation.

Sources: [envd](fle/envd/), [stack boundary](docs/architecture/factorio-rlvr-stack.md),
[AgentENV integration](integrations/agentenv/README.md).

## Persistent benchmark objectives and scoring

- Added customer contracts with seeded hidden demand, protected customer sink
  depots, delivery accounting, deadlines, service/reliability scoring, and sealed
  receipts. Internal production counts alone do not satisfy delivery contracts.
- Added adaptive requisition sessions that retain the same factory across orders:
  capability graphs and certificates, contextual contract features, generation,
  selection, calibration, conservative TrueSkill ratings, uncertainty, and
  reconstructable epoch records. Training curriculum/replay policies are distinct
  from official evaluation policy.
- Added sustained-throughput qualification. Cheap native production-rate reads
  identify audit candidates; dedicated unleased workers restore candidate states
  and run autonomous holdouts. Passing audits can finish sustained orders early;
  failed hidden audits leave the source factory unchanged.
- Added resource, power, logistics, and enemy disruptions with recovery
  measurement; map generations, lineage, fresh/inherited/pathological episode
  selection, retirement, and checkpoint pools.
- Added independent technology and rocket-launch evaluations with engine-verified
  research milestones and launch-counter changes, public progress, terminal
  precedence rules, budgets, and checkpoint recovery.
- Added versioned API microtasks, manifests, benchmark runners, strict/development
  baseline artifacts, full trajectories, and publication validation. Historical
  baselines are separate from persistent factory evaluations.

Sources: [contract substrate](docs/architecture/factorio-contract-benchmark.md),
[adaptive benchmark](docs/architecture/adaptive-contract-benchmark.md),
[throughput audits](docs/architecture/throughput-qualification-and-early-termination.md),
[evaluation modes](docs/architecture/evaluation-modes.md),
[microbenchmark guide](benchmark/README.md).

## Harnesses, memory, and reusable work

- Added native model, Codex, OpenCode, and Hermes evaluation workflows, persistent
  conversations, checkpoint/resume handling, timing records, and partial results.
- Added a lease-bound MCP adapter with typed routes for actions, live observations,
  immutable references, retained results, and session memory. Independent safe
  reads may run concurrently; world operations retain per-lease ordering.
- Added bounded tool history, execution-result retrieval, searchable session
  memory, pinned recipe/prototype knowledge, and memory profile identity.
- Added scoped blueprint storage and native placement with material/time costs,
  plus agent-authored parameterized program templates for saving and reusing
  explicit programs.
- Added the `factorio_v1` Verifiers adapter, Prime-RL bootstrap and compatibility
  configuration, a separately packaged `factorio_microtasks` environment, and
  remote model/host workflows. Training infrastructure remains external to FLE.

Sources: [tool contract](docs/architecture/tool-calling-compatibility.md),
[memory and knowledge](docs/architecture/factorio-agent-memory-and-knowledge.md),
[scripts](scripts/), [Prime integration](integrations/prime/README.md),
[microtasks package](environments/factorio_microtasks/README.md).

## Agent actions and public game information

- Added semantic motor execution and an action queue with submission, inspection,
  insertion, cancellation, and resumption. Default execution pauses during model
  reasoning and advances on simulation ticks during actions. Optional realtime
  pacing keeps the world running between interventions and reports that mode.
- Added or extended movement, harvesting, exact placement, rotation, pickup,
  transfers, crafting, research, rocket launch, delivery-chest selection, and
  explicit pattern/grid/path/power-line construction helpers. The file inventory
  distinguishes additions from changes to inherited tools.
- Added bounded waits on public conditions and simulation deadlines, explicit
  termination reasons, and transport timing. Crafting completes within the
  intervention; queue inspection/cancellation and a stateless crafting-menu read
  expose native craftability and ingredient differences.
- Added exact tile maps, machine connection ports, and belt tracing. Spatial
  failures retain the requested target and expose bounded collision/terrain
  diagnostics instead of silently choosing another destination or build.
- Added live technology details, available research, research queues, inverse
  recipe lookup, force bonuses, production/consumption statistics, logistic and
  circuit network reads, train/station information, and bounded pollution reads.
- Added sampled machine-status transitions, stable entity identity, observation
  revisions, bounded journals, retention-gap reporting, and reconnect reads.
- Added a persistent configurable camera, coarse wide-area maps, nearby machine
  tooltips, visible terrain/obstacles/characters, public objective overlays, and
  image routing through supported harnesses.

Sources: [action reference](fle/envd/action_reference.py),
[tool implementations and agent documentation](fle/env/tools/agent/),
[observation parity](docs/architecture/player-observation-parity.md),
[crafting menu](docs/architecture/crafting-menu.md).

## Runtime fixes and operational changes

- Corrected direction normalization across Python/Lua actions and rendering,
  burner-drill output geometry, drill-feed status, real machine alert icons, and
  resource-aware placement diagnostics.
- Hardened missing-entity and placement errors, exact coordinate handling, path
  requests/polling, crafting completion, action accounting, response
  serialization, integer-keyed Lua array decoding, and runtime error reporting.
- Extended game/research state persistence and engine identity handling; added
  freeplay initialization and objective counters used by progression verification.
- Restored MCP resources and recipe data lookup, made MCP state initialization
  lazy to avoid import-time resets, and surfaced camera render failures.
- Added capture-cycle caching to reduce repeated intervention work. Public reads,
  camera detail, journals, and condition waits use bounded queries or sampling.
- Extended cluster provisioning with a runtime scenario, server configuration,
  observer camera, watching, and platform-specific launch behavior.

Sources: [runtime code](fle/env/), [cluster guide](fle/cluster/README.md),
[runtime error review](docs/architecture/2026-09-07-runtime-error-review.md),
[live findings and validation records](docs/architecture/2026-09-10-live-play-findings.md).

## Packaging, tests, and project documentation

- Established the FactorioAgentBench identity, architecture/usage documents,
  project site, blog syndication, and GitHub Pages publishing workflow.
- Retained the `fle` namespace and temporary `factorio-learning-environment`
  distribution name. This fork must not publish over the upstream distribution;
  installing the upstream package does not install these development changes.
- Added `fle-envd`, `fle-benchmark`, and `fle-benchmark-results` entry points,
  packaged `factorio_v1`, added Prime/rating/calibration/MCP dependencies, and
  constrained the A2A SDK to the API used by FLE. See the authoritative
  [package configuration](pyproject.toml).
- Added offline contract, service, scoring, lifecycle, memory, transport, runtime,
  and harness tests; Lua/Python boundary checks; isolated live validation scripts;
  a reference factory fixture; and benchmark artifact CI.
- Separated `factorio_live` tests from the default suite and identified
  server-free checks with `no_factorio`. Removed obsolete, assertion-free, and
  redundant tests and consolidated repeated cases.

This is an inventory of changes, not a claim that every supported configuration
has passed live validation. Individual architecture and validation records state
the tested boundaries. No new runtime validation is implied by this document.

## Reproduce or update the comparison

From this repository, the exact documented comparison is:

```sh
git log --reverse --oneline f748ec452dfa79f6a57a12ddcff1ff9102cdb11f..b634604b
git diff --stat f748ec452dfa79f6a57a12ddcff1ff9102cdb11f b634604b
git diff --name-status f748ec452dfa79f6a57a12ddcff1ff9102cdb11f b634604b
```

To refresh this inventory, select a new committed endpoint, review its code and
architecture contracts, update the sections above, and regenerate the inventory
below. Retain the base SHA unless deliberately changing the upstream comparison.

## Complete net file inventory

`A` = added, `M` = modified, `D` = deleted; rename records include both paths.
This records net differences at the documented endpoint, including retained
benchmark evidence. Intermediate additions later removed appear in Git history.

<details>
<summary>Expand all 553 changed files</summary>

```text
A	.github/workflows/benchmark-results.yml
M	.github/workflows/factorio-test.yml
A	.github/workflows/site.yml
M	.gitignore
A	AGENTS.md
M	README.md
A	benchmark/README.md
A	benchmark/blind_subagent_broker.py
A	benchmark/codex_developer_baseline.py
A	benchmark/data/factorio-2.0.73-contract-game-data.json
A	benchmark/data/factorio-2.0.77-contract-game-data.json
A	benchmark/manifests/benchmark-0.2.0-dev.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_automate_electronic_circuit_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_automate_iron_gear_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_automate_red_science_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_automate_steel_plate_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_configure_assembler_recipe_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_configure_centrifuge_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_configure_chemical_plant_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_configure_oil_refinery_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_craft_iron_gear_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_fuel_furnace_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_harvest_coal_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_install_speed_module_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_load_lab_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_place_entity_next_to_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_place_lab_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_place_pumpjack_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_place_roboport_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_place_rocket_silo_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_research_logistics_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_start_furnace_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x-trajectories/micro_transfer_to_chest_v1-attempt-0.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x.json
A	benchmark/results/deepseek-v4-flash-full-strict-1x.summary.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_automate_electronic_circuit_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_automate_iron_gear_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_automate_red_science_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_automate_steel_plate_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_configure_assembler_recipe_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_configure_centrifuge_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_configure_chemical_plant_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_configure_oil_refinery_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_craft_iron_gear_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_fuel_furnace_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_harvest_coal_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_install_speed_module_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_load_lab_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_place_entity_next_to_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_place_lab_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_place_pumpjack_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_place_roboport_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_place_rocket_silo_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_research_logistics_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_start_furnace_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer-trajectories/micro_transfer_to_chest_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-developer.json
A	benchmark/results/gpt-5.6-sol-developer.summary.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_automate_iron_gear_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_automate_steel_plate_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_configure_assembler_recipe_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_craft_iron_gear_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_fuel_furnace_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_harvest_coal_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_install_speed_module_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_load_lab_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_place_entity_next_to_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_place_lab_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development-trajectories/micro_place_pumpjack_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development.json
A	benchmark/results/gpt-5.6-sol-medium-blind-development.summary.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_automate_iron_gear_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_automate_steel_plate_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_configure_assembler_recipe_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_craft_iron_gear_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_fuel_furnace_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_harvest_coal_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_install_speed_module_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_load_lab_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_place_entity_next_to_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_place_lab_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development-trajectories/micro_place_pumpjack_v1-attempt-0.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development.json
A	benchmark/results/gpt-5.6-sol-xhigh-blind-development.summary.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_automate_iron_gear_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_automate_steel_plate_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_configure_assembler_recipe_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_craft_iron_gear_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_fuel_furnace_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_harvest_coal_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_install_speed_module_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_load_lab_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_place_entity_next_to_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_place_lab_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development-trajectories/micro_place_pumpjack_v1-attempt-0.json
A	benchmark/results/gpt-5.6-terra-max-blind-development.json
A	benchmark/results/gpt-5.6-terra-max-blind-development.summary.json
A	data/recipes/recipes.jsonl
A	docs/architecture/2026-09-05-delivery-resume-review.md
A	docs/architecture/2026-09-06-freeplay-bootstrap-review.md
A	docs/architecture/2026-09-07-runtime-error-review.md
A	docs/architecture/2026-09-10-live-play-findings.md
A	docs/architecture/adaptive-contract-benchmark.md
A	docs/architecture/crafting-menu.md
A	docs/architecture/evaluation-modes.md
A	docs/architecture/factorio-agent-memory-and-knowledge.md
A	docs/architecture/factorio-contract-benchmark.md
A	docs/architecture/factorio-rlvr-stack.md
A	docs/architecture/player-observation-parity.md
A	docs/architecture/reference-factory.md
A	docs/architecture/requisition-prompt.md
A	docs/architecture/throughput-qualification-and-early-termination.md
A	docs/architecture/tool-calling-compatibility.md
A	docs/benchmark-v0.2.md
A	docs/evaluations/2026-07-26-raider-qwen36-35b.md
A	docs/evaluations/2026-08-09-deepseek-v4-flash.md
A	environments/factorio_microtasks/.prime/.env-metadata.json
A	environments/factorio_microtasks/README.md
A	environments/factorio_microtasks/factorio_microtasks/__init__.py
A	environments/factorio_microtasks/factorio_microtasks/taskset.py
A	environments/factorio_microtasks/pyproject.toml
A	factorio_v1/__init__.py
M	fle/agents/data/blueprints_to_policies/blueprint_analyzer.py
M	fle/agents/data/blueprints_to_policies/blueprint_analyzer_with_connect.py
M	fle/agents/data/blueprints_to_policies/blueprint_analyzer_with_place_next_to.py
M	fle/agents/data/blueprints_to_policies/trajectory_generator.py
M	fle/agents/data/screenshots_from_run.py
M	fle/agents/data/sprites/basis_image_resolver.py
M	fle/agents/data/sprites/extractors/character.py
M	fle/agents/data/sprites/extractors/decoratives.py
M	fle/agents/data/sprites/extractors/entities.py
M	fle/cluster/README.md
M	fle/cluster/config/server-settings.json
A	fle/cluster/config/server-whitelist.json
A	fle/cluster/observer_camera.py
M	fle/cluster/run-envs.sh
M	fle/cluster/run_envs.py
A	fle/cluster/runtime_scenario.py
A	fle/cluster/watch.py
A	fle/commons/directions.py
M	fle/commons/models/game_state.py
M	fle/commons/models/research_state.py
A	fle/env/action_queue.py
M	fle/env/game_types.py
M	fle/env/instance.py
M	fle/env/lua_manager.py
M	fle/env/mods/alerts.lua
A	fle/env/mods/crafting_menu.lua
M	fle/env/mods/initialise.lua
A	fle/env/mods/objective_telemetry.lua
A	fle/env/mods/observer.lua
M	fle/env/mods/serialize.lua
A	fle/env/mods/spatial_diagnostics.lua
A	fle/env/mods/status_monitor.lua
M	fle/env/mods/utils.lua
M	fle/env/namespace.py
M	fle/env/protocols/_mcp/__init__.py
M	fle/env/protocols/_mcp/resources.py
M	fle/env/protocols/_mcp/state.py
A	fle/env/tools/admin/customer_depot/client.py
A	fle/env/tools/admin/customer_depot/server.lua
A	fle/env/tools/admin/entity_census/client.py
A	fle/env/tools/admin/entity_census/server.lua
M	fle/env/tools/admin/get_path/client.py
M	fle/env/tools/admin/get_path/server.lua
A	fle/env/tools/admin/get_recent_rate/client.py
A	fle/env/tools/admin/get_recent_rate/server.lua
A	fle/env/tools/admin/initialize_freeplay/client.py
A	fle/env/tools/admin/initialize_freeplay/server.lua
M	fle/env/tools/admin/inspect_entities/server.lua
A	fle/env/tools/admin/objective_telemetry/client.py
A	fle/env/tools/admin/objective_telemetry/server.lua
A	fle/env/tools/admin/perturbation/client.py
A	fle/env/tools/admin/perturbation/server.lua
A	fle/env/tools/admin/public_status/client.py
A	fle/env/tools/admin/public_status/server.lua
A	fle/env/tools/admin/public_view/client.py
A	fle/env/tools/admin/public_view/server.lua
M	fle/env/tools/admin/render/client.py
M	fle/env/tools/admin/render/renderer.py
M	fle/env/tools/admin/render/server.lua
M	fle/env/tools/admin/render/utils.py
M	fle/env/tools/admin/render_simple/server.lua
M	fle/env/tools/admin/request_path/server.lua
M	fle/env/tools/admin/save_blueprint/server.lua
M	fle/env/tools/admin/save_research_state/client.py
M	fle/env/tools/admin/save_research_state/server.lua
M	fle/env/tools/admin/score/server.lua
M	fle/env/tools/agent.md
A	fle/env/tools/agent/blueprint/agent.md
A	fle/env/tools/agent/blueprint/client.py
A	fle/env/tools/agent/blueprint/server.lua
A	fle/env/tools/agent/cancel_actions/client.py
A	fle/env/tools/agent/cancel_actions/server.lua
A	fle/env/tools/agent/cancel_craft/agent.md
A	fle/env/tools/agent/cancel_craft/client.py
A	fle/env/tools/agent/cancel_craft/server.lua
M	fle/env/tools/agent/craft_item/agent.md
M	fle/env/tools/agent/craft_item/client.py
M	fle/env/tools/agent/craft_item/server.lua
M	fle/env/tools/agent/extract_item/client.py
M	fle/env/tools/agent/extract_item/server.lua
A	fle/env/tools/agent/get_available_technologies/agent.md
A	fle/env/tools/agent/get_available_technologies/client.py
A	fle/env/tools/agent/get_available_technologies/server.lua
A	fle/env/tools/agent/get_circuit_network/agent.md
A	fle/env/tools/agent/get_circuit_network/client.py
A	fle/env/tools/agent/get_circuit_network/server.lua
A	fle/env/tools/agent/get_craft_plan/client.py
A	fle/env/tools/agent/get_craft_plan/server.lua
A	fle/env/tools/agent/get_craft_queue/agent.md
A	fle/env/tools/agent/get_craft_queue/client.py
A	fle/env/tools/agent/get_craft_queue/server.lua
M	fle/env/tools/agent/get_entities/server.lua
A	fle/env/tools/agent/get_entity_ports/client.py
A	fle/env/tools/agent/get_entity_ports/server.lua
A	fle/env/tools/agent/get_force_bonuses/agent.md
A	fle/env/tools/agent/get_force_bonuses/client.py
A	fle/env/tools/agent/get_force_bonuses/server.lua
A	fle/env/tools/agent/get_logistic_network/agent.md
A	fle/env/tools/agent/get_logistic_network/client.py
A	fle/env/tools/agent/get_logistic_network/server.lua
A	fle/env/tools/agent/get_pollution/agent.md
A	fle/env/tools/agent/get_pollution/client.py
A	fle/env/tools/agent/get_pollution/server.lua
A	fle/env/tools/agent/get_production_statistics/agent.md
A	fle/env/tools/agent/get_production_statistics/client.py
A	fle/env/tools/agent/get_production_statistics/server.lua
M	fle/env/tools/agent/get_prototype_recipe/agent.md
M	fle/env/tools/agent/get_prototype_recipe/client.py
A	fle/env/tools/agent/get_recipes_using/agent.md
A	fle/env/tools/agent/get_recipes_using/client.py
A	fle/env/tools/agent/get_recipes_using/server.lua
A	fle/env/tools/agent/get_research_queue/agent.md
A	fle/env/tools/agent/get_research_queue/client.py
A	fle/env/tools/agent/get_research_queue/server.lua
A	fle/env/tools/agent/get_technology/agent.md
A	fle/env/tools/agent/get_technology/client.py
A	fle/env/tools/agent/get_technology/server.lua
A	fle/env/tools/agent/get_tile_map/agent.md
A	fle/env/tools/agent/get_tile_map/client.py
A	fle/env/tools/agent/get_tile_map/server.lua
A	fle/env/tools/agent/get_train_stop/agent.md
A	fle/env/tools/agent/get_train_stop/client.py
A	fle/env/tools/agent/get_train_stop/server.lua
A	fle/env/tools/agent/get_trains/agent.md
A	fle/env/tools/agent/get_trains/client.py
A	fle/env/tools/agent/get_trains/server.lua
M	fle/env/tools/agent/harvest_resource/agent.md
M	fle/env/tools/agent/harvest_resource/client.py
M	fle/env/tools/agent/harvest_resource/server.lua
A	fle/env/tools/agent/insert_actions/client.py
A	fle/env/tools/agent/insert_actions/server.lua
M	fle/env/tools/agent/insert_item/agent.md
M	fle/env/tools/agent/insert_item/client.py
M	fle/env/tools/agent/insert_item/server.lua
A	fle/env/tools/agent/inspect_action_queue/client.py
A	fle/env/tools/agent/inspect_action_queue/server.lua
M	fle/env/tools/agent/inspect_inventory/server.lua
M	fle/env/tools/agent/launch_rocket/agent.md
M	fle/env/tools/agent/launch_rocket/client.py
M	fle/env/tools/agent/launch_rocket/server.lua
M	fle/env/tools/agent/move_to/agent.md
M	fle/env/tools/agent/move_to/client.py
M	fle/env/tools/agent/move_to/server.lua
M	fle/env/tools/agent/nearest/agent.md
M	fle/env/tools/agent/nearest/client.py
M	fle/env/tools/agent/pickup_entity/client.py
M	fle/env/tools/agent/pickup_entity/server.lua
A	fle/env/tools/agent/place_between/client.py
A	fle/env/tools/agent/place_between/server.lua
M	fle/env/tools/agent/place_entity/agent.md
M	fle/env/tools/agent/place_entity/client.py
M	fle/env/tools/agent/place_entity/server.lua
M	fle/env/tools/agent/place_entity_next_to/client.py
A	fle/env/tools/agent/place_grid/client.py
A	fle/env/tools/agent/place_grid/server.lua
A	fle/env/tools/agent/place_offshore_pump/client.py
A	fle/env/tools/agent/place_offshore_pump/server.lua
A	fle/env/tools/agent/place_path/client.py
A	fle/env/tools/agent/place_path/server.lua
A	fle/env/tools/agent/place_power_line/client.py
A	fle/env/tools/agent/place_power_line/server.lua
A	fle/env/tools/agent/queue_craft/agent.md
A	fle/env/tools/agent/queue_craft/client.py
A	fle/env/tools/agent/queue_craft/server.lua
A	fle/env/tools/agent/queue_research/client.py
A	fle/env/tools/agent/queue_research/server.lua
A	fle/env/tools/agent/repeat_pattern/client.py
A	fle/env/tools/agent/repeat_pattern/server.lua
A	fle/env/tools/agent/resolve_entity/client.py
A	fle/env/tools/agent/resolve_entity/server.lua
A	fle/env/tools/agent/resume_actions/client.py
A	fle/env/tools/agent/resume_actions/server.lua
M	fle/env/tools/agent/rotate_entity/client.py
M	fle/env/tools/agent/score/server.lua
A	fle/env/tools/agent/set_delivery_chest/client.py
A	fle/env/tools/agent/set_delivery_chest/server.lua
M	fle/env/tools/agent/set_entity_recipe/agent.md
M	fle/env/tools/agent/set_entity_recipe/client.py
M	fle/env/tools/agent/set_research/server.lua
M	fle/env/tools/agent/sleep/client.py
M	fle/env/tools/agent/sleep/server.lua
A	fle/env/tools/agent/submit_actions/client.py
A	fle/env/tools/agent/submit_actions/server.lua
A	fle/env/tools/agent/trace_belt/agent.md
A	fle/env/tools/agent/trace_belt/client.py
A	fle/env/tools/agent/trace_belt/server.lua
A	fle/env/tools/agent/transfer_item/client.py
A	fle/env/tools/agent/transfer_item/server.lua
A	fle/env/tools/agent/wait/agent.md
A	fle/env/tools/agent/wait/client.py
A	fle/env/tools/agent/wait/server.lua
M	fle/env/tools/controller.py
A	fle/env/tools/observation.py
A	fle/env/tools/spatial.py
M	fle/env/tools/tool.py
M	fle/env/utils/controller_loader/type_definition_processor.py
A	fle/envd/__init__.py
A	fle/envd/__main__.py
A	fle/envd/action_reference.py
A	fle/envd/agentenv.py
A	fle/envd/api.py
A	fle/envd/backend.py
A	fle/envd/benchmark.py
A	fle/envd/benchmark_results.py
A	fle/envd/blueprints.py
A	fle/envd/camera.py
A	fle/envd/capability_certificates.py
A	fle/envd/capability_graph.py
A	fle/envd/client.py
A	fle/envd/contract_calibration.py
A	fle/envd/contract_curriculum.py
A	fle/envd/contract_features.py
A	fle/envd/contract_generator.py
A	fle/envd/contract_policy.py
A	fle/envd/contract_rating.py
A	fle/envd/contract_selector.py
A	fle/envd/curriculum.py
A	fle/envd/customer.py
A	fle/envd/delivery.py
A	fle/envd/errors.py
A	fle/envd/evaluation_modes.py
A	fle/envd/follow_up.py
A	fle/envd/knowledge.py
A	fle/envd/lifecycle.py
A	fle/envd/memory.py
A	fle/envd/microtasks.py
A	fle/envd/models.py
A	fle/envd/objective_engine.py
A	fle/envd/perturbations.py
A	fle/envd/program_policy.py
A	fle/envd/service.py
A	fle/envd/status_journal.py
A	fle/envd/task_builder.py
A	fle/envd/templates.py
A	fle/eval/benchmark_agent.py
M	fle/eval/inspect/integration/experiments/condensed_prompts.py
M	fle/eval/inspect/sandbox/Dockerfile
A	fle/eval/remote_agent.py
M	fle/eval/tasks/task_definitions/lab_play/throughput_tasks.py
A	fle/integrations/__init__.py
A	fle/integrations/prime_v1/__init__.py
A	fle/integrations/prime_v1/taskset.py
M	fle/overlay.py
M	fle/run.py
A	integrations/agentenv/Dockerfile
A	integrations/agentenv/README.md
A	integrations/agentenv/compatibility.toml
A	integrations/agentenv/entrypoint.sh
A	integrations/agentenv/smoke.py
A	integrations/deepseek/Invoke-DeepSeekBenchmark.ps1
A	integrations/deepseek/README.md
A	integrations/prime/DSpark.md
A	integrations/prime/README.md
A	integrations/prime/bootstrap.py
A	integrations/prime/compatibility.toml
A	integrations/prime/rl-dspark-smoke.toml
A	integrations/prime/rl-smoke.toml
A	integrations/raider/Invoke-FactorioRaiderEval.ps1
A	integrations/raider/README.md
M	pyproject.toml
A	scripts/adaptive_contract_benchmark.py
A	scripts/codex_benchmark.py
A	scripts/export_contract_game_data.py
A	scripts/factorio_codex_mcp.py
A	scripts/hermes_benchmark.py
A	scripts/list_free_models.py
A	scripts/progression_benchmark.py
A	scripts/validate_craft_menu.py
A	scripts/validate_freeplay_bootstrap.py
A	scripts/validate_native_runtime_regressions.py
A	scripts/validate_player_observation.py
A	scripts/validate_progression_modes.py
A	scripts/validate_public_status.py
A	scripts/validate_public_view.py
A	scripts/validate_public_waits.py
A	scripts/validate_reference_factory.py
A	scripts/validate_spatial_diagnostics.py
A	site/.nojekyll
A	site/assets/current-factory.png
A	site/blog/blog.css
A	site/blog/feed.json
A	site/blog/ideal-rl-environment/index.html
A	site/blog/index.html
A	site/blog/syndication.js
A	site/favicon.ico
A	site/index.html
A	site/styles.css
D	tests/actions/_test_inspect_entities.py
D	tests/actions/_test_shift_entity.py
A	tests/actions/test_action_queue.py
A	tests/actions/test_bootstrap_regressions.py
M	tests/actions/test_craft.py
A	tests/actions/test_craft_menu.py
A	tests/actions/test_customer_depot_client.py
M	tests/actions/test_elapsed_ticks.py
M	tests/actions/test_extract_item.py
M	tests/actions/test_get_entities.py
M	tests/actions/test_get_entity.py
M	tests/actions/test_get_resource_patch.py
M	tests/actions/test_harvest_resource.py
M	tests/actions/test_insert_item.py
M	tests/actions/test_inspect_inventory.py
M	tests/actions/test_logistic_chests.py
M	tests/actions/test_move_to.py
A	tests/actions/test_native_runtime_regressions.py
M	tests/actions/test_nearest_buildable.py
A	tests/actions/test_nearest_validation.py
M	tests/actions/test_place_entity_next_to.py
A	tests/actions/test_place_path_blocker.py
A	tests/actions/test_player_information.py
M	tests/actions/test_print_in_functions.py
A	tests/actions/test_production_statistics.py
A	tests/actions/test_public_status.py
A	tests/actions/test_public_view.py
D	tests/actions/test_render.py
D	tests/actions/test_request_path.py
M	tests/actions/test_rotate.py
A	tests/actions/test_semantic_motor_units.py
M	tests/actions/test_set_entity_recipe.py
A	tests/actions/test_spatial_diagnostics.py
A	tests/actions/test_tile_map.py
A	tests/actions/test_tool_argument_errors.py
A	tests/actions/test_trace_belt.py
A	tests/actions/test_wait.py
A	tests/agents/test_basis_sprite_extractor.py
A	tests/agents/test_camera_sprites.py
D	tests/benchmarks/test_demo_video.py
D	tests/benchmarks/test_script_caching.py
M	tests/blueprints/test_blueprint_based_policies.py
M	tests/blueprints/test_save_load.py
M	tests/complex/test_edge_cases.py
D	tests/complex/test_slow.py
M	tests/conftest.py
M	tests/connect/test_connect_pipes.py
M	tests/connect/test_connect_poles.py
M	tests/connect/test_connect_transport_belts.py
M	tests/connect/test_connect_underground_pipes.py
M	tests/connect/test_fluid_handlers.py
M	tests/entities/test_assemblers.py
M	tests/entities/test_fluid_processors.py
M	tests/entities/test_inserters.py
M	tests/entities/test_modules.py
A	tests/envd/__init__.py
A	tests/envd/conftest.py
A	tests/envd/test_adaptive_contract_backend.py
A	tests/envd/test_agentenv.py
A	tests/envd/test_api.py
A	tests/envd/test_backend.py
A	tests/envd/test_benchmark.py
A	tests/envd/test_benchmark_agent.py
A	tests/envd/test_benchmark_ladder.py
A	tests/envd/test_benchmark_results.py
A	tests/envd/test_blueprints.py
A	tests/envd/test_blueprints_live.py
A	tests/envd/test_camera.py
A	tests/envd/test_capability_certificates.py
A	tests/envd/test_contract_calibration.py
A	tests/envd/test_contract_curriculum.py
A	tests/envd/test_contract_features.py
A	tests/envd/test_contract_generator.py
A	tests/envd/test_contract_policy.py
A	tests/envd/test_contract_rating.py
A	tests/envd/test_contract_selector.py
A	tests/envd/test_customer.py
A	tests/envd/test_customer_live.py
A	tests/envd/test_delivery_resume_clock.py
A	tests/envd/test_evaluation_modes.py
A	tests/envd/test_factorio_codex_mcp.py
A	tests/envd/test_finalize_transport.py
A	tests/envd/test_game_state_restore.py
A	tests/envd/test_hermes_benchmark.py
A	tests/envd/test_launch_tracking.py
A	tests/envd/test_lifecycle.py
A	tests/envd/test_memory_and_knowledge.py
A	tests/envd/test_objective_engine.py
A	tests/envd/test_perturbations.py
A	tests/envd/test_perturbations_live.py
A	tests/envd/test_program_templates.py
A	tests/envd/test_public_status_receipts.py
A	tests/envd/test_realtime_pacing.py
A	tests/envd/test_reference_factory_live.py
A	tests/envd/test_remote_agent.py
A	tests/envd/test_research_state_identity.py
A	tests/envd/test_service.py
A	tests/envd/test_state_observation.py
A	tests/envd/test_status_journal.py
A	tests/envd/test_task_builder.py
A	tests/envd/test_throughput_audit.py
A	tests/envd/test_tool_calling_compatibility.py
D	tests/eval/_test_recursive_formatter_functional.py
M	tests/eval/samplers/test_kld_mean_sampler.py
D	tests/eval/samplers/test_python_parser.py
M	tests/eval/samplers/test_weighted_reward_sampler.py
M	tests/eval/test_achievements.py
M	tests/eval/test_conversation_formatter.py
M	tests/eval/test_game_state.py
D	tests/eval/test_production_divergence.py
M	tests/eval/test_python_parser.py
M	tests/eval/test_recursive_formatter.py
A	tests/fixtures/reference_iron_factory.lua
M	tests/functional/test_electricity_unit.py
M	tests/functional/test_objectives.py
M	tests/gym_env/test_observation_formatter.py
M	tests/gym_env/test_registry.py
M	tests/invariants/test_entity_lifecycle.py
M	tests/invariants/test_placement_invariants.py
M	tests/mcp/test_mcp.py
D	tests/multiagent/test_actions_multiagent.py
M	tests/multiagent/test_agent_instructions.py
D	tests/multiagent/test_messages.py
A	tests/prime/__init__.py
A	tests/prime/test_microtasks_package.py
A	tests/prime/test_taskset.py
M	tests/render/test_assembler_recipes.py
A	tests/scripts/test_adaptive_contract_benchmark.py
A	tests/scripts/test_openai_tool_batch_compatibility.py
A	tests/scripts/test_opencode_timing.py
A	tests/scripts/test_progression_benchmark.py
M	tests/test_character_persistence.py
A	tests/test_cluster.py
M	tests/test_eval.py
A	tests/test_game_control.py
A	tests/test_instance_timeout_recovery.py
A	tests/test_mcp_state_lazy.py
A	tests/test_observer_camera.py
M	tests/test_production_stats.py
A	tests/test_render_direction_normalization.py
A	tests/test_run.py
A	tests/test_runtime_identity.py
M	tests/test_variables.py
A	tests/test_watch.py
```

</details>
