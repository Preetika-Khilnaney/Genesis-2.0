"""Evidence check: accept a field meaning only if it holds on every sample. OWNER: Bhupesh.

Today's version (hackathon): a hypothesis is ACCEPTED only when it holds on all
samples and there are at least MIN_SAMPLES of them, and REJECTED as soon as one
sample contradicts it. Anything else stays OPEN and the field is `unverified`.

Roadmap (pitch, not built today): replace the all-samples rule with MDL scoring and
held-out e-values (accept at >= 20 : 1).

Every call records its result in the ledger, so FIELD-LOG.md captures failures too.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import ledger

MIN_SAMPLES = 3


@dataclass
class Verdict:
    hypothesis: str
    outcome: str             # "accepted" | "rejected" | "open"
    held: int
    total: int
    counterexamples: list[int]

    @property
    def accepted(self) -> bool:
        return self.outcome == "accepted"


def evaluate(fmt: str, hypothesis: str, samples: list[bytes], test: Callable[[bytes], bool],
             author: str = "", log: bool = True) -> Verdict:
    held, bad = 0, []
    for i, s in enumerate(samples):
        try:
            ok = bool(test(s))
        except Exception:
            ok = False
        if ok:
            held += 1
        else:
            bad.append(i)
    if bad:
        outcome = "rejected"
    elif held >= MIN_SAMPLES:
        outcome = "accepted"
    else:
        outcome = "open"
    v = Verdict(hypothesis, outcome, held, len(samples), bad)
    if log:
        ledger.log(fmt, hypothesis,
                   evidence=f"held on {held}/{len(samples)} samples"
                            + (f"; counterexamples: samples {bad}" if bad else ""),
                   outcome=outcome, author=author)
    return v


def best_of(fmt: str, field: str, samples: list[bytes],
            candidates: dict[str, Callable[[bytes], bool]], author: str = "") -> str | None:
    """Try every candidate meaning for one field. Return the single accepted one, or None
    when zero or several survive (ambiguous -> keep the field unverified)."""
    survivors = [name for name, test in candidates.items()
                 if evaluate(fmt, f"{field} is {name}", samples, test, author).accepted]
    return survivors[0] if len(survivors) == 1 else None
