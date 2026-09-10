# Muse-Spark delivery and resume review

Run: `2026-09-05-054852-afb3c91c`. Reviewed 2026-09-05.

## Finding

The zero-delivery outcomes are not clean evidence of an agent autonomy failure.
There is a reproducible accounting defect after resume, alongside genuine
manual maintenance in the trajectory and transport failures in the runner.

The live observation showed a bound gear depot with 200 accepted units,
306 automated gear arrivals, and an active order claiming zero fulfillment.
A subsequent saved observation recorded 356 gear arrivals and still zero
fulfillment. Its recent delivery buckets ended around tick 634,619, before the
order's issued-at tick 639,470. These are incompatible clock domains, not evidence
that nothing crossed the delivery boundary. The local evidence snapshot is
`.runtime/delivery-clock-evidence.json` (ignored operational artifact).

`import_resume_state` restores the Python worker's original `epoch_game_tick`.
The Lua customer `adopt` action resets its own `epoch_tick` to the current game
tick. Delivery buckets use the latter; `ActiveOrder.attribute` compares them
against order boundaries using the former. Valid arrivals can therefore appear
to precede the order and are rejected. Recent-rate candidate detection is also
affected by misdated delivery samples.

Execution 68 is not decisive evidence of a failed autonomous audit: its receipt
has an empty `customer_depot_ids` list, and it records a failed attempt to insert
wood into an inserter already containing coal. It shows physical geometry and
an idle inserter, but not a passing bound delivery path or the cause of an audit
failure. The run does contain repeated manual refueling; that remains a useful
behavioral observation, not an explanation for every zero in its accounting.

## Implemented refinements

- Translate Lua delivery timestamps to the persistent worker clock at ingestion,
  using `lua_epoch_tick - worker_epoch_game_tick`. Apply the same translation to
  automated and manual samples. Keep raw quantities and original evidence intact.
- Retry finalization transport failures up to three times only with a replayable
  request ID and an unchanged payload. Do not retry semantic failures or
  non-idempotent abandonment. Exhaustion is identified as an uncertain
  infrastructure interruption.
- Recheck the finalization cache after taking the worker lock, covering a retry
  arriving before the original request finishes.
- Return delivery feedback after waits as well as insertions. Separate physical
  depot arrivals since the order boundary from interval contract credit and
  qualification. Explain missing bindings and distinguish an empty interval
  from a failed audit.
- Clarify the shared objective and per-order prompt: hand work is available for
  bootstrap; recurring fuel/input replacement is not sustained autonomy; actions
  and waits consume the deadline; production, delivery, and certification are
  separate measurements. Preserve freedom over layout and future investment.

These edits do not change throughput thresholds or reveal hidden audit outcomes.
Existing run artifacts and ratings have not been rewritten. Running processes
have not been hot-patched or restarted as part of this review.

## Validation

78 focused tests passed across delivery-clock regression, finalize transport,
adaptive lifecycle, throughput audit, and runner behavior; two live tests were
deselected. Regression coverage includes valid arrivals after clock rebasing,
manual traffic exclusion, no double credit, non-aligned epoch offsets, a lost
response after committed finalization, concurrent retries, retry exhaustion,
and non-retryable semantic failures.

The live observation establishes the accounting discrepancy. A new full native
save/restore evaluation with the updated service has not yet been run.

## Before interpreting the next run

1. Use a fresh, versioned run with the corrected service and prompt. Preserve
   this trajectory as infrastructure-affected evidence; do not pool its zero
   results as clean model losses or retroactively infer an autonomous pass.
2. Test a known working factory across save/restore and compare depot arrivals,
   contract credit, timestamps, and qualification. Also retain a deliberately
   hand-maintained factory as a negative autonomy control.
3. Add bounded, observable feeder diagnostics if feedback still proves
   insufficient: the bound chest, feeding inserter status and pickup location,
   and immediate source status. Report `no_fuel` only when observed. Do not
   invent a starvation diagnosis from an empty receipt or expose failed hidden
   audits. This richer machine-level diagnostic is not implemented here.
4. Compare a neutral operational prompt with an explicitly coached diagnostic
   prompt as separate participant identities. This can distinguish missing
   communication from planning limitations without weakening E2E qualification.
5. Review resume adoption separately: it currently reuses audit restoration,
   including clearing depot contents. Live resume and isolated audit restoration
   should have distinct inventory/provenance contracts before claiming exact
   save/restore equivalence.

Keep the unattended requirement. First establish that a known autonomous factory
passes and that resume preserves its measurements; then interpret a model's
refueling loops as evidence about its engineering behavior.

## Corrected relaunch

The [native reference factory](reference-factory.md) subsequently passed physical
delivery, canonical audits, and checkpoint continuation, with broken-delivery
and depleted-fuel controls correctly rejected. It also exposed the live recipe
`count` versus `amount` parsing defect, now corrected.

Fresh run `2026-09-05-183202-d0244b1b` starts Muse-Spark on OpenCode with stateful
memory, 10x execution speed, observer enabled, and a 24-hour wall limit. The
service and runner were restarted. The prior run retains its artifacts and an
operator checkpoint. The fresh run records source hashes in
`validation-provenance.json`.

The shared prompt now defines E2E explicitly. Subsequent contract prompts include
the previous public status and credited quantity, with general troubleshooting
guidance for unsuccessful contracts. This summary does not expose hidden audit
details or assert an unobserved machine-level cause. 43 focused runner, transport,
and delivery-clock tests passed before launch.
