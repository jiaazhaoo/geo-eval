#!/usr/bin/env python3
"""End to end on synthetic data: truths -> benchmark (dev/holdout) -> gate candidate vs baseline. Runs in a second, no data."""
import random, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalcore import Benchmark, Case, Gate, Truth, TruthRegistry, digest_of

rng = random.Random(0)
tmp = Path(tempfile.mkdtemp())
reg = TruthRegistry(tmp / "truth.jsonl")
cases = []
for i in range(300):
    art = digest_of({"output": i})                      # the artefact's content digest: truth binds to it
    town = rng.choice("ABC")
    label = "wrong" if rng.random() < 0.3 else "right"
    reg.append(Truth(art, label, "client:audit-2026-10.xlsx", at=f"2026-10-{1 + i % 28:02d}T00:00:00Z", case=f"X{i:03d}"))
    cases.append(Case(f"X{i:03d}", art, {"town": town}))
bench = Benchmark.build("demo", "v1", reg, cases, strata_keys=["town"], holdout=0.3, seed=1)
bench.freeze(tmp / "bench-demo-v1")
print("benchmark:", bench.summary())

labels = bench.labels("dev")
def system(miss_rate, review_rate):
    """A pretend decision system: misses some wrong cases, sends some right cases to review."""
    return {c: ("accept" if (l == "wrong" and rng.random() < miss_rate) or (l == "right" and rng.random() > review_rate) else "review")
            for c, l in labels.items()}
baseline = system(0.10, 0.35)
candidate = dict(baseline)
for c in list(candidate)[:40]:                         # a change that moves 40 cases, none for the worse
    if labels[c] == "right":
        candidate[c] = "accept"
res = Gate(Benchmark.load(tmp / "bench-demo-v1"), allow_moves=True, log=tmp / "gate.jsonl").run(candidate, baseline)
print(res.render())
print("controller view:", res.to_controller())
