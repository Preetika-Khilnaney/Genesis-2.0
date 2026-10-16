#!/usr/bin/env python3
"""Measure false recoveries on the real samples. OWNER: Manas (delivery).

    python3 tools/false_recovery.py [--flips 400] [--seed 5]

Takes every clean real sample, flips 1-3 random bits many times, decodes each damaged copy and
compares every record marked verified with the record decoded from the clean file. A record that
is marked verified but differs is a FALSE RECOVERY. Prints the rate per format.

Formats without checksums (WKS, CVT, WAD, PAK, WPD, BRAVO) are listed too: a bit flipped inside a
value there can only be caught by value checks, so their rate shows what is undetectable.
"""
from __future__ import annotations

import argparse
import collections
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from salvage import formats  # noqa: E402,F401
from salvage.core.fingerprint import identify_detailed  # noqa: E402
from salvage.output.contract import to_contract  # noqa: E402

KEYS = {"LIBRA-98": "id", "LABLOG": "sample", "VAULT": "id", "EBCDIC-DUMP": "student_id", "WKS": "cell",
        "CVT": "slot", "WAD": "name", "PAK": "name", "WPD": "index", "BRAVO": "index"}


def strip(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("verified", "issues")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--samples", type=Path, default=ROOT / "real-samples" / "samples")
    ap.add_argument("--flips", type=int, default=400)
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    stats: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for f in sorted(p for p in a.samples.iterdir() if p.is_file()):
        b = f.read_bytes()
        ident = identify_detailed(b)
        if ident.decoder is None:
            continue
        dec, key = ident.decoder, KEYS.get(ident.decoder.name)
        clean = to_contract(dec.decode(f.name, b))
        if clean["status"] != "ok" or key is None:
            continue                                  # only clean files give a ground truth
        truth = {r.get(key): strip(r) for r in clean["records"]}
        for _ in range(a.flips):
            c = bytearray(b)
            for _ in range(rng.choice([1, 1, 1, 2, 3])):
                c[rng.randrange(len(c))] ^= 1 << rng.randrange(8)
            out = to_contract(dec.decode(f.name, bytes(c)))
            for r in out["records"]:
                if r.get("verified") is False:
                    stats[dec.name]["unverified"] += 1
                elif truth.get(r.get(key)) == strip(r):
                    stats[dec.name]["verified_right"] += 1
                else:
                    stats[dec.name]["FALSE"] += 1
    print(f"{'format':12} {'verified ok':>12} {'unverified':>11} {'FALSE':>7}   false rate")
    worst = 0.0
    for fmt, s in sorted(stats.items()):
        tot = sum(s.values()) or 1
        rate = s["FALSE"] / tot
        print(f"{fmt:12} {s['verified_right']:12} {s['unverified']:11} {s['FALSE']:7}   {rate:7.2%}")
        worst = max(worst, rate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
