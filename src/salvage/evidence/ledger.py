"""Hypothesis ledger -> FIELD-LOG.md. OWNER: Bhupesh (evidence). Used by EVERYONE.

FIELD-LOG.md is scored: it must be a dated log of every hypothesis, including the
ones that failed. Log as you go, never at the end.

From code:
    from salvage.evidence import ledger
    ledger.log("lablog", "u16 at 0x04 is block length", "matched 5/5 samples", "accepted", "Khushi")

From the terminal:
    python3 tools/log.py lablog "u16 at 0x04 is block length" "matched 5/5" accepted --by Khushi

Code-run logging is written to FIELD-LOG.md only when SALVAGE_LOG=1, so normal
`./salvage` runs never touch the repo file.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

LOG_PATH = Path(os.environ.get("SALVAGE_FIELD_LOG", Path(__file__).resolve().parents[3] / "FIELD-LOG.md"))
OUTCOMES = ("accepted", "rejected", "open")


def _row(fmt: str, hypothesis: str, evidence: str, outcome: str, author: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    clean = lambda s: str(s).replace("|", "/").replace("\n", " ")
    return f"| {ts} | {clean(fmt)} | {clean(hypothesis)} | {clean(evidence)} | {outcome} | {clean(author)} |\n"


def log(fmt: str, hypothesis: str, evidence: str, outcome: str, author: str = "", force: bool = False) -> None:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    if not (force or os.environ.get("SALVAGE_LOG") == "1"):
        return
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(_row(fmt, hypothesis, evidence, outcome, author))


def main() -> None:
    p = argparse.ArgumentParser(description="Append one hypothesis to FIELD-LOG.md")
    p.add_argument("format")
    p.add_argument("hypothesis")
    p.add_argument("evidence")
    p.add_argument("outcome", choices=OUTCOMES)
    p.add_argument("--by", default="")
    a = p.parse_args()
    log(a.format, a.hypothesis, a.evidence, a.outcome, a.by, force=True)
    print(f"logged to {LOG_PATH}")


if __name__ == "__main__":
    main()
