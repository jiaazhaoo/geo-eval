"""evalcore: deciding when an AI's output can be acted on, and proving a change did not make that worse.

Domain-neutral. An *artefact* is any output (a polygon, a date string, a script) known by its content digest; a *truth*
is a label somebody gave that artefact, with a source and a time, appended and never edited; a *case* is the unit
being evaluated, carrying its strata; a *decision* is what a system did with a case (accept / review / reject); a
*benchmark* is a frozen set of cases with their truth and artefact digests, split into dev and holdout; a *gate*
compares a candidate's decisions with a baseline's on a benchmark under declared rules.

Project vocabulary (what the artefact is, where truth comes from, what the actions are called) lives in adapters.
"""
from .model import Artefact, Case, Decision, Truth, digest_of, now_iso
from .truth import TruthRegistry
from .benchmark import Benchmark
from .gate import Check, Gate, GateResult
from . import stats

__all__ = ["Artefact", "Case", "Decision", "Truth", "digest_of", "now_iso", "TruthRegistry", "Benchmark",
           "Check", "Gate", "GateResult", "stats"]
__version__ = "0.1.0"
from .evidence import Evidence, EvidenceSet            # noqa: E402
from .policy import Outcome, Policy, Rule              # noqa: E402
from .calibration import Calibrator, selective         # noqa: E402
__all__ += ["Evidence", "EvidenceSet", "Outcome", "Policy", "Rule", "Calibrator", "selective"]
