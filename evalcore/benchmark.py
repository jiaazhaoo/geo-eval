"""A benchmark is a frozen list: case id, artefact digest, truth label, strata, split. Everything else is derived.

Build one from a TruthRegistry with stratified sampling and a seed; freeze it to a directory (manifest + cases.csv,
read-only); load it later; ask whether it is stale (a case's artefact digest no longer matches what the truth was
about); summarise it by stratum. The dev split is what a daily gate replays; the holdout is touched only at release.
"""
from __future__ import annotations

import csv
import json
import os
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from .model import Case, digest_of, now_iso
from .truth import TruthRegistry


@dataclass(frozen=True)
class BenchCase:
    case: str
    artefact: str
    label: str
    strata: Mapping[str, str]
    split: str = "dev"


@dataclass
class Benchmark:
    name: str
    version: str
    cases: list[BenchCase]
    seed: int = 0
    created: str = field(default_factory=now_iso)
    note: str = ""

    # -- construction ---------------------------------------------------------------------------------------------
    @classmethod
    def build(cls, name: str, version: str, registry: TruthRegistry, cases: Iterable[Case], *, strata_keys: list[str],
              per_stratum: int | None = None, holdout: float = 0.0, seed: int = 0, note: str = "") -> "Benchmark":
        """Stratified by the labelled value and `strata_keys`; `per_stratum` caps each stratum (None = take all);
        `holdout` is the share of each stratum set aside (never replayed by a daily gate)."""
        truth = registry.current_by_case()
        rng = random.Random(seed)
        groups: dict[tuple, list[tuple[Case, str]]] = defaultdict(list)
        for c in cases:
            t = truth.get(c.id)
            if t is None or t.artefact != c.artefact:
                continue                                   # no truth, or truth about another version of the artefact
            key = (t.label,) + tuple(c.strata.get(k, "") for k in strata_keys)
            groups[key].append((c, t.label))
        out: list[BenchCase] = []
        for key in sorted(groups):
            items = sorted(groups[key], key=lambda x: x[0].id)
            rng.shuffle(items)
            if per_stratum is not None:
                items = items[:per_stratum]
            n_hold = int(round(len(items) * holdout))
            for i, (c, label) in enumerate(items):
                out.append(BenchCase(c.id, c.artefact, label, dict(c.strata), "holdout" if i < n_hold else "dev"))
        out.sort(key=lambda b: b.case)
        return cls(name, version, out, seed=seed, note=note)

    # -- persistence ----------------------------------------------------------------------------------------------
    def digest(self) -> str:
        return digest_of([asdict(b) for b in self.cases])

    def freeze(self, dir: str | Path) -> Path:
        """Write manifest.json + cases.csv and make them read-only. Refuses to overwrite a frozen benchmark."""
        d = Path(dir)
        if (d / "manifest.json").exists():
            raise FileExistsError(f"{d} is already frozen; a changed benchmark is a new version")
        d.mkdir(parents=True, exist_ok=True)
        keys = sorted({k for b in self.cases for k in b.strata})
        with open(d / "cases.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["case", "artefact", "label", "split"] + keys)
            for b in self.cases:
                w.writerow([b.case, b.artefact, b.label, b.split] + [b.strata.get(k, "") for k in keys])
        man = {"name": self.name, "version": self.version, "seed": self.seed, "created": self.created, "note": self.note,
               "cases": len(self.cases), "digest": self.digest(), "strata_keys": keys, "summary": self.summary()}
        (d / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True))
        for p in (d / "cases.csv", d / "manifest.json"):
            os.chmod(p, 0o444)
        return d

    @classmethod
    def load(cls, dir: str | Path) -> "Benchmark":
        d = Path(dir)
        man = json.loads((d / "manifest.json").read_text())
        keys = man.get("strata_keys", [])
        cases = []
        with open(d / "cases.csv") as f:
            for r in csv.DictReader(f):
                cases.append(BenchCase(r["case"], r["artefact"], r["label"], {k: r.get(k, "") for k in keys}, r.get("split", "dev")))
        b = cls(man["name"], man["version"], cases, seed=man.get("seed", 0), created=man.get("created", ""), note=man.get("note", ""))
        if b.digest() != man["digest"]:
            raise ValueError(f"{d}: cases.csv does not match manifest digest; the benchmark was edited after freezing")
        return b

    # -- queries --------------------------------------------------------------------------------------------------
    def split(self, name: str) -> list[BenchCase]:
        return [b for b in self.cases if b.split == name]

    def labels(self, split: str | None = None) -> dict[str, str]:
        return {b.case: b.label for b in self.cases if split is None or b.split == split}

    def stale(self, current_digests: Mapping[str, str]) -> list[dict]:
        """Cases whose artefact digest today differs from the one the truth was recorded for."""
        return [{"case": b.case, "frozen": b.artefact, "now": current_digests[b.case]}
                for b in self.cases if b.case in current_digests and current_digests[b.case] != b.artefact]

    def summary(self) -> dict:
        by_label = Counter(b.label for b in self.cases)
        by_split = Counter(b.split for b in self.cases)
        by_stratum: dict[str, Counter] = defaultdict(Counter)
        for b in self.cases:
            for k, v in b.strata.items():
                by_stratum[k][f"{v}|{b.label}"] += 1
        return {"labels": dict(by_label), "splits": dict(by_split), "strata": {k: dict(v) for k, v in by_stratum.items()}}
