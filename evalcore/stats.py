"""The few statistics a gate report needs. No scipy: exact binomial for McNemar, Wilson for proportions."""
from __future__ import annotations

import math
from typing import Iterable, Mapping


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials, as (low, high) proportions. (0, 0) -> (0, 1) for n = 0."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def wilson_upper(k: int, n: int, z: float = 1.96) -> float:
    return wilson(k, n, z)[1]


def _binom_two_sided(b: int, c: int) -> float:
    """Exact two-sided p of b successes in b+c fair-coin trials (McNemar's exact test)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def mcnemar(b: int, c: int) -> dict:
    """Paired comparison on the same cases: b = cases where only A was right, c = only B was right."""
    return {"only_a_right": b, "only_b_right": c, "p_exact": _binom_two_sided(b, c), "n_discordant": b + c}


def paired(truth_right: Mapping[str, bool], a_right: Mapping[str, bool], b_right: Mapping[str, bool]) -> dict:
    """b/c counts over the cases both systems answered; `*_right` maps case -> whether that system got it right."""
    cases = [k for k in truth_right if k in a_right and k in b_right]
    b = sum(1 for k in cases if a_right[k] and not b_right[k])
    c = sum(1 for k in cases if b_right[k] and not a_right[k])
    out = mcnemar(b, c)
    out["n"] = len(cases)
    return out


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "ci95": [round(lo, 4), round(hi, 4)]}


def ece(probs: Iterable[float], outcomes: Iterable[bool], bins: int = 10) -> dict:
    """Expected calibration error with equal-width bins, plus the reliability table."""
    pr, oc = list(probs), list(outcomes)
    if len(pr) != len(oc):
        raise ValueError("probs and outcomes differ in length")
    table, total, n = [], 0.0, len(pr)
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        idx = [j for j, p in enumerate(pr) if (lo <= p < hi) or (i == bins - 1 and p == 1.0)]
        if not idx:
            continue
        conf = sum(pr[j] for j in idx) / len(idx)
        acc = sum(1 for j in idx if oc[j]) / len(idx)
        total += abs(acc - conf) * len(idx)
        table.append({"bin": [round(lo, 2), round(hi, 2)], "n": len(idx), "confidence": round(conf, 4), "accuracy": round(acc, 4)})
    return {"ece": round(total / n, 4) if n else None, "n": n, "bins": table}
