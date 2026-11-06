"""The five objects every other module speaks in. Frozen dataclasses: a record is a fact, not a mutable row."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


def digest_of(obj: Any) -> str:
    """Content digest of anything JSON-serialisable (bytes and str hashed as-is). Same content, same digest."""
    if isinstance(obj, (bytes, bytearray)):
        raw = bytes(obj)
    elif isinstance(obj, str):
        raw = obj.encode()
    else:
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass(frozen=True)
class Artefact:
    """An output under evaluation. `digest` is what truth attaches to: a label about one digest says nothing about another."""
    id: str
    kind: str                      # adapter-defined: "polygon", "text_field", "script" ...
    digest: str
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Truth:
    """One label, from one source, at one time, about one artefact digest. Appended, never edited."""
    artefact: str                  # Artefact.digest
    label: str                     # adapter-defined vocabulary; the gate only needs to know which label means "wrong"
    source: str                    # "<kind>:<who>", kind ranked by the registry (client / person / verified / check / batch / import)
    at: str = field(default_factory=now_iso)
    case: str = ""                 # the case this artefact belongs to, for lookups
    schema: str = "v1"             # label vocabulary version
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Case:
    """The unit of evaluation: an id, its strata (any key -> value), and the digest of the artefact being judged."""
    id: str
    artefact: str
    strata: Mapping[str, str] = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """What a system did with a case. `action` vocabulary is declared to the gate (which one means "acted on without a person")."""
    case: str
    action: str
    why: str = ""
    evidence: tuple = ()
