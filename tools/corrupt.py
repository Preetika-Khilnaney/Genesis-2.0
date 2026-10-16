#!/usr/bin/env python3
"""Corruption lab (mini). OWNER: Manas.

Makes damaged copies of clean sample files so we can test recovery and measure
how often the tool is wrong:

    python tools/corrupt.py samples/libra98/a.bin --out tests/fixtures/damaged --seed 1

Writes <name>.truncN, <name>.flipK (single bit flips), <name>.zeroed (a zeroed block).
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path


def variants(data: bytes, rng: random.Random) -> dict[str, bytes]:
    out = {}
    if len(data) > 4:
        for frac in (0.5, 0.9):
            cut = int(len(data) * frac)
            out[f"trunc{int(frac * 100)}"] = data[:cut]
        for k in range(3):
            buf = bytearray(data)
            bit = rng.randrange(len(buf) * 8)
            buf[bit // 8] ^= 1 << (bit % 8)
            out[f"flip{k}_bit{bit}"] = bytes(buf)
        start = rng.randrange(len(data))
        end = min(len(data), start + max(1, len(data) // 10))
        out[f"zeroed_{start}_{end}"] = data[:start] + bytes(end - start) + data[end:]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    for f in a.files:
        for tag, blob in variants(f.read_bytes(), rng).items():
            (a.out / f"{f.name}.{tag}").write_bytes(blob)
    print(f"wrote damaged variants to {a.out}")


if __name__ == "__main__":
    main()
