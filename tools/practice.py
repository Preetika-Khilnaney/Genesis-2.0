#!/usr/bin/env python3
"""Practice files for rehearsing before the real samples arrive. OWNER: Preetika.

    python3 tools/practice.py                 # writes practice/ (git-ignored)
    python3 tools/practice.py --damaged       # also damaged copies + manifest.json per format

THESE ARE NOT THE REAL FORMATS. They are made-up formats with the same kinds of
structure as the PS 02 formats, so each of us can rehearse the full flow
(survey -> spec -> decoder -> ./salvage -> damage report) on files whose right
answer we know. Never copy a layout from here into formats/*.py.

    practice/prec/   like LIBRA-98: header + fixed-size records, plus one decoy field
                     that looks like a length but is not          -> Preetika, Bhupesh
    practice/plog/   like LABLOG: marker / seq / length / payload / CRC-32 blocks
                                                                  -> Khushi
    practice/parc/   like VAULT: index table, RLE blobs, XOR-obfuscated names
                                                                  -> Khushi, Bhupesh
Each folder has answers/<file>.json with the true decoded contents, so you can check
your output field by field. Manas: point the corruption tool and tests at these.
"""
from __future__ import annotations

import argparse
import json
import random
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

NAMES = ["ASHA PATEL", "RAVI KUMAR", "MEERA IYER", "JOHN DSOUZA", "PRIYA NAIR", "ARJUN MEHTA",
         "SARA KHAN", "VIKRAM RAO", "NEHA JOSHI", "KIRAN DAS", "ANITA ROY", "OMAR SHAIKH"]


def dos_date(y: int, m: int, d: int) -> int:
    return ((y - 1980) << 9) | (m << 5) | d


# ---------------- prec: header + records (LIBRA-98-like) ----------------

PREC_MAGIC = b"PRAC-REC"
PREC_REC = 30            # u32 id, str 20 name, u16 dos_date, u8 grade, u8 flags, u16 pad


def make_prec(rng: random.Random, k: int) -> tuple[bytes, dict]:
    n = rng.randint(3, 12)
    created = 883612800 + k * 86400 * 17             # early 1998
    decoy = n * PREC_REC + 7                          # looks like a length, is not
    header = PREC_MAGIC + struct.pack("<BHIH", 1, n, created, decoy) + b"\x00" * 3   # 20 bytes
    recs, truth = b"", []
    for i in range(n):
        name = rng.choice(NAMES)
        y, m, d = rng.randint(1990, 1997), rng.randint(1, 12), rng.randint(1, 28)
        grade, flags = rng.randint(35, 100), rng.choice([0, 1, 3])
        recs += struct.pack("<I", 1000 + i) + name.encode().ljust(20, b"\x00") + \
            struct.pack("<HBB", dos_date(y, m, d), grade, flags) + b"\x00\x00"
        truth.append({"id": 1000 + i, "name": name, "enrolled": f"{y:04d}-{m:02d}-{d:02d}",
                      "grade": grade, "flags": flags})
    return header + recs, {"format": "prec", "header": {"version": 1, "record_count": n, "created_unix": created,
                                                        "decoy_u16_at_15": decoy}, "records": truth}


# ---------------- plog: checksummed blocks (LABLOG-like) ----------------

PLOG_MAGIC = b"PLOG"
PLOG_MARK = b"\xA5\x5A"


def make_plog(rng: random.Random, k: int) -> tuple[bytes, dict]:
    inst = 40 + k
    out, truth = PLOG_MAGIC + struct.pack("<H", inst), []
    t = 0
    for seq in range(rng.randint(4, 10)):
        t += rng.randint(30, 90)
        payload = f"t={t};temp={rng.uniform(18, 26):.1f};ph={rng.uniform(6.5, 7.5):.2f}".encode()
        out += PLOG_MARK + struct.pack("<HH", seq, len(payload)) + payload + struct.pack("<I", zlib.crc32(payload))
        truth.append({"seq": seq, "payload": payload.decode()})
    return out, {"format": "plog", "header": {"instrument": inst},
                 "block_layout": "marker A5 5A, u16 seq, u16 length, payload, u32 crc32(payload)",
                 "records": truth}


# ---------------- parc: index + RLE + XOR (VAULT-like) ----------------

PARC_MAGIC = b"PARC"
PARC_KEY = 0x5C


def rle_pairs(data: bytes) -> bytes:
    out = []
    i = 0
    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i] and j - i < 255:
            j += 1
        out += [j - i, data[i]]
        i = j
    return bytes(out)


def make_parc(rng: random.Random, k: int) -> tuple[bytes, dict]:
    files = []
    for i in range(rng.randint(2, 5)):
        name = f"{rng.choice(['MAP', 'LVL', 'TXT', 'SND'])}{k}{i}.DAT"
        body = (f"entry {i} of archive {k}\n" + "=" * rng.randint(10, 40) + "\n"
                + " " * rng.randint(5, 30) + "end\n").encode()
        files.append((name, body))
    table_len = len(files) * 24      # str 12 name (xor), u32 offset, u32 size, u32 raw_size
    pos = 6 + table_len
    table, blobs, truth = b"", b"", []
    for name, body in files:
        packed = rle_pairs(body)
        xname = bytes(c ^ PARC_KEY for c in name.encode().ljust(12, b"\x00"))
        table += xname + struct.pack("<III", pos, len(packed), len(body))
        blobs += packed
        truth.append({"name": name, "offset": pos, "size": len(packed), "raw_size": len(body),
                      "content": body.decode()})
        pos += len(packed)
    return PARC_MAGIC + struct.pack("<H", len(files)) + table + blobs, {
        "format": "parc", "header": {"entry_count": len(files)},
        "notes": "names XOR 0x5C; blobs RLE as (count, byte) pairs", "entries": truth}


MAKERS = {"prec": make_prec, "plog": make_plog, "parc": make_parc}
EXT = {"prec": ".rec", "plog": ".log", "parc": ".arc"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=Path("practice"))
    ap.add_argument("--count", type=int, default=5, help="files per format")
    ap.add_argument("--seed", type=int, default=98)
    ap.add_argument("--damaged", action="store_true", help="also write damaged copies via tools/corrupt.py")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    for fmt, make in MAKERS.items():
        d = a.out / fmt
        (d / "answers").mkdir(parents=True, exist_ok=True)
        for k in range(a.count):
            data, truth = make(rng, k)
            name = f"{fmt}_{k}{EXT[fmt]}"
            (d / name).write_bytes(data)
            (d / "answers" / f"{name}.json").write_text(json.dumps(truth, indent=2) + "\n")
        if a.damaged:
            import corrupt
            dd = a.out / f"{fmt}_damaged"
            dd.mkdir(exist_ok=True)
            manifest = []
            for f in sorted(d.glob(f"*{EXT[fmt]}")):
                for tag, (blob, info) in corrupt.variants(f.read_bytes(), rng).items():
                    (dd / f"{f.name}.{tag}").write_bytes(blob)
                    manifest.append({"file": f"{f.name}.{tag}", "source": f.name, **info})
            (dd / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote practice files to {a.out}/ (prec, plog, parc"
          + (" + damaged copies" if a.damaged else "") + "). NOT the real formats.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
