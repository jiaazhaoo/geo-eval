"""Adapter for the delivered-polygon QA flow: labels.csv (truth) + qa_final.csv (decisions) -> evalcore objects.

Vocabulary mapped here and nowhere in evalcore:
  truth labels   labels.csv `truth` column: right / wrong (the client's verdict on the exact polygon it graded)
  actions        qa_final.csv `lane` column: "auto pass" -> accept, anything else -> review
  strata         labels.csv `stratum` column "<council>|<label>|<capture>|<kind>" -> keys council / capture / kind
  artefact       the polygon itself is not in these files; its digest is taken from the delivery file + case id
                 (what the client graded), which is enough to tell a re-delivered polygon from the graded one
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from evalcore import Case, Truth, digest_of

ACTION_OF = {"auto pass": "accept"}
STRATUM_KEYS = ("council", "label", "capture", "kind")


def read_labels(labels_csv: str | Path, source_kind: str = "client") -> tuple[list[Case], list[Truth]]:
    cases, truths = [], []
    with open(labels_csv) as f:
        for r in csv.DictReader(f):
            parts = (r.get("stratum") or "").split("|")
            strata = {k: v for k, v in zip(STRATUM_KEYS, parts) if k != "label"}
            if not strata.get("council"):
                strata["council"] = r.get("council", "")
            art = digest_of({"case": r["case"], "delivery": r.get("delivery_file", ""), "oa": r.get("orig_oachargeid", "")})
            cases.append(Case(r["case"], art, strata, {"ref": r.get("ref", "")}))
            truths.append(Truth(art, r["truth"], f"{source_kind}:{Path(r.get('grade_file') or labels_csv).name}",
                                at=r.get("batch_date") or "1970-01-01T00:00:00Z", case=r["case"], note=r.get("error_note", "")))
    return cases, truths


def read_decisions(qa_final_csvs: Iterable[str | Path]) -> dict[str, str]:
    out = {}
    for p in qa_final_csvs:
        with open(p) as f:
            for r in csv.DictReader(f):
                out[r["case"]] = ACTION_OF.get(r["lane"], "review")
    return out
