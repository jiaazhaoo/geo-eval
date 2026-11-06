"""Truth registry: append-only JSONL of Truth records; the current label per artefact is derived, never stored.

Resolution order (the same idea as a ledger of facts with ranked sources): highest source rank wins, then the newest.
Losing labels are kept and listed by `conflicts()` for a person. A truth is bound to an artefact *digest*: if the
artefact changes, the old truth no longer applies, and `Benchmark.stale()` will say so.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

from .model import Truth

DEFAULT_RANKS = {"client": 40, "person": 30, "verified": 30, "check": 20, "batch": 20, "delivery": 15, "import": 10}


class TruthRegistry:
    def __init__(self, path: str | Path | None = None, ranks: dict[str, int] | None = None):
        self.path = Path(path) if path else None
        self.ranks = dict(ranks or DEFAULT_RANKS)
        self._items: list[Truth] = []
        if self.path and self.path.exists():
            with open(self.path) as f:
                self._items = [Truth(**json.loads(l)) for l in f if l.strip()]

    # -- writing -------------------------------------------------------------------------------------------------
    def rank(self, source: str) -> int:
        kind = source.split(":", 1)[0]
        if kind not in self.ranks:
            raise ValueError(f"unknown source kind {kind!r}; known: {sorted(self.ranks)}")
        return self.ranks[kind]

    def append(self, t: Truth) -> Truth:
        self.rank(t.source)                      # refuse unknown sources at write time
        if not t.artefact or not t.label:
            raise ValueError("a truth needs an artefact digest and a label")
        self._items.append(t)
        if self.path:
            with open(self.path, "a") as f:
                f.write(json.dumps(t.to_dict(), sort_keys=True) + "\n")
        return t

    def extend(self, items: Iterable[Truth]) -> int:
        return sum(1 for t in items if self.append(t))

    # -- reading -------------------------------------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Truth]:
        return iter(self._items)

    def all_for(self, artefact: str) -> list[Truth]:
        return [t for t in self._items if t.artefact == artefact]

    def current(self, artefact: str) -> Truth | None:
        """The winning label for one artefact digest: highest rank, then newest."""
        items = self.all_for(artefact)
        if not items:
            return None
        return max(items, key=lambda t: (self.rank(t.source), t.at))

    def current_by_case(self) -> dict[str, Truth]:
        """case id -> winning truth of the case's newest artefact digest (older digests are superseded artefacts)."""
        by_case: dict[str, list[Truth]] = defaultdict(list)
        for t in self._items:
            if t.case:
                by_case[t.case].append(t)
        out = {}
        for c, items in by_case.items():
            newest_digest = max(items, key=lambda t: t.at).artefact
            out[c] = self.current(newest_digest)
        return out

    def conflicts(self) -> list[dict]:
        """Artefacts with more than one distinct label: the winner and the losers, for a person to look at."""
        out = []
        seen = {t.artefact for t in self._items}
        for a in sorted(seen):
            items = self.all_for(a)
            labels = {t.label for t in items}
            if len(labels) > 1:
                w = self.current(a)
                out.append({"artefact": a, "case": w.case, "winner": w.to_dict(),
                            "losers": [t.to_dict() for t in items if t is not w and t.label != w.label]})
        return out
