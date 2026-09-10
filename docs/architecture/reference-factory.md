# Native reference iron factory

`tests/fixtures/reference_iron_factory.lua` defines a deterministic physical
factory for Factorio 2.0.77. It is a harness acceptance fixture, built with
administrative placement on controlled terrain, not an agent trajectory or a
claim that a model can bootstrap the factory.

The layout includes water, steam power, electric coal and iron mining, belts,
automatic boiler and furnace fueling, smelting, and inserter delivery into a
bound customer chest. Its only injected fuel is five coal at bootstrap. The
coal drill then supplies both recurring fuel consumers. No electric energy
interface, infinite fluid source, or injected production is used.

## Run

Run `uv run python scripts/validate_reference_factory.py` from the repository.
Docker must be running. The script creates the dedicated Compose project
`fle-reference-factory`, with RCON ports 27010/27011 and UDP ports 34207/34208
bound to localhost. It resets these two dedicated worlds and leaves them
paused afterward. It does not use the evaluation servers on 27000/27001.

The opt-in pytest entry point is
`tests/envd/test_reference_factory_live.py`; set `FLE_RUN_REFERENCE_FACTORY=1`
to enable it. Ordinary test runs skip this Docker workload.

Outputs are under `.runtime/reference-factory/`: `validation.json` records
the layout hash and native results; `reference-iron-v1.json` is a successful
world snapshot; `checkpoints/` contains lifecycle state. The controlled terrain
must be seeded in the audit world because entity snapshots are not full map
saves. The Lua source is the portable fixture definition.

## Acceptance boundaries

- Ten simulated minutes of untouched production must deliver at least 120 plates.
- The canonical throughput audit must pass at 10 plates/minute, with depot
  service, subwindow floors, and upstream supply checking enabled.
- A lifecycle checkpoint must restore the active order and credit at least
  25 additional plates in two simulated minutes; the restored factory must
  also pass the throughput audit.
- Removing the delivery inserter must fail the audit with zero depot throughput.
- Removing coal mining and allowing ten simulated minutes for bootstrap fuel
  to expire must fail with zero plate production.

This is the baseline for delivery, auditing, and persistence integration tests.
It complements focused unit tests; one iron line cannot cover multi-product
orders, fluids, research, trains, or late-game logistics. Extend the fixture
family as those boundaries are validated instead of replacing unrelated tests
with variations of one successful factory.

The audit observes a finite interval. Recipe closure checks iron-ore supply;
coal consumed as fuel is not a recipe ingredient in that graph. Passing the
audit alone therefore does not establish indefinite fuel autonomy. The explicit
coal loop, ten-minute unattended run, and depleted-fuel control provide separate
evidence for this fixture. A future buffer-heavy adversarial fixture should test
how long a disconnected fuel supply can masquerade as autonomous production.

Candidate snapshots here are submitted directly to the production audit API.
Automatic candidate detection and agent tool use remain separate test boundaries.

## Defect discovered by native validation

The namespace recipe API returns typed ingredients/products with `count`.
The audit recipe source expected raw Lua `amount` fields, causing a `KeyError`
after the physical holdout. The source now accepts both schemas. Regression
tests exercise the actual `Recipe` model and raw dictionaries.

## Validated baseline — 2026-09-05

Native validation completed successfully on the dedicated 2.0.77 pair:

| Check | Observed result |
| --- | --- |
| Ten minutes unattended | 177 credited iron plates |
| Initial audit | Pass; 18.50 depot plates/minute |
| Two minutes after lifecycle restore | 37 additional credited plates |
| Restored-world audit | Pass; 18.57 depot plates/minute |
| Delivery inserter removed | Fail; 0 depot plates/minute while smelting continued |
| Coal mining removed, bootstrap fuel depleted | Fail; 0 production and delivery |

31 focused unit tests passed across recipe features, throughput auditing, and
resume clocks. The opt-in test skips in ordinary runs. Ruff 0.11.13 checks passed.

A native save of the healthy paused source was also exported locally to
`.runtime/reference-factory/reference-iron-v1.zip`. Unlike the entity snapshot,
this includes terrain and can be inspected as a Factorio save. This export is
a baseline artifact; the validation command regenerates the JSON snapshot and
report, not the native ZIP.
