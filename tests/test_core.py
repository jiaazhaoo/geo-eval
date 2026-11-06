import json, os, tempfile
from pathlib import Path

import pytest

from evalcore import Artefact, Benchmark, Case, Gate, Truth, TruthRegistry, digest_of, stats


def _reg(tmp):
    reg = TruthRegistry(tmp / "truth.jsonl")
    for i in range(20):
        art = digest_of({"poly": i})
        label = "wrong" if i % 4 == 0 else "right"
        reg.append(Truth(art, label, "client:feedback.xlsx", at=f"2026-10-0{1 + i % 9}T00:00:00Z", case=f"C{i:02d}"))
    return reg


def _cases():
    return [Case(f"C{i:02d}", digest_of({"poly": i}), {"town": "A" if i < 10 else "B"}) for i in range(20)]


def test_truth_rank_and_conflict(tmp_path):
    reg = _reg(tmp_path)
    art = digest_of({"poly": 1})
    reg.append(Truth(art, "wrong", "batch:run-1", at="2026-11-01T00:00:00Z", case="C01"))
    assert reg.current(art).label == "right"          # client (40) beats batch (20) although older
    reg.append(Truth(art, "wrong", "person:jia", at="2026-11-02T00:00:00Z", case="C01"))
    assert reg.current(art).label == "right"          # client still outranks person
    assert any(c["case"] == "C01" for c in reg.conflicts())
    with pytest.raises(ValueError):
        reg.append(Truth(art, "x", "rumour:someone", case="C01"))
    reg2 = TruthRegistry(tmp_path / "truth.jsonl")    # reloads from disk, append-only file
    assert len(reg2) == len(reg)


def test_truth_bound_to_digest(tmp_path):
    reg = _reg(tmp_path)
    cases = _cases()
    cases[3] = Case("C03", digest_of({"poly": "redelivered"}), {"town": "A"})
    b = Benchmark.build("t", "v1", reg, cases, strata_keys=["town"])
    assert "C03" not in b.labels()                     # truth was about another digest: excluded, not guessed


def test_benchmark_build_freeze_load_stale(tmp_path):
    reg = _reg(tmp_path)
    b = Benchmark.build("t", "v1", reg, _cases(), strata_keys=["town"], holdout=0.5, seed=1)
    assert len(b.cases) == 20 and b.summary()["labels"] == {"wrong": 5, "right": 15}
    assert len(b.split("holdout")) in (9, 10, 11)
    d = b.freeze(tmp_path / "bench")
    with pytest.raises(FileExistsError):
        b.freeze(d)
    b2 = Benchmark.load(d)
    assert b2.digest() == b.digest() and b2.labels() == b.labels()
    stale = b2.stale({"C00": "sha256:other", "C01": b2.cases[1].artefact})
    assert [s["case"] for s in stale] == ["C00"]
    os.chmod(d / "cases.csv", 0o644)
    (d / "cases.csv").write_text((d / "cases.csv").read_text().replace("C00", "C99"))
    with pytest.raises(ValueError):
        Benchmark.load(d)


def test_gate_rules(tmp_path):
    reg = _reg(tmp_path)
    b = Benchmark.build("t", "v1", reg, _cases(), strata_keys=["town"])
    labels = b.labels()
    base = {c: ("review" if l == "wrong" else "accept") for c, l in labels.items()}
    base["C04"] = "accept"                              # baseline already misses one
    g = Gate(b, log=tmp_path / "gate.jsonl")
    r = g.run(dict(base), base)
    assert r.ok and r.metrics["missed_errors"]["candidate"]["k"] == 1
    worse = dict(base, C08="accept")
    r = g.run(worse, base)
    assert not r.ok and [c.name for c in r.checks if not c.ok] == ["missed_errors", "frozen_actions"]
    better = dict(base, C04="review")
    r = Gate(b, allow_moves=True).run(better, base)
    assert r.ok and r.metrics["missed_errors"]["candidate"]["k"] == 0 and r.metrics["moved"] == 1
    assert r.metrics["paired"]["only_a_right"] == 1 and r.metrics["paired"]["only_b_right"] == 0
    r = g.run({k: v for k, v in base.items() if k != "C10"}, base)
    assert not r.ok and r.checks[0].name.startswith("coverage")
    assert len((tmp_path / "gate.jsonl").read_text().splitlines()) == 3
    ctl = r.to_controller()
    assert set(ctl) >= {"missed_error", "base_missed_error", "review_load", "base_review_load", "golden_regressions"}


def test_stats():
    assert abs(stats.wilson_upper(0, 30) - 0.1135) < 1e-3
    assert stats.wilson_upper(1, 300) < 0.02
    assert stats.mcnemar(0, 0)["p_exact"] == 1.0
    assert abs(stats.mcnemar(1, 9)["p_exact"] - 0.0215) < 1e-3
    e = stats.ece([0.9, 0.9, 0.1, 0.1], [True, True, False, True], bins=10)
    assert e["n"] == 4 and 0 < e["ece"] < 1
