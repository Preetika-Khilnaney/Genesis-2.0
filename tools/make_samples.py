#!/usr/bin/env python3
"""Generate the project's samples (our demo data). OWNER: Preetika.

    python3 tools/make_samples.py         # or: make samples
                                          # writes samples/<format>/ and sample-answers/<format>/

Naming: "samples" = these files, made by us. "real samples" = the organisers' files, which
go in real-samples/<format>/ (git-ignored, may be sensitive) and are never mixed with these.

Two kinds of sample, and the difference matters:

  STAND-INS (layout invented by us; the real format WILL differ):
      samples/libra98/   samples/lablog/   samples/vault/
    Same kind of structure as the real formats (header + records; checksummed blocks;
    index + RLE + XOR), so the full flow can be wired up and tested now. When the real
    samples arrive, redo the SPEC from their bytes. Only the spec should change: the
    decoder glue, checks pattern, tests and Docker setup carry over.

  REAL PUBLIC FORMATS (layout follows the published format):
      samples/wks/       Lotus 1-2-3 worksheet (.WKS): candidate real-world format
      samples/pak/       Quake PACK archive (.PAK): candidate game archive
    Built from the public format descriptions. Still check them against the real samples,
    which may use other record types or be damaged on purpose.

Every folder also gets a few damaged copies (<name>.damaged-<what>). The true contents of
every file, and what damage was done, are in sample-answers/ (outside samples/, so
./salvage never reads them). Output is the same on every run (fixed seed).
"""
from __future__ import annotations

import argparse
import json
import random
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import corrupt   # noqa: E402
import practice  # noqa: E402

STAND_IN_MAGIC = {"libra98": (practice.PREC_MAGIC, b"LIBRA-98"),
                  "lablog": (practice.PLOG_MAGIC, b"LBLG"),
                  "vault": (practice.PARC_MAGIC, b"VALT")}


# ---------------- stand-ins (reuse the practice generators, new magic) ----------------

def stand_in(fmt: str, rng: random.Random, k: int) -> tuple[bytes, dict]:
    maker = {"libra98": practice.make_prec, "lablog": practice.make_plog, "vault": practice.make_parc}[fmt]
    data, truth = maker(rng, k)
    old, new = STAND_IN_MAGIC[fmt]
    assert data.startswith(old) and len(old) == len(new)
    truth["format"] = f"{fmt} (STAND-IN: invented layout, not the real format)"
    return new + data[len(old):], truth


# ---------------- Lotus 1-2-3 .WKS (real format) ----------------
# Every record: u16 opcode, u16 length, body. Little-endian. Cells: u8 format, u16 col, u16 row.

WKS_BOF, WKS_EOF, WKS_RANGE = 0x0000, 0x0001, 0x0006
WKS_INTEGER, WKS_NUMBER, WKS_LABEL = 0x000D, 0x000E, 0x000F
FMT = 0xFF   # "default" cell format byte (protected bit + default format)


def wks_record(op: int, body: bytes) -> bytes:
    return struct.pack("<HH", op, len(body)) + body


def make_wks(rng: random.Random, k: int) -> tuple[bytes, dict]:
    items = ["Rice", "Wheat", "Sugar", "Oil", "Salt", "Tea", "Dal", "Milk"]
    rows = rng.sample(items, rng.randint(3, 6))
    cells, truth = [], []

    def label(col, row, text):
        cells.append(wks_record(WKS_LABEL, struct.pack("<BHH", FMT, col, row) + b"'" + text.encode() + b"\x00"))
        truth.append({"col": col, "row": row, "type": "label", "value": text})

    def integer(col, row, v):
        cells.append(wks_record(WKS_INTEGER, struct.pack("<BHHh", FMT, col, row, v)))
        truth.append({"col": col, "row": row, "type": "integer", "value": v})

    def number(col, row, v):
        cells.append(wks_record(WKS_NUMBER, struct.pack("<BHHd", FMT, col, row, v)))
        truth.append({"col": col, "row": row, "type": "number", "value": v})

    label(0, 0, "Item"), label(1, 0, "Qty"), label(2, 0, "Price")
    for r, item in enumerate(rows, start=1):
        label(0, r, item)
        integer(1, r, rng.randint(1, 500))
        number(2, r, round(rng.uniform(5, 400), 2))
    last_row = len(rows)
    data = (wks_record(WKS_BOF, struct.pack("<H", 0x0404))                       # 0x0404 = .WKS
            + wks_record(WKS_RANGE, struct.pack("<HHHH", 0, 0, 2, last_row))     # active range
            + b"".join(cells)
            + wks_record(WKS_EOF, b""))
    return data, {"format": "wks (Lotus 1-2-3, real public format)",
                  "layout": "records of u16 opcode, u16 length, body; BOF 0x0000 (0x0404), RANGE 0x0006, "
                            "INTEGER 0x000D, NUMBER 0x000E (f64), LABEL 0x000F (prefix char + NUL text), EOF 0x0001",
                  "cells": truth}


