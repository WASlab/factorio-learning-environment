# Freeplay evaluation modes

The evaluation launcher selects one of three objectives with `--mode`:

| Mode | Objective | Result |
| --- | --- | --- |
| `requisitions` | Meet adaptive production requisitions in a persistent factory | Existing contract outcomes and capability rating |
| `technology` | Complete six research milestones from fresh freeplay | Verified milestone completion, success, simulation and wall time |
| `rocket_launch` | Complete one new rocket launch from fresh freeplay | Engine-confirmed launch, success, simulation and wall time |

Requisitions remain the default. Technology and rocket launch are independent
evaluations, not extra requisition types or inputs to the requisition rating.
Each uses the same native, OpenCode, or Hermes harness and public Factorio tools.

## Goals and verification

The authoritative definitions are in
[`evaluation_modes.py`](../../fle/envd/evaluation_modes.py). Technology milestones
are automation, logistic, chemical, production, and utility science-pack
technologies, followed by rocket silo. All six must be researched. This is a
milestone evaluation, not an exhaustive completion of every optional or infinite
technology. Rocket mode exposes those research milestones as progress indicators;
its required goal is one new launch.

Research uses completed engine research state. Queued research or a progress bar
at 100% is not a substitute for completion. Rocket progress uses the increase in
the force's engine launch counter relative to the task baseline. Accepting a launch
request, building a silo, or preparing a rocket does not complete the evaluation.

The worker checks the goals after actions and returns a public
`evaluation_progress` in execution results and observations. The MCP receipt
preserves this view. It contains only the advertised milestones, their completion,
simulation time, launches, and terminal status. Finalization independently uses
the native verifier over paused authoritative state. It does not advance the game
to create additional progress during scoring.

Death takes precedence over goal completion. A completed goal at the simulation
limit is accepted; completion beyond that limit fails. The runner also enforces
the wall-clock budget. A harness or infrastructure failure leaves an interrupted
partial result, rather than a finalized model failure. Timings interrupted by
cancellation are explicitly marked incomplete. Model time includes harness
overhead, consistent with the existing runner.

## Launch and recovery

For example, from the repository root:

```powershell
uv run python scripts/adaptive_contract_benchmark.py --mode technology --harness opencode --provider PROVIDER --model PROVIDER/MODEL --recipe-dump benchmark/data/factorio-2.0.77-contract-game-data.json --output benchmark/results/adaptive-contracts/technology-run/session.json
```

Use `--mode rocket_launch` for the launch objective. The default wall-clock limit
is 24 hours; `--wall-clock-failsafe-seconds` and `--max-session-ticks` control the
budgets. The game-data export must match the configured Factorio version and
contain every advertised technology. Progression modes do not require a reserved
throughput audit worker. They require envd's `progression_evaluations` capability.
Restart an older envd only after its active runs finish before selecting a new mode.

Fresh tasks use the normal freeplay starter state and unresearched technologies.
The declared seed follows the existing runtime contract: map generation is a
server-provisioning concern, so declaring a seed does not regenerate a warm
worker's map.

Results use `factorio-progression-session-v1`; they contain no TrueSkill rating or
synthetic contract epochs. The UI shows a single evaluation with a milestone
ledger. Partial artifacts are updated during play, including between long
persistent harness invocations.

OpenCode can resume an interrupted evaluation using `--resume-from` with its
`session.json.checkpoint.json` bundle. Mode, model, provider, harness, reasoning,
memory profile, seed, and task fingerprint must match. Recovery uses the newest
world checkpoint, preserves elapsed simulation time and verified launch progress,
and restores the same conversation. Finalized evaluations cannot resume.

## Validation

Focused unit tests cover completion predicates, budget/death precedence, runner
lifecycle, prompt selection, and distinct records. To validate the native boundary
on the dedicated reference server (Factorio 2.0.77, localhost RCON 27010):

```powershell
uv run python scripts/validate_progression_modes.py
```

This fixture resets only that reference server. It provisions research and a
ready rocket to test engine verification and checkpoint recovery. It is not a
claim that an agent completed a full freeplay run.
