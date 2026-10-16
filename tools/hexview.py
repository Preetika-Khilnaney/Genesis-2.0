#!/usr/bin/env python3
"""Reverse-engineering helper for everyone (hour 0).

    python tools/hexview.py samples/libra98/*            # hex + entropy + strings per file
    python tools/hexview.py --diff samples/libra98/*     # which byte positions are constant across files
    python tools/hexview.py --ints 0x08 samples/x/*      # u16/u32 LE+BE at an offset, per file (spot length fields)

Standard library only. Log what you learn in FIELD-LOG.md as you go.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from salvage.core.fingerprint import entropy, printable_strings  # noqa: E402


def hexdump(data: bytes, limit: int) -> None:
    for off in range(0, min(len(data), limit), 16):
        chunk = data[off:off + 16]
        hx = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{off:08x}  {hx:<47}  {asc}")


def show(path: Path, limit: int) -> None:
    data = path.read_bytes()
    print(f"== {path}  size={len(data)}  entropy={entropy(data):.2f} bits/byte")
    hexdump(data, limit)
    strs = printable_strings(data, limit=15)
    if strs:
        print("strings:", ", ".join(f"{s['offset']:#x}:{s['text']!r}" for s in strs))
    print()


def diff(paths: list[Path], limit: int) -> None:
    blobs = [p.read_bytes() for p in paths]
    n = min(min(len(b) for b in blobs), limit)
    print(f"sizes: {[len(b) for b in blobs]}")
    row = []
    for i in range(n):
        vals = {b[i] for b in blobs}
        row.append(f"{blobs[0][i]:02x}" if len(vals) == 1 else "..")
        if len(row) == 16:
            print(f"{i - 15:08x}  {' '.join(row)}")
            row = []
    if row:
        print(f"{n - len(row):08x}  {' '.join(row)}")
    print("\n'..' = differs between files (data); hex = constant (magic, version, padding)")


def ints(paths: list[Path], offset: int) -> None:
    print(f"offset {offset:#x}: file  size  u16le  u16be  u32le  u32be")
    for p in paths:
        d = p.read_bytes()
        def u(fmt, n):
            return struct.unpack(fmt, d[offset:offset + n])[0] if offset + n <= len(d) else None
        print(f"  {p.name}  {len(d)}  {u('<H', 2)}  {u('>H', 2)}  {u('<I', 4)}  {u('>I', 4)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--ints", type=lambda s: int(s, 0))
    ap.add_argument("--limit", type=int, default=256)
    a = ap.parse_args()
    if a.diff:
        diff(a.files, a.limit)
    elif a.ints is not None:
        ints(a.files, a.ints)
    else:
        for p in a.files:
            show(p, a.limit)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:      # e.g. piped into head
        pass
