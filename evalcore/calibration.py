"""Scores -> probabilities, and the selective-prediction view: how much can be accepted at what error.

`bin_fit` fits a monotone (pool-adjacent-violators) map on dev scores; `apply` turns new scores into probabilities;
`selective` gives, for every threshold, the coverage and the error among the covered: the curve behind "the top band
is 88% right on 25% of the cases". ECE and the reliability table are in `stats`.
"""
from __future__ import annotations

from typing import Iterable, Sequence


def pav(scores: Sequence[float], outcomes: Sequence[bool]) -> list[tuple[float, float]]:
    """Isotonic regression by pool-adjacent-violators: -> sorted (score, fitted probability) knots."""
    pairs = sorted(zip(scores, (1.0 if o else 0.0 for o in outcomes)))
    blocks: list[list] = []                              # [sum, n, max_score]
    for s, y in pairs:
        blocks.append([y, 1, s])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            a, b = blocks.pop(), blocks.pop()
            blocks.append([a[0] + b[0], a[1] + b[1], max(a[2], b[2])])
    return [(b[2], b[0] / b[1]) for b in blocks]


class Calibrator:
    def __init__(self, knots: list[tuple[float, float]]):
        self.knots = knots

    @classmethod
    def fit(cls, scores: Sequence[float], outcomes: Sequence[bool]) -> "Calibrator":
        return cls(pav(scores, outcomes))

    def prob(self, score: float) -> float:
        p = self.knots[0][1] if self.knots else 0.5
        for s, q in self.knots:
            if score >= s:
                p = q
            else:
                break
        return p

    def apply(self, scores: Iterable[float]) -> list[float]:
        return [self.prob(s) for s in scores]


def selective(scores: Sequence[float], outcomes: Sequence[bool], higher_is_better: bool = True) -> list[dict]:
    """For each distinct threshold: coverage (share accepted) and error (share wrong among accepted)."""
    pairs = sorted(zip(scores, outcomes), key=lambda p: p[0], reverse=higher_is_better)
    n, out, acc, wrong = len(pairs), [], 0, 0
    for i, (s, o) in enumerate(pairs):
        acc += 1
        wrong += int(not o)
        if i + 1 == n or pairs[i + 1][0] != s:
            out.append({"threshold": s, "coverage": round(acc / n, 4), "error": round(wrong / acc, 4), "n": acc, "wrong": wrong})
    return out
