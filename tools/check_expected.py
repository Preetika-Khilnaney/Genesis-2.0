#!/usr/bin/env python3
"""Compare ./salvage output with the organisers' expected_outputs. OWNER: Manas (delivery).

    python3 tools/check_expected.py                      # runs ./salvage on real-samples/samples first
    python3 tools/check_expected.py --out out-real       # or check an existing output folder

For each expected file it checks, the way a grader would:
  - format and status match
  - every expected metadata key has the same value
  - records: matched on the expected "match_on" keys; every expected field equal;
    "optional_partial_records" may be present or absent; any other extra record is reported
  - expected_damage: each entry needs one of our damage entries with a kind in "any_of"
    (and the same "lossy" when given)
Exit code 1 if anything differs (so CI and `make test` catch regressions).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "real-samples"


def same(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
        except (TypeError, ValueError):
            return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def check(exp: dict, got: dict) -> list[str]:
    errs = []
    for k in ("format", "status"):
        if got.get(k) != exp.get(k):
            errs.append(f"{k}: expected {exp.get(k)!r}, got {got.get(k)!r}")
    for k, v in (exp.get("metadata") or {}).items():
        if not same(v, (got.get("metadata") or {}).get(k)):
            errs.append(f"metadata.{k}: expected {v!r}, got {(got.get('metadata') or {}).get(k)!r}")
    keys = exp.get("match_on") or []
    key = lambda r: tuple(r.get(k) for k in keys)  # noqa: E731
    ours = {key(r): r for r in got.get("records", [])}
    for r in exp.get("records", []):
        o = ours.pop(key(r), None)
        if o is None:
            errs.append(f"record {key(r)} missing")
            continue
        for k, v in r.items():
            if not same(v, o.get(k)):
                errs.append(f"record {key(r)}.{k}: expected {v!r}, got {o.get(k)!r}")
        if o.get("verified") is False and r.get("verified") is not False:
            errs.append(f"record {key(r)}: marked verified=false")
    optional = {tuple(p.get(k) for k in keys) for p in exp.get("optional_partial_records", [])}
    for k in ours:
        if k not in optional:
            errs.append(f"extra record {k}")
    for want in exp.get("expected_damage", []):
        kinds = set(want.get("any_of", []))
        if not any(d.get("kind") in kinds and ("lossy" not in want or d.get("lossy") == want["lossy"])
                   for d in got.get("damage", [])):
            errs.append(f"damage {sorted(kinds)} lossy={want.get('lossy')} not reported "
                        f"(got {[(d.get('kind'), d.get('lossy')) for d in got.get('damage', [])]})")
    if not exp.get("expected_damage") and any(d.get("lossy") for d in got.get("damage", [])):
        errs.append(f"unexpected lossy damage {[d.get('kind') for d in got.get('damage', []) if d.get('lossy')]}")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kit", type=Path, default=KIT, help="folder with samples/ and expected_outputs/")
    ap.add_argument("--out", type=Path, default=None, help="existing output folder (default: run ./salvage)")
    a = ap.parse_args(argv)
    out = a.out or ROOT / "out-real"
    if a.out is None:
        # same as ./salvage, but runnable on every OS (Windows cannot execute the sh wrapper)
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT / "src"),
                                                                         os.environ.get("PYTHONPATH")]))}
        subprocess.run([sys.executable, "-m", "salvage", str(a.kit / "samples"), str(out)], check=False,
                       stdout=subprocess.DEVNULL, env=env)
    bad = 0
    for e in sorted((a.kit / "expected_outputs").glob("*.json")):
        exp = json.loads(e.read_text(encoding="utf-8"))
        g = out / e.name
        errs = ["no output file"] if not g.exists() else check(exp, json.loads(g.read_text(encoding="utf-8")))
        print(f"{'OK  ' if not errs else 'FAIL'} {e.name}")
        for x in errs[:12]:
            print(f"       {x}")
        bad += bool(errs)
    print(f"\n{len(list((a.kit / 'expected_outputs').glob('*.json'))) - bad} of "
          f"{len(list((a.kit / 'expected_outputs').glob('*.json')))} expected outputs match")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
