"""Decision policy as an ordered table of rules, not as code with forty guards in it.

A rule: `when(facts)` holds (facts also carry `_trail`, the rules fired so far, and `_action`) and the current action is in `from_actions` (None = any) -> action becomes `to`.
Rules run in order; every rule that fires is recorded in the decision's trail; the last one that changed the action
is the *decisive* rule. `measure()` fills each rule's cell with what happened to the cases it decided on a benchmark:
of the cases it finally accepted, how many were wrong (Wilson interval). `table()` prints the policy with those cells,
so "why does this combination accept" is a row, not a code search.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from . import stats

Pred = Callable[[Mapping], bool]


@dataclass
class Rule:
    id: str
    when: Pred
    to: str
    from_actions: tuple | None = None       # None = applies from any action
    when_text: str = ""                      # the condition in words, for the table
    note: str = ""                           # what it answers (the incident, the decision number)
    why: str = ""                            # fragment appended to the decision's `why`

    def applies(self, action: str | None, facts: Mapping) -> bool:
        if self.from_actions is not None and action not in self.from_actions:
            return False
        try:
            return bool(self.when(facts))
        except (KeyError, TypeError, ValueError):
            return False


@dataclass
class Outcome:
    action: str
    trail: list[str]                          # every rule that fired, in order
    decisive: str | None                      # the last rule that changed the action
    why: str


class Policy:
    def __init__(self, name: str, version: str, rules: Iterable[Rule], default: str = "review"):
        self.name, self.version = name, version
        self.rules = list(rules)
        self.default = default
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule ids must be unique")
        self.measured: dict[str, dict] = {}

    def decide(self, facts: Mapping) -> Outcome:
        action, trail, decisive, why = self.default, [], None, []
        view = dict(facts)                        # rules may look at what fired before them: facts["_trail"], ["_action"]
        for r in self.rules:
            view["_trail"], view["_action"] = list(trail), action
            if r.applies(action, view):
                trail.append(r.id)
                if r.to != action:
                    action, decisive = r.to, r.id
                if r.why:
                    why.append(r.why)
        return Outcome(action, trail, decisive, "; ".join(why))

    def decide_all(self, facts_by_case: Mapping[str, Mapping]) -> dict[str, Outcome]:
        return {c: self.decide(f) for c, f in facts_by_case.items()}

    def measure(self, outcomes: Mapping[str, Outcome], labels: Mapping[str, str], *, accept: str = "accept",
                wrong: str = "wrong", benchmark: str = "") -> dict[str, dict]:
        """Per rule: cases it was decisive for, how many of those ended accepted, how many of the accepted were wrong."""
        per: dict[str, dict] = {r.id: {"decisive_n": 0, "accepted": 0, "accepted_wrong": 0, "reviewed": 0, "reviewed_wrong": 0,
                                       "fired": 0} for r in self.rules}
        for c, o in outcomes.items():
            for rid in o.trail:
                per[rid]["fired"] += 1
            if o.decisive:
                d = per[o.decisive]
                d["decisive_n"] += 1
                if o.action == accept:
                    d["accepted"] += 1
                    d["accepted_wrong"] += int(labels.get(c) == wrong)
                else:
                    d["reviewed"] += 1
                    d["reviewed_wrong"] += int(labels.get(c) == wrong)
        for rid, d in per.items():
            d["wrong_rate"] = stats.rate(d["accepted_wrong"], d["accepted"]) if d["accepted"] else None
            d["caught_rate"] = stats.rate(d["reviewed_wrong"], d["reviewed"]) if d["reviewed"] else None
            d["benchmark"] = benchmark
        self.measured = per
        return per

    def table(self) -> str:
        head = "| # | rule | from → to | when | decisive on | accepted wrong | sent to review: wrong | note |\n|---|---|---|---|---|---|---|---|"
        rows = []
        for i, r in enumerate(self.rules, 1):
            m = self.measured.get(r.id, {})
            frm = "any" if r.from_actions is None else "/".join(r.from_actions)
            wr = m.get("wrong_rate")
            cr = m.get("caught_rate")
            fmt = lambda x: f"{x['k']}/{x['n']} ({x['ci95'][0]:.2f}–{x['ci95'][1]:.2f})" if x else ("–" if m else "")
            rows.append(f"| {i} | {r.id} | {frm} → {r.to} | {r.when_text} | {m.get('decisive_n', '')} | {fmt(wr)} | {fmt(cr)} | {r.note} |")
        return "\n".join([head] + rows)

    def to_json(self) -> str:
        return json.dumps({"name": self.name, "version": self.version, "default": self.default,
                           "rules": [{"id": r.id, "to": r.to, "from": r.from_actions, "when": r.when_text, "note": r.note}
                                     for r in self.rules], "measured": self.measured}, indent=1)
