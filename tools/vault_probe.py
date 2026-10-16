#!/usr/bin/env python3
"""Test the VAULT layout hypotheses on every sample. OWNER: Khushi.

    python3 tools/vault_probe.py samples/vault/
    python3 tools/vault_probe.py real-samples/vault/ --by Khushi --log

Analysis only, standard library only, clean samples only (*.damaged-* skipped). Each
hypothesis goes through evidence.checker.evaluate (the all-samples rule); rejected ones are
printed and logged too. What it checks, in order:

  1. magic and entry count        bytes shared by every file; u16 vs u8 count at 4
  2. index table                  entry size E: the first blob offset == header + count * E
  3. offset / size fields         blobs chain end to start and the last one ends at EOF
  4. RLE                          which recovery.rle variant round-trips every blob exactly,
                                  and which entry field equals the decoded size
  5. XOR names                    the single-byte key that gives clean NUL-padded names,
                                  per sample: one key for all, or one per file?
  6. the rival "header + N fixed records" layout that tools/survey.py proposes
"""
from __future__ import annotations

import argparse
import shlex
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from salvage.evidence import checker  # noqa: E402
from salvage.recovery import rle, xor  # noqa: E402
from survey import common_prefix, load  # noqa: E402

COUNT_AT = 4
ENTRY_SIZES = range(8, 65)
NAME_LENGTHS = (8, 12, 13, 16, 20, 32)


def u(data: bytes, off: int, fmt: str = "<I") -> int | None:
    n = struct.calcsize(fmt)
    return struct.unpack_from(fmt, data, off)[0] if 0 <= off and off + n <= len(data) else None


