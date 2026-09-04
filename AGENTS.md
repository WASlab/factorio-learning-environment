# FactorioAgentBench

This repository develops a persistent, adaptive Factorio agent benchmark derived from FLE. Preserve upstream attribution and licensing. The Python namespace is `fle`; the distribution is currently named `factorio-learning-environment`. Do not publish this fork over the upstream package.

## Orientation

Read the relevant current code and architecture document before changing a subsystem:

- `fle/envd/`: environment leases, benchmark contracts, lifecycle, scoring, and verification.
- `fle/env/`: Factorio runtime integration, Python tools, and Lua implementations.
- `fle/cluster/`: Factorio server orchestration.
- `fle/integrations/`, `integrations/`, and `scripts/`: harness integrations and workflows.
- `docs/architecture/`: benchmark design and tool-calling contracts.
- `tests/`: runtime, action, integration, and benchmark verification.

## Implementation and validation

Use the repository's `pyproject.toml` and `uv.lock` for Python dependencies. Use `uv run` for project commands. Follow the Ruff configuration in `.pre-commit-config.yaml` for changed Python files.

Run focused tests for the changed behavior, then broader checks when the affected boundary warrants them. The `no_factorio` pytest marker identifies tests intended to run without a live server: `uv run pytest -m no_factorio <relevant-test-path>`.

For Python/Lua tool changes, check both sides of the boundary and the agent-facing reference. Live Factorio behavior needs live validation when it cannot be established by unit tests; report unavailable runtime coverage explicitly.

Keep benchmark scoring and hidden verifier state separate from agent-visible observations. Changes to scoring, determinism, saved state, or replay behavior must be checked against the relevant architecture contract and tests.

Check the installed Factorio version and configured endpoints before live validation. Use isolated test instances or leases so tests do not reset an active run.

Keep architecture and usage documentation aligned with changed behavior. Prefer links to the authoritative files over copying changing implementation details into these instructions.
