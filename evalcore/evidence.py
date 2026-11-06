"""Evidence: typed facts about a case, each with a source kind and an independence *family*.

Two facts support each other only when their families differ: two readings of the same drawing by two models are one
family ("drawing-reader"); a drawing reading and an address-register lookup are two. The policy asks `facts()` for
plain values; the independence bookkeeping is for the policy table and for anyone asking "what backs this accept".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

SOURCE_KINDS = ("deterministic", "model", "person", "record")


@dataclass(frozen=True)
class Evidence:
    name: str
    value: Any
    source: str = "deterministic"      # one of SOURCE_KINDS
    family: str = ""                   # independence class; "" = stands alone
    cost: float = 0.0                  # what producing it cost (money, or seconds: the adapter decides the unit)
    note: str = ""

    def __post_init__(self):
        if self.source not in SOURCE_KINDS:
            raise ValueError(f"source {self.source!r} not in {SOURCE_KINDS}")


class EvidenceSet:
    def __init__(self, items: Iterable[Evidence] = ()):
        self._items: dict[str, Evidence] = {}
        for e in items:
            self.add(e)

    def add(self, e: Evidence) -> "EvidenceSet":
        self._items[e.name] = e
        return self

    def __getitem__(self, name: str) -> Any:
        return self._items[name].value

    def get(self, name: str, default: Any = None) -> Any:
        e = self._items.get(name)
        return default if e is None else e.value

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def facts(self) -> dict[str, Any]:
        return {k: e.value for k, e in self._items.items()}

    def families(self, names: Iterable[str]) -> set[str]:
        return {self._items[n].family or n for n in names if n in self._items}

    def independent(self, names: Iterable[str]) -> int:
        """How many independent families the named facts span: the number that counts as corroboration."""
        return len(self.families(names))

    def cost(self) -> float:
        return sum(e.cost for e in self._items.values())

    def items(self) -> Mapping[str, Evidence]:
        return dict(self._items)
