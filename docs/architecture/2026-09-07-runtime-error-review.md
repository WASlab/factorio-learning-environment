# Runtime error review — 7 September 2026

Scope: run `2026-09-06-192338-b34a7f56`, execution receipts 1–280, plus
isolated reproductions of the affected tool boundaries. The reviewed run kept
its originally loaded code. Validation uses only the dedicated reference
cluster on RCON ports 27010/27011, Factorio 2.0.77.

## Findings and changes

| Evidence | Classification and resolution |
| --- | --- |
| 9: every recipe reported disabled, zero duration, no category | The recipe client discarded fields returned by Factorio. Preserve live enablement, duration, and category. The separate request for a coal crafting recipe was invalid. |
| 89, 91: delivery binding error reduced to `['plate']` | Shared serialization emitted unquoted strings. Both scoring scripts also overwrote that serializer. Quote strings once at the boundary, remove duplicate serializers, and return native tables from tools that previously serialized twice. Preserve complete error text. The underlying one-depot capacity rule still applies. |
| 146, 165, 172, 239: automation science remained locked after crafting labs | Unconnected character entities do not populate force handcraft production statistics. Track active native crafting queues and record completed recipe flows, including intermediates, so engine craft-item research triggers work. Do not credit requests or cancellations. Player-attached characters retain engine accounting without duplicate flows. |
| 150, 189: assembler and electric drill recipes locked | These technologies were downstream of the broken research progression. Recipe validation remains enforced. |
| 33–40, 60–64, 149–161: repeated blocked or missing walking paths | Requests used an oversized one-tile box and could choose an obstructed straight-line approach point. Use the character collision box with a small clearance margin and let native pathfinding choose an approach radius. Retain normal resolution first; retry the alternate resolution only on `not_found`. The isolated enclosed gate reproduces a valid passage rejected at normal resolution. This does not prove every historical failed route was physically open. |
| 182: iron target reported as stalled copper mining | Resource identification chose the first entity in an area query, while mining used nearest-center ordering. Use the same ordered selector for identification and mining. |
| 259: long wait timed out, then reported `int(dict)` | The requested 183,000 ticks need at least 305 seconds at 10x, exceeding the 120-second program limit. That request remains invalid for its budget. Transport failures now raise explicit errors; wait polls cooperatively for cancellation and validates tick responses. |
| Research wait condition | Zero remaining science ingredients does not establish completion of a craft-trigger technology. Check Factorio's researched flag directly. |
| Rocket tool review | Correct player-index/coordinate argument binding, require the specified player-owned silo, check engine acceptance, and remove request-time launch credit. Verification uses the engine's completed launch count. |
| OpenCode epoch telemetry | Measure the union of tool timestamp intervals, avoiding duplicate/overlap credit. Report remaining wall time as model/provider/harness time, not pure inference. Partial records also receive measured runner wall time. |

Other flagged receipts were model/API mistakes or valid state-dependent
rejections: 3 (string position), 5 (`len(ResourcePatch)`, caught and printed),
6 (forbidden `type`), 23/174 (placement under the character), 58 (an active
inserter refilled a chest before binding), 90 (empty chest extraction),
93/202/213 (insufficient coal), 132 (water destination), 137 (mixed unit grid),
138 (pipe inside boiler), 147 (no current research), 208/270 (duplicate
placement), and 254/257/258 (full boiler fuel inventory). A printed caught
exception can flag an entire receipt; the flag alone does not establish a
runtime defect. Locked downstream recipes and repeated route failures must
be interpreted with the root causes above rather than counted as independent
model failures.

## Validation

Run, in order:

```text
uv run python scripts/validate_freeplay_bootstrap.py
uv run python scripts/validate_native_runtime_regressions.py
uv run pytest -m no_factorio tests/actions/test_native_runtime_regressions.py tests/scripts/test_opencode_timing.py
```

The focused and boundary suites passed 118 distinct tests; two live-only tests
were deselected in the broader backend suite. Ruff checks passed.

The native checks cover freeplay starter equipment and crash site, wood/stone/
ore/coal mining, crafting, placement, five smelted plates, lab craft research
unlock, cancellation without production credit, program timeout and subsequent
RCON reuse, an enclosed narrow gate, rejected wrong-target launch, and one
completed engine launch. Results are saved under `.runtime/reference-factory/`.
Fixture inventory and rocket construction are test setup, not benchmark credit.
The test worlds are paused afterward.

The implementation follows the [semantic motor contract](tool-calling-compatibility.md#canonical-semantic-motor-runtime):
policy decisions remain with the agent; the controller executes native actions
and reports their actual completion. Lua changes require regenerating the
runtime mod and restarting its server before a new connection. The running
benchmark was not switched to these fixes mid-epoch.

## Docker interruption

Windows System events show a WSL package update starting at 10:35:28 EDT and
completing at 10:35:31 on 7 September, installing version 2.7.13. The WSL
service configuration changed during installation, its virtual network
subsequently disconnected, and a new WSL virtual network connected at 10:40:59.
Docker recorded the same 14:41:30 UTC finish time for both main Factorio
containers, both reference containers, and Postgres. Main Factorio containers
restarted at 14:41:32 UTC under `unless-stopped`; reference containers with
restart policy `no` remained exited with code 255. None reported `OOMKilled`.
The main Factorio log contains no preceding Lua exception or engine crash trace.

This supports a WSL/Docker interruption associated with the host update, rather
than an isolated Factorio crash. Docker's finish timestamp may reflect its
startup reconciliation, not the exact instant the VM stopped. The original
Docker backend logs for that interval had rotated by inspection, so the exact
shutdown mechanism is not established. No host update policies were changed.
The restarted main server loaded its configured scenario; automatic container
restart does not by itself restore the benchmark's in-memory world and lease.
A benchmark continuation must use a verified checkpoint restore.
