from evalcore import Calibrator, Evidence, EvidenceSet, Policy, Rule, selective, stats


def test_evidence_families():
    es = EvidenceSet([Evidence("judge_a", "correct", "model", "drawing-reader", 0.01),
                      Evidence("judge_b", "correct", "model", "drawing-reader", 0.003),
                      Evidence("parcel_iou", 0.9, "deterministic", "address-register")])
    assert es.independent(["judge_a", "judge_b"]) == 1
    assert es.independent(["judge_a", "parcel_iou"]) == 2
    assert abs(es.cost() - 0.013) < 1e-9 and es.facts()["parcel_iou"] == 0.9


def test_policy_order_trail_measure():
    rules = [Rule("all_correct", lambda f: f["a"] and f["b"], "accept", from_actions=None, when_text="both readers correct"),
             Rule("far_away", lambda f: f.get("far", False), "review", from_actions=("accept",), when_text="far from the address"),
             Rule("rescue", lambda f: f.get("parcel", False) and "far_away" not in f["_trail"], "accept", from_actions=("review",),
                  when_text="own parcel and no guard fired")]
    p = Policy("t", "v1", rules)
    o = p.decide({"a": True, "b": True, "far": True})
    assert o.action == "review" and o.trail == ["all_correct", "far_away"] and o.decisive == "far_away"
    o2 = p.decide({"a": True, "b": False, "parcel": True})
    assert o2.action == "accept" and o2.decisive == "rescue"
    o3 = p.decide({"a": True, "b": True, "far": True, "parcel": True})
    assert o3.action == "review"                             # the rescue sees that a guard fired
    outs = p.decide_all({"c1": {"a": True, "b": True}, "c2": {"a": True, "b": True}, "c3": {"a": False, "b": True}})
    m = p.measure(outs, {"c1": "right", "c2": "wrong", "c3": "wrong"}, benchmark="t-v1")
    assert m["all_correct"]["accepted"] == 2 and m["all_correct"]["accepted_wrong"] == 1
    assert "all_correct" in p.table() and "1/2" in p.table()
    assert m["all_correct"]["reviewed"] == 0


def test_calibration_and_selective():
    scores = [0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9]
    outcomes = [False, False, True, False, True, True, True, True]
    c = Calibrator.fit(scores, outcomes)
    probs = c.apply(scores)
    assert all(probs[i] <= probs[i + 1] + 1e-12 for i in range(len(probs) - 1))     # monotone
    assert c.prob(0.95) == probs[-1] and c.prob(0.0) == probs[0]
    curve = selective(scores, outcomes)
    assert curve[0]["coverage"] == 0.125 and curve[0]["error"] == 0.0 and curve[-1]["coverage"] == 1.0
    assert stats.ece(probs, outcomes)["ece"] < 0.2
