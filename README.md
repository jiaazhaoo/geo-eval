# geo-eval

**Deciding when an AI's output can be acted on, and proving a change did not make that worse.**

Status: v0.2, the core extracted from a production QA flow (2026-11). In: truth registry, benchmark, gate, evidence
model, decision policy as a measured table, calibration and selective prediction. Next: drift monitoring.

## The problem

A system produces thousands of outputs a week: polygons, dates, scripts. At run time nobody knows which are wrong.
Truth arrives later, from a client's audit or a reviewer, for a sample. The system has to decide per case whether to
act on the output or send it to a person, and every change to the system has to be shown not to let more errors
through. Missing an error costs far more than one extra look, so accuracy is the wrong number: the number is
*wrong outputs acted on without a person*.

## What it does

| part | what it guarantees |
|---|---|
| `TruthRegistry` | a label is bound to the content digest of the artefact it was given for; sources are ranked (client > person > check > batch > import), the winner is derived, losers are kept as conflicts; append-only |
| `Benchmark` | a frozen, versioned, stratified case list with a dev / holdout split and a seed; refuses to be overwritten; detects when an artefact has changed under its truth |
| `Gate` | candidate vs baseline decisions on a benchmark: missed errors may not rise, actions stay frozen unless the change is meant to move them; review load, right-cases-sent-to-review and accept rate with Wilson intervals; paired McNemar; one JSON line per run |
| `Evidence` / `EvidenceSet` | a fact with a source kind (deterministic / model / person / record) and an independence *family*: two readings by two models of the same drawing are one family, a drawing reading and a register lookup are two; corroboration counts families, not facts |
| `Policy` / `Rule` | the decision rules as an ordered table (`when` -> action, from which actions), with a trail of what fired; `measure()` fills every rule's cell from a benchmark: of the cases it finally accepted, how many were wrong; of the cases it sent to a person, how many were wrong; `table()` prints it |
| `Calibrator` / `selective` | isotonic (pool-adjacent-violators) score -> probability map fitted on dev; the coverage-vs-error curve behind "the top band is 88% right on 25% of cases" |
| `stats` | Wilson, exact McNemar, ECE with a reliability table; no scipy |
| `adapters/` | the project vocabulary: what an artefact is, where truth comes from, what the actions are called |

Nothing in `evalcore/` knows what a polygon, a council or a judge is.

## What we measured

The core was accepted when it reproduced the production gate exactly: on a frozen benchmark of 100 delivered
polygons graded by the client (60 right / 40 wrong, four areas), the generic gate returned the same four missed
errors, the same 48 / 52 accept / review split and the same 16 right cases sent to a person as the project's own
gate script. Numbers from the production flow this was extracted from (2026-10): missed errors on that benchmark
3–4 of 40 across releases; a change that required independent evidence before flagging raised flag precision from
42% to 73% on 300 cases at unchanged misses.

The second acceptance: the production flow's lane logic (forty guards spread over a 520-line script, grown from
eleven dated incidents) rewritten as 13 `Rule`s reproduced every one of the 100 frozen lanes. Measured on the same
benchmark the table then showed where the misses live: 3 of 38 accepts decided by "both readers correct", 1 of 3
decided by the appeal round, 0 of 6 by the firm-match rule; of the guards that send an accepted case back to a
person, the recheck guard held 3 cases (1 wrong), the unnamed-address guard and the case-type guard 1 each (both wrong).

## Run it

```bash
python3 examples/synthetic_gate.py        # truths -> benchmark -> gate, synthetic, one second
python3 -m pytest -q tests
```

An adapter is 60 lines for the gate (read your truth source into `Truth` records, your run's decisions into
`{case: action}`, name the action that means "acted on without a person") and one `Rule` per guard for the policy.
`adapters/polygon_qa.py` is the full worked example: facts from a run's files, 13 rules, measured on the benchmark.

## Where it sits

- the systems it gates: a scan-to-polygon pipeline and an evidence-checked document reader (separate repositories)
- the control layer that calls the gate at merge time: [ReinsLite](https://github.com/jiaazhaoo/ReinsLite)

## Origin

Extracted from a private production repository (400+ commits, 2026-09 to 2026-11) that checks AI-produced land
parcels against scanned planning drawings for a client. Data, client names and the judges' answers
stay private; the methods and the numbers above are public. The author defined the problem, the rules and the
acceptance checks; implementation was produced with coding agents under those checks.
