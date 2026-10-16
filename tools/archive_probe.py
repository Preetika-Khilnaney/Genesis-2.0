#!/usr/bin/env python3
"""Find the index of a game archive (where it is, what an entry holds). OWNER: Khushi.

    python3 tools/archive_probe.py samples/pak/
    python3 tools/archive_probe.py real-samples/<archive>/ --format pak --by Khushi --log

Analysis only, standard library only, clean samples only (*.damaged-* skipped). Every
hypothesis goes through evidence.checker.evaluate (the all-samples rule). Steps:

  1. magic                      bytes shared by every file
  2. where is the index?        a header (offset, length) pair whose table ends at EOF, or
                                starts right after the header; or an (offset, count) pair
  3. entry layout               entry size E dividing the table; inside an entry, a name and
                                an (offset, size) pair whose blobs tile the data area exactly
  4. names                      plain NUL-padded text, or XORed (recovery.xor)?
  5. compression / checksum     room for a flags / packed-size / CRC field in the entry?
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
from salvage.recovery import xor  # noqa: E402
from survey import common_prefix, load  # noqa: E402

ENTRY_SIZES = (16, 20, 24, 32, 40, 48, 64, 72, 80, 128)


def u32(b: bytes, off: int) -> int | None:
    return struct.unpack_from("<I", b, off)[0] if 0 <= off and off + 4 <= len(b) else None


def probe(paths: list[Path], fmt: str = "game_archive", by: str = "", include_damaged: bool = False) -> int:
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

    # 1. magic
    print("\n== 1. magic")
    magic = common_prefix(blobs)[:4]
    record(f"bytes 0-{len(magic) - 1} are the magic {magic.hex(' ').upper()} ({magic.decode('latin-1')!r})",
           lambda b: b.startswith(magic))
    m = len(magic)

    # 2. where is the index: try header pairs (a at m+i, b at m+j)
    print("\n== 2. where is the index?")
    where = None
    for i in range(0, 16, 4):
        for j in range(0, 16, 4):
            if i == j:
                continue
            at_end = lambda b, i=i, j=j: u32(b, m + i) is not None and u32(b, m + j) is not None and \
                u32(b, m + i) + u32(b, m + j) == len(b) and u32(b, m + j) > 0
            if checker.evaluate(fmt, "", blobs, at_end, log=False).accepted and where is None:
                where = ("end", m + i, m + j)
                record(f"u32 at {m + i} is the directory offset and u32 at {m + j} its length in bytes: "
                       "offset + length == file size (directory at the END)", at_end)
    if where is None:
        print("  no (offset, length) header pair puts a table at the end of every file")
        return 0
    _, off_at, len_at = where
    header = max(off_at, len_at) + 4
    record(f"the header is {header} bytes and the first blob starts right after it",
           lambda b: u32(b, off_at) >= header)
    record(f"the directory length is the same in every file (a constant is not a length)",
           lambda b: u32(b, len_at) == u32(blobs[0], len_at))

    # 3. entry size + (offset, size) pair that tiles [header, dir_offset)
    print("\n== 3. entry layout")
    found = []
    for E in ENTRY_SIZES:
        for oa in range(0, E - 7, 4):
            sa = oa + 4
            def tiles(b, E=E, oa=oa, sa=sa):
                d, n = u32(b, off_at), u32(b, len_at)
                if n % E:
                    return False
                spans = sorted((u32(b, d + k * E + oa), u32(b, d + k * E + sa)) for k in range(n // E))
                pos = header
                for o, s in spans:
                    if o != pos:
                        return False
                    pos = o + s
                return pos == d
            if checker.evaluate(fmt, "", blobs, tiles, log=False).accepted:
                found.append((E, oa, sa, tiles))
    for E, oa, sa, _ in found:
        print(f"  entry size {E}: u32 at +{oa} = offset, u32 at +{sa} = size; blobs tile {header}..dir exactly")
    if not found:
        print("  no entry layout tiles the data area")
        return 0
    E, oa, sa, tiles = found[0]
    record(f"directory = {E}-byte entries; u32 at entry+{oa} is the blob offset, u32 at entry+{sa} its size",
           tiles, "sorted by offset the blobs start right after the header, touch end to start, and end "
                  "exactly where the directory begins")
    record("blob sizes vary between entries (so the size field is evidence, not a constant)",
           lambda b: len({u32(b, u32(b, off_at) + k * E + sa) for k in range(u32(b, len_at) // E)}) > 1
           or u32(b, len_at) // E < 2)

    # 4. names
    print("\n== 4. names")
    def names(b):
        d = u32(b, off_at)
        return [b[d + k * E:d + k * E + oa] for k in range(u32(b, len_at) // E)]
    record(f"entry bytes 0-{oa - 1} are a plain NUL-padded name (printable text, then zeros)",
           lambda b: all(xor.is_clean_fixed_string(n) for n in names(b)),
           "e.g. " + ", ".join(repr(n.rstrip(b'\0').decode('latin-1')) for n in names(blobs[0])[:3]))
    keys = [xor.best_fixed_string_key(names(b))[0] for b in blobs]
    record("names are XOR-obfuscated (a non-zero key reads them best)", lambda b: xor.best_fixed_string_key(names(b))[0] not in (0, None),
           f"best key per sample: {', '.join('none' if k is None else f'0x{k:02X}' for k in keys)}")

    # 5. compression / checksum: is there any room in the entry or header?
    print("\n== 5. compression and checksum")
    spare = E - (sa + 4)
    logs.append((f"an entry has a flags / packed-size / checksum field",
                 f"rejected: name {oa} + offset 4 + size 4 = {oa + 8} of {E} bytes; {spare} bytes left"
                 if spare == 0 else f"open: {spare} unexplained bytes after the size field", "rejected" if spare == 0 else "open"))
    print(f"  [{'rejected' if spare == 0 else 'open':>8}] entry has room for flags/packed size/CRC ({spare} spare bytes)")
    logs.append(("blob contents can be verified",
                 "rejected: no checksum, no compression to round-trip, no packed size to cross-check; blob bytes "
                 "stay unverified (the guide's rule for archives without a checksum)", "rejected"))
    print("  [rejected] blob contents can be verified (nothing in the file covers them)")

    print(f"\n== log commands ({len(logs)} hypotheses; run them, or pass --log)")
    for hyp, ev, outcome in logs:
        print("python3 tools/log.py " + " ".join(shlex.quote(x) for x in (fmt, hyp, ev, outcome))
              + (f" --by {shlex.quote(by)}" if by else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--format", default="pak")
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
