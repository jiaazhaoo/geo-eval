"""The gate: a candidate's decisions against a baseline's, on a benchmark, under declared rules.

Rules (each is a Check; any failed check fails the gate):
  missed_errors   cases whose truth is the *wrong* label and whose action is the *accept* action: not more than the baseline's
  frozen_actions  every case keeps its baseline action (a change meant to move cases needs a new benchmark version),
                  unless `allow_moves` is True
  extra           anything the adapter adds (e.g. "every cached answer reproduced", "0 paid calls")
Reported, never gating: review load, accept rate, right cases sent to review, each with a Wilson interval, and the
paired McNemar comparison of candidate vs baseline on "the action was right for the truth".
Every run appends one JSON line to a log; `to_controller()` gives the counts an external controller reads.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from . import stats
from .benchmark import Benchmark
from .model import now_iso


@dataclass
class Check:
    name: str
    ok: bool
    detail: object = ""
    gating: bool = True


@dataclass
class GateResult:
    ok: bool
    checks: list[Check]
    metrics: dict
    benchmark: str
    split: str
    at: str = field(default_factory=now_iso)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_controller(self) -> dict:
        m = self.metrics
        other = [c.name for c in self.checks if c.gating and not c.ok and c.name != "missed_errors"]
        return {"benchmark": self.benchmark, "split": self.split,
                "missed_error": m["missed_errors"]["candidate"]["k"], "base_missed_error": m["missed_errors"]["baseline"]["k"],
                "review_load": m["review_load"]["candidate"]["k"], "base_review_load": m["review_load"]["baseline"]["k"],
                "golden_regressions": len(other)}

    def render(self) -> str:
        lines = []
        for c in self.checks:
            tag = ("ok  " if c.ok else "FAIL") if c.gating else "info"
            det = c.detail if c.detail not in ("", None, [], {}) else ""
            lines.append(f"   {tag} {c.name}  {det}"[:400])
        m = self.metrics
        lines.append(f"   missed errors {m['missed_errors']['candidate']['k']} (baseline {m['missed_errors']['baseline']['k']}) "
                     f"of {m['missed_errors']['candidate']['n']} wrong; review load {m['review_load']['candidate']['k']} "
                     f"(baseline {m['review_load']['baseline']['k']}) of {m['review_load']['candidate']['n']}; "
                     f"McNemar p={m['paired']['p_exact']:.3f} on {m['paired']['n_discordant']} discordant")
        lines.append(f"{'PASS' if self.ok else 'FAIL'}  {self.benchmark} [{self.split}]")
        return "\n".join(lines)


class Gate:
    def __init__(self, benchmark: Benchmark, *, accept: str = "accept", wrong: str = "wrong", right: str | None = "right",
                 split: str = "dev", allow_moves: bool = False, log: str | Path | None = None):
        self.bench = benchmark
        self.accept, self.wrong, self.right = accept, wrong, right
        self.split, self.allow_moves = split, allow_moves
        self.log = Path(log) if log else None

    # -- helpers ----------------------------------------------------------------------------------------------------
    def _labels(self) -> dict[str, str]:
        return self.bench.labels(None if self.split == "all" else self.split)

    def _missed(self, actions: Mapping[str, str], labels: Mapping[str, str]) -> list[str]:
        return sorted(c for c, l in labels.items() if l == self.wrong and actions.get(c) == self.accept)

    def _right_action(self, actions: Mapping[str, str], labels: Mapping[str, str]) -> dict[str, bool]:
        """Was the action right for the truth? wrong -> anything but accept; right -> accept."""
        out = {}
        for c, l in labels.items():
            if c not in actions:
                continue
            a = actions[c]
            out[c] = (a != self.accept) if l == self.wrong else (a == self.accept) if l == self.right else True
        return out

    # -- the run ---------------------------------------------------------------------------------------------------
    def run(self, candidate: Mapping[str, str], baseline: Mapping[str, str], *, extra: Iterable[Check] = (),
            meta: dict | None = None) -> GateResult:
        labels = self._labels()
        missing = sorted(c for c in labels if c not in candidate)
        checks = list(extra)
        checks.append(Check("coverage: every benchmark case has a candidate decision", not missing, missing[:20]))
        m_now, m_base = self._missed(candidate, labels), self._missed(baseline, labels)
        checks.append(Check("missed_errors", len(m_now) <= len(m_base), {"candidate": m_now, "baseline": m_base}))
        moved = sorted(c for c in labels if c in candidate and c in baseline and candidate[c] != baseline[c])
        checks.append(Check("frozen_actions", self.allow_moves or not moved, moved[:20], gating=not self.allow_moves))
        n_wrong = sum(1 for l in labels.values() if l == self.wrong)
        n_right = sum(1 for l in labels.values() if l == self.right)
        n = len(labels)
        def load(actions):
            return sum(1 for c in labels if c in actions and actions[c] != self.accept)
        def right_to_review(actions):
            return sum(1 for c, l in labels.items() if l == self.right and c in actions and actions[c] != self.accept)
        metrics = {
            "missed_errors": {"candidate": stats.rate(len(m_now), n_wrong), "baseline": stats.rate(len(m_base), n_wrong)},
            "review_load": {"candidate": stats.rate(load(candidate), n), "baseline": stats.rate(load(baseline), n)},
            "right_to_review": {"candidate": stats.rate(right_to_review(candidate), n_right),
                                "baseline": stats.rate(right_to_review(baseline), n_right)},
            "accept_rate": {"candidate": stats.rate(n - load(candidate), n), "baseline": stats.rate(n - load(baseline), n)},
            "paired": stats.paired({c: True for c in labels}, self._right_action(candidate, labels), self._right_action(baseline, labels)),
            "moved": len(moved),
        }
        ok = all(c.ok for c in checks if c.gating)
        res = GateResult(ok, checks, metrics, f"{self.bench.name}-{self.bench.version}", self.split, meta=meta or {})
        if self.log:
            with open(self.log, "a") as f:
                f.write(json.dumps(res.to_dict(), default=str, sort_keys=True) + "\n")
        return res
