#!/usr/bin/env python3
"""Corruption lab (mini). OWNER: Manas.

Makes damaged copies of clean sample files so we can test recovery and measure
how often the tool is wrong:

    python3 tools/corrupt.py real-samples/samples/s01.dat --out tests/fixtures/damaged --seed 1

Damage types (one file each, the name says what was done and where):
    truncN            file cut to N% of its length
    flipK_bitB        one bit flipped at bit offset B
    zeroed_S_E        bytes S..E overwritten with zeros
    inserted_S_N      N random bytes inserted at offset S (shifts everything after)
    deleted_S_N       N bytes removed at offset S (shifts everything after)

Inserted and deleted bytes are the hard case: every later offset moves, so a decoder
must resync on markers or report the rest as damaged, never read shifted garbage
as valid records.

Each run also writes manifest.json listing every variant and its damage, so tests
can compare what the tool reported against what was really done.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def variants(data: bytes, rng: random.Random) -> dict[str, tuple[bytes, dict]]:
    """name -> (damaged bytes, description of the damage)."""
    out: dict[str, tuple[bytes, dict]] = {}
    n = len(data)
    if n <= 4:
        return out
    for frac in (0.5, 0.9):
        cut = int(n * frac)
        out[f"trunc{int(frac * 100)}"] = (data[:cut], {"type": "truncate", "keep": cut})
    for k in range(3):
        buf = bytearray(data)
        bit = rng.randrange(n * 8)
        buf[bit // 8] ^= 1 << (bit % 8)
        out[f"flip{k}_bit{bit}"] = (bytes(buf), {"type": "bit_flip", "bit": bit, "byte": bit // 8})
    start = rng.randrange(n)
    end = min(n, start + max(1, n // 10))
    out[f"zeroed_{start}_{end}"] = (data[:start] + bytes(end - start) + data[end:],
                                    {"type": "zeroed", "start": start, "end": end})
    for size in (1, max(2, n // 20)):
        at = rng.randrange(1, n)
        junk = bytes(rng.randrange(256) for _ in range(size))
        out[f"inserted_{at}_{size}"] = (data[:at] + junk + data[at:],
                                        {"type": "inserted", "offset": at, "count": size})
    for size in (1, max(2, n // 20)):
        at = rng.randrange(1, n - size)
        out[f"deleted_{at}_{size}"] = (data[:at] + data[at + size:],
                                       {"type": "deleted", "offset": at, "count": size})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for f in a.files:
        for tag, (blob, info) in variants(f.read_bytes(), rng).items():
            name = f"{f.name}.{tag}"
            (a.out / name).write_bytes(blob)
            manifest.append({"file": name, "source": f.name, **info})
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {len(manifest)} damaged variants and manifest.json to {a.out}")


if __name__ == "__main__":
    main()
