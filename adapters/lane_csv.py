"""Adapter for a lane-style QA flow: a labels CSV (truth) + per-area decision CSVs (lanes) -> evalcore objects.

Vocabulary mapped here and nowhere in evalcore (column names are parameters; the defaults are generic):
  truth labels   `truth` column: right / wrong (the auditor's verdict on the exact output it graded)
  actions        `lane` column: the value in ACCEPT_LANES -> accept, anything else -> review
  strata         `stratum` column "<area>|<label>|<method>|<kind>" -> keys area / method / kind
  artefact       the output itself is not in these files; its digest is taken from (case, delivery file, source id),
                 which is enough to tell a re-delivered output from the graded one
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from evalcore import Case, Truth, digest_of

ACCEPT_LANES = {"auto pass"}
STRATUM_KEYS = ("area", "label", "method", "kind")
DEFAULT_COLS = {"case": "case", "truth": "truth", "stratum": "stratum", "area": "area", "delivery": "delivery_file",
                "source_id": "orig_oachargeid", "grade_file": "grade_file", "at": "", "note": "error", "ref": "ref"}


def read_labels(labels_csv: str | Path, source_kind: str = "client", cols: dict | None = None) -> tuple[list[Case], list[Truth]]:
    k = dict(DEFAULT_COLS, **(cols or {}))
    cases, truths = [], []
    with open(labels_csv) as f:
        for r in csv.DictReader(f):
            parts = (r.get(k["stratum"]) or "").split("|")
            strata = {s: v for s, v in zip(STRATUM_KEYS, parts) if s != "label"}
            if not strata.get("area"):
                strata["area"] = r.get(k["area"], "")
            art = digest_of({"case": r[k["case"]], "delivery": r.get(k["delivery"], ""), "source_id": r.get(k["source_id"], "")})
            cases.append(Case(r[k["case"]], art, strata, {"ref": r.get(k["ref"], "")}))
            truths.append(Truth(art, r[k["truth"]], f"{source_kind}:{Path(r.get(k['grade_file']) or labels_csv).name}",
                                at=(r.get(k["at"]) if k["at"] else "") or "1970-01-01T00:00:00Z",
                                case=r[k["case"]], note=r.get(k["note"], "")))
    return cases, truths


def read_decisions(lane_csvs: Iterable[str | Path], case_col: str = "case", lane_col: str = "lane") -> dict[str, str]:
    out = {}
    for p in lane_csvs:
        with open(p) as f:
            for r in csv.DictReader(f):
                out[r[case_col]] = "accept" if r[lane_col] in ACCEPT_LANES else "review"
    return out