def probe(paths: list[Path], fmt: str = "vault", by: str = "", include_damaged: bool = False) -> int:
    files = [(n, d) for n, d in load(paths) if include_damaged or ".damaged-" not in Path(n).name]
    if len(files) < checker.MIN_SAMPLES:
        print(f"need at least {checker.MIN_SAMPLES} clean samples (all-samples rule), got {len(files)}")
        return 1
    blobs = [d for _, d in files]
    logs: list[tuple[str, str, str]] = []
    probe.logs = logs

    def record(hyp: str, test, extra: str = "") -> checker.Verdict:
        v = checker.evaluate(fmt, hyp, blobs, test, log=False)
        bad = [Path(files[i][0]).name for i in v.counterexamples]
        ev = f"held on {v.held}/{v.total} samples" + ("" if not bad else "; fails on every sample"
                                                      if len(bad) == v.total else f"; fails on {', '.join(bad)}")
        logs.append((hyp, ev + (f"; {extra}" if extra else ""), v.outcome))
        print(f"  [{v.outcome:>8}] {hyp}  ({ev})")
        return v

    print(f"{len(files)} samples: " + ", ".join(f"{Path(n).name} ({len(d)} B)" for n, d in files))

    # 1. magic + count
    print("\n== 1. magic and entry count")
    magic = common_prefix(blobs)[:COUNT_AT]
    record(f"bytes 0-{len(magic) - 1} are the magic {magic.hex(' ').upper()} ({magic.decode('latin-1')!r})",
           lambda b: b.startswith(magic))
    hi_zero = record(f"byte {COUNT_AT + 1} is always 0 (high byte of a u16 count, or padding after a u8 count)",
                     lambda b: b[COUNT_AT + 1] == 0).accepted
    header = COUNT_AT + 2

    def count(b: bytes) -> int:
        return u(b, COUNT_AT, "<H")

    # 2. entry size: the first blob starts right after count * E bytes of table
    print("\n== 2. index table: entry size E with an offset field pointing at header + count * E")
    found = []
    for E in ENTRY_SIZES:
        for at in range(0, E - 3):
            if all(u(b, header + at) == header + count(b) * E for b in blobs):
                found.append((E, at))
    for E, at in found:
        print(f"  entry size {E}: u32 at +{at} of entry 0 == {header} + count * {E} in every sample")
    if len(found) != 1:
        print(f"  {len(found)} candidates; look at the hex view")
        return 0 if found else 1
    E, off_at = found[0]
    record(f"u16le at {COUNT_AT} is the entry count; index table of {E}-byte entries starts at {header}",
           lambda b: u(b, header + off_at) == header + count(b) * E,
           "the first entry's offset points at the first byte after count entries"
           + ("; a u8 count fits too (byte 5 is always 0)" if hi_zero else ""))

    def entries(b: bytes) -> list[bytes]:
        return [b[header + i * E:header + (i + 1) * E] for i in range(count(b))]

    # 3. offset + size: blobs chain end to start, last one ends at EOF
    print("\n== 3. offset and size fields")
    size_at = None
    for at in range(0, E - 3, 4):
        if at == off_at:
            continue
        def chain(b, at=at):
            es = entries(b)
            offs = [u(e, off_at) for e in es]
            ends = [o + u(e, at) for o, e in zip(offs, es)]
            return offs[1:] == ends[:-1] and ends[-1] == len(b)
        v = checker.evaluate(fmt, "", blobs, chain, log=False)
        if v.accepted and size_at is None:
            size_at = at
            sizes = {u(e, at) for b in blobs for e in entries(b)}
            record(f"u32 at entry+{off_at} is the blob offset and u32 at entry+{at} the stored blob size",
                   chain, "blobs chain end to start and the last ends at EOF"
                   + (f"; NOTE: the size is {sizes.pop()} in every entry, so it is checked only by the "
                      "chain, never by varying" if len(sizes) == 1 else ""))
    if size_at is None:
        print("  no size field makes the blobs chain to EOF")
        return 0
    def tiles(b):
        spans = sorted((u(e, off_at), u(e, off_at) + u(e, size_at)) for e in entries(b))
        starts = [header + count(b) * E] + [end for _, end in spans]
        return [s for s, _ in spans] == starts[:-1] and starts[-1] == len(b)
    record("blobs tile the data area exactly: sorted by offset they start at the table end, touch "
           "end to start, and the last ends at EOF (no gaps, no overlaps)", tiles)

    def blob_list(b: bytes) -> list[bytes]:
        return [b[u(e, off_at):u(e, off_at) + u(e, size_at)] for e in entries(b)]

    # 4. RLE variant and decoded size
    print("\n== 4. RLE: which variant round-trips every blob, and which field is the decoded size")
    variant = None
    for name, (dec, enc) in rle.VARIANTS.items():
        def rt(b, dec=dec, enc=enc):
            try:
                return all(enc(dec(x)) == x for x in blob_list(b))
            except rle.RLEError:
                return False
        if record(f"blobs are RLE '{name}': encode(decode(blob)) == blob for every blob", rt).accepted:
            variant = variant or name
    raw_at = None
    if variant:
        dec = rle.VARIANTS[variant][0]
        for at in range(0, E - 3, 4):
            if at in (off_at, size_at):
                continue
            def size_ok(b, at=at):
                return all(len(dec(x)) == u(e, at) for x, e in zip(blob_list(b), entries(b)))
            if checker.evaluate(fmt, "", blobs, size_ok, log=False).accepted:
                raw_at = at
                record(f"u32 at entry+{at} is the decoded ('{variant}') size of the blob", size_ok)
                break
    else:
        print("  no variant round-trips: add the candidate to recovery/rle.py")

    # 5. XOR names
    print("\n== 5. XOR-obfuscated names")
    name_len = min(off_at, size_at, raw_at if raw_at is not None else E)
    names = [[e[:name_len] for e in entries(b)] for b in blobs]
    keys = [xor.best_fixed_string_key(ns)[0] for ns in names]
    print(f"  best single-byte key per sample (bytes 0-{name_len - 1} of each entry): "
          + ", ".join("none" if k is None else f"0x{k:02X}" for k in keys))
    k0 = keys[0]
    if k0 is not None:
        text = ", ".join(repr(xor.xor(n, bytes([k0])).rstrip(b"\0").decode("latin-1")) for n in names[0][:3])
        record(f"entry bytes 0-{name_len - 1} are a name XORed with the single-byte key 0x{k0:02X}, "
               "NUL-padded", lambda b: all(xor.is_clean_fixed_string(xor.xor(n, bytes([k0])))
                                          for n in [e[:name_len] for e in entries(b)]),
               f"e.g. {text}")
        record("the XOR key is the same in every file (not one key per file)",
               lambda b: xor.best_fixed_string_key([e[:name_len] for e in entries(b)])[0] == k0)
        record(f"the XOR key is per entry (each name needs a different key)",
               lambda b: len({xor.best_fixed_string_key([e[:name_len]])[0] for e in entries(b)}) > 1)
        record("blob contents are XORed too (decoded blobs are not printable text as stored)",
               lambda b: variant is not None and not all(
                   all(32 <= c < 127 or c in (9, 10, 13) for c in rle.VARIANTS[variant][0](x)) for x in blob_list(b)))

    # 6. the rival fixed-record layout
    print("\n== 6. rival layout from tools/survey.py")
    R = (len(blobs[0]) - header) // max(count(blobs[0]), 1)
    if not record(f"file size == {header} + count * {R} (true, but see the next row)",
                  lambda b: len(b) == header + count(b) * R).accepted:
        R = None
    if R:
        packed = sorted({u(e, size_at) for b in blobs for e in entries(b)})
        logs.append((f"{R}-byte fixed records are the real structure (what tools/survey.py proposes)",
                 f"the size fits only because every blob packs to {packed} bytes; the u32 at entry+{off_at} "
                 f"points exactly at the end of a {E}-byte-entry table in every sample, so the first count*{E} "
                 "bytes are an index and the rest are blobs", "rejected"))
        print(f"  [rejected] {R}-byte records are the real structure (the offsets prove an index + blobs)")

    print(f"\n== log commands ({len(logs)} hypotheses; run them, or pass --log)")
    for hyp, ev, outcome in logs:
        print("python3 tools/log.py " + " ".join(shlex.quote(x) for x in (fmt, hyp, ev, outcome))
              + (f" --by {shlex.quote(by)}" if by else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--format", default="vault")
    ap.add_argument("--by", default="")
    ap.add_argument("--all", action="store_true", help="include *.damaged-* files")
    ap.add_argument("--log", action="store_true", help="also append every hypothesis to FIELD-LOG.md")
    a = ap.parse_args(argv)
    rc = probe(a.paths, a.format, a.by, a.all)
    if a.log and rc == 0:
        from salvage.evidence import ledger
        for hyp, ev, outcome in probe.logs:
            ledger.log(a.format, hyp, ev, outcome, a.by, force=True)
        print(f"logged {len(probe.logs)} rows to {ledger.LOG_PATH}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
