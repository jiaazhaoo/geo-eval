"""Adapter for the delivered-polygon QA flow: its lab files -> facts, and its lane logic -> a Policy of 14 rules.

This file carries the project's vocabulary (judges, recheck, appeal, firm match, address parcel, case types). The
fact builders reuse the project's own helper functions so the rules here are *the* rules, not a paraphrase; the
check that proves it is `Policy.decide` reproducing every frozen lane of a benchmark.

Facts (per case):                                               source        family
  local_verdict / local_correct / local_bad                     deterministic  geometry
  judge_all_correct / judge_any_correct / judge_split /
  veto_correct / judge_too_big / size_only                      model          drawing-reader
  recheck_on / recheck_answered / recheck_correct               model          drawing-reader
  appeal_all_pass                                               model          drawing-reader
  own_parcel / snapped_firm / firm_match / address_in_input /
  traced_iou                                                    deterministic  geometry | address-register
  amended / next_to / far_m / addr_extra / routing_check        record+deterministic
  has_plan / case_type                                          deterministic
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from evalcore import Policy, Rule

E2E = Path(os.environ.get("E2E_REPO", "/env/code/e2e-plan-extract"))
sys.path.insert(0, str(E2E / "e2e_plan_extract" / "s4_verify"))
sys.path.insert(0, str(E2E))
import qa_final as qf              # noqa: E402  the project's helpers (regexes, parcel tests, distance test)
import type_routing as tr          # noqa: E402

JUDGES = ("gemini-3.8-flash", "gpt-6-luna-pro")
RECHECK, VETO = "gemini-3.8-flash-recheck", "gemini-3.8-flash"
APPEAL = ("gemini-3.8-flash-appeal", "gpt-6-luna-pro-appeal")
RESCUE_TYPES = ("T2", "T8", "T9")


def _j(lab: Path, tag: str) -> dict:
    p = lab / f"judge_{tag}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def facts_for_lab(lab: Path, case_prefix: str) -> dict[str, dict]:
    """Every fact the policy needs, for every case in lab/qa.json."""
    lab = Path(lab)
    W = lab.parent
    os.environ["CASE_PREFIX"] = case_prefix
    Q = json.loads((lab / "qa.json").read_text())
    plans = {p["case"] for p in json.loads((lab / "plans.json").read_text())} if (lab / "plans.json").exists() else set(Q)
    J = {t: _j(lab, t) for t in JUDGES}
    RC, AP = _j(lab, RECHECK), {t: _j(lab, t) for t in APPEAL}
    PROP = qf.proposals(W)
    RT = tr.load(None)
    cc = json.loads((lab / "case_class.json").read_text()) if (lab / "case_class.json").exists() else {}
    out = {}
    for c, v in Q.items():
        says = {t: (J[t].get(c) or {}) for t in JUDGES}
        verd = [s.get("verdict") for s in says.values()]
        ct = tr.case_type(cc.get(c), PROP.get(c, ""))
        ti = v.get("traced_iou")
        try:
            ti = float(ti) if ti not in (None, "") else None
        except (TypeError, ValueError):
            ti = None
        rc = RC.get(c) or {}
        out[c] = {
            "local_verdict": v["verdict"], "local_correct": v["verdict"] == "correct", "local_bad": v["verdict"] in ("wrong", "query"),
            "judge_all_correct": all(x == "correct" for x in verd), "judge_any_correct": any(x == "correct" for x in verd),
            "judge_split": qf.split(says), "veto_correct": (says.get(VETO) or {}).get("verdict") == "correct",
            "judge_too_big": any(s.get("error") == "too_big" for s in says.values()),
            "size_only": all(s.get("verdict") == "correct" or s.get("error") in ("too_big", "too_small") for s in says.values())
                         and all(s.get("verdict") for s in says.values()),
            "recheck_on": True, "recheck_answered": bool(rc), "recheck_correct": rc.get("verdict") == "correct",
            "appeal_on": bool(AP[APPEAL[0]] or AP[APPEAL[1]]),
            "appeal_all_pass": all((AP[t].get(c) or {}).get("appeal_pass") for t in APPEAL),
            "own_parcel": qf.own_parcel(v), "snapped_firm": qf.snapped_firm(v), "firm_match": str(v.get("firm_match")) == "True",
            "address_in_input": str(v.get("address_in_input")) == "True", "traced_iou": ti,
            "amended": bool(qf.AMENDED.search(PROP.get(c, ""))), "next_to": qf.next_to_own_parcel(v),
            "far_m": qf.far_from_record(v), "addr_extra": qf.addr_extra_inside(v, PROP.get(c, "")),
            "routing_check": tr.check(RT, ct, v), "has_plan": c in plans, "case_type": ct,
        }
    return out


def _demoted(f) -> bool:
    """A guard sent the case back from accept (the project's `" -- but " in why`)."""
    return any(r in f["_trail"] for r in GUARDS)


GUARDS = ("recheck_missing", "recheck_doubts", "amended_plans", "next_to_own_parcel", "far_from_record",
          "addr_extra_inside", "traced_disagrees", "type_routing")


def policy() -> Policy:
    A, R = ("accept",), ("review",)
    rules = [
        Rule("judges_all_correct", lambda f: f["judge_all_correct"] and not f["local_bad"], "accept",
             when_text="both drawing readers say correct; the local check did not say wrong / query", note="decision #22: every case is judged"),
        Rule("recheck_missing", lambda f: f["recheck_on"] and not f["recheck_answered"], "review", A,
             when_text="the boundary recheck did not answer", note="a two-reader pass needs the recheck"),
        Rule("recheck_doubts", lambda f: f["recheck_on"] and f["recheck_answered"] and not f["recheck_correct"] and not f["own_parcel"], "review", A,
             when_text="the recheck doubts it and the polygon is not the address's own parcel", note="2026-10-07; parcel stand-down 2026-11-05"),
        Rule("appeal_pass", lambda f: not f["judge_all_correct"] and not f["local_bad"] and f["appeal_on"] and f["appeal_all_pass"], "accept", R,
             when_text="readers did not both pass; every appeal answer passes (marking found, location confirmed)", note="judge-context_appeal-20261022-1"),
        Rule("firm_match_size_only", lambda f: f["local_correct"] and f["firm_match"] and f["size_only"] and not f["local_bad"], "accept", R,
             when_text="the traced plot (or its snap to OS lines) IS the polygon and the readers only complain about size", note="lanes-ring_extent-20261105-3"),
        Rule("amended_plans", lambda f: f["amended"] and not f["snapped_firm"], "review", A,
             when_text="the proposal says the plans were amended and no snapped firm match", note="2026-10-05: superseded sheet picked"),
        Rule("next_to_own_parcel", lambda f: bool(f["next_to"]), "review", A,
             when_text="site is land next to No. N but the polygon is N's own parcel", note="issue #1; 68 error / 32 correct by people"),
        Rule("far_from_record", lambda f: f["far_m"] is not None, "review", A,
             when_text="polygon far from the record's own place AND from every address the register finds", note="2026-10-26: 89 km off"),
        Rule("addr_extra_inside", lambda f: bool(f["addr_extra"]), "review", A,
             when_text="the polygon holds an address the record does not name", note="a client capture rule on address coverage"),
        Rule("traced_disagrees", lambda f: f["traced_iou"] is not None and f["traced_iou"] < 0.3, "review", A,
             when_text="the plot traced on the drawing disagrees with the polygon (IoU < 0.3)", note="trace-seg_gate-20261028-1"),
        Rule("type_routing", lambda f: bool(f["routing_check"]), "review", A,
             when_text="the case type's row requires evidence the case lacks", note="lanes-type_routing-20261027-5"),
        Rule("evidence_consistent", lambda f: f["local_correct"] and f["address_in_input"] and f["case_type"] in RESCUE_TYPES and f["has_plan"]
             and f["judge_any_correct"] and not (f["traced_iou"] is not None and f["traced_iou"] < 0.3) and f["veto_correct"]
             and not f["judge_too_big"] and not _demoted(f) and not f["local_bad"], "accept", R,
             when_text="own parcel, address inside, works on an existing property, one reader correct, veto reader correct, no size complaint, no guard fired",
             note="lanes-evidence_consistent-20261028-1 + hotfix: 24 cases, 0 wrong on three sets"),
        Rule("no_drawing", lambda f: not f["has_plan"], "review", A,
             when_text="no drawing to check against", note="2026-10-05: a check without a drawing is not enough"),
    ]
    return Policy("polygon-qa-lanes", "qa-20261105", rules, default="review")