# ---------------- Quake .PAK (real format) ----------------
# Header: "PACK", i32 directory offset, i32 directory length. Entry (64 bytes): name[56], i32 offset, i32 size.

def make_pak(rng: random.Random, k: int) -> tuple[bytes, dict]:
    names = ["maps/e1m1.bsp", "sound/door.wav", "gfx/palette.lmp", "progs/player.mdl",
             "scripts/autoexec.cfg", "maps/start.bsp", "sound/ambience.wav"]
    files = []
    for n in rng.sample(names, rng.randint(2, 5)):
        if n.endswith(".cfg"):
            body = f"// pak {k}\nbind w +forward\nbind s +back\nsensitivity {rng.randint(3, 9)}\n".encode()
        else:
            body = n.encode() + b"\x00" + bytes(rng.randrange(256) for _ in range(rng.randint(40, 200)))
        files.append((n, body))
    blob, entries, pos = b"", [], 12
    for n, body in files:
        entries.append((n, pos, len(body)))
        blob += body
        pos += len(body)
    directory = b"".join(n.encode().ljust(56, b"\x00") + struct.pack("<ii", o, s) for n, o, s in entries)
    data = b"PACK" + struct.pack("<ii", 12 + len(blob), len(directory)) + blob + directory
    return data, {"format": "pak (Quake PACK archive, real public format)",
                  "layout": "'PACK', i32 dir_offset, i32 dir_length; directory at the END: 64-byte entries "
                            "of name[56] NUL-padded, i32 offset, i32 size",
                  "entries": [{"name": n, "offset": o, "size": s} for n, o, s in entries]}


MAKERS = {
    "libra98": (lambda r, k: stand_in("libra98", r, k), ".l98"),
    "lablog": (lambda r, k: stand_in("lablog", r, k), ".lbl"),
    "vault": (lambda r, k: stand_in("vault", r, k), ".vlt"),
    "wks": (make_wks, ".wks"),
    "pak": (make_pak, ".pak"),
}
DAMAGE_PER_FORMAT = ("trunc90", "flip0", "zeroed", "inserted")   # a few, like a real sample pack


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--samples", type=Path, default=ROOT / "samples")
    ap.add_argument("--answers", type=Path, default=ROOT / "sample-answers")
    ap.add_argument("--count", type=int, default=6, help="clean files per format")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    a.answers.mkdir(parents=True, exist_ok=True)
    (a.answers / "README.md").write_text(
        "# sample-answers/\n\nTrue contents of every file in samples/ (made by tools/make_samples.py), and\n"
        "manifest.json per format listing the damaged copies and what was done to them.\n\n"
        "libra98, lablog and vault are STAND-INS with an invented layout; wks and pak follow the real\n"
        "public formats. The organisers' files are the real samples: they go in real-samples/.\n")
    total = 0
    for fmt, (make, ext) in MAKERS.items():
        d, ad = a.samples / fmt, a.answers / fmt
        d.mkdir(parents=True, exist_ok=True)
        ad.mkdir(parents=True, exist_ok=True)
        manifest, clean_files = [], []
        for k in range(a.count):
            data, truth = make(rng, k)
            name = f"{fmt}_{k}{ext}"
            (d / name).write_bytes(data)
            (ad / f"{name}.json").write_text(json.dumps(truth, indent=2) + "\n")
            clean_files.append((name, data))
            total += 1
        for name, data in clean_files[:2]:
            for tag, (blob, info) in corrupt.variants(data, rng).items():
                if tag.startswith(DAMAGE_PER_FORMAT):
                    dn = f"{Path(name).stem}.damaged-{tag}{ext}"
                    (d / dn).write_bytes(blob)
                    manifest.append({"file": dn, "source": name, **info})
                    total += 1
        (ad / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {total} samples to {a.samples}/ (libra98, lablog, vault = STAND-INS with invented "
          f"layouts; wks, pak = real public formats). Answers in {a.answers}/.")
    print("The organisers' files are the real samples: put them in real-samples/<format>/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
