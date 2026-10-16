#!/usr/bin/env python3
"""Find the block layout of a marker/length/payload/checksum format. OWNER: Khushi.

    python3 tools/lablog_probe.py samples/lablog/
    python3 tools/lablog_probe.py real-samples/lablog/ --by Khushi

Analysis only, standard library only. Clean samples only: files named *.damaged-* are
skipped (use --all to include them). Everything it reports must hold on EVERY sample:

  1. header      first 32 bytes, with the bytes identical in every sample marked
  2. markers     2- and 4-byte patterns occurring >= 3 times in every file, ranked
                 (--min-hits; small files may hold only a handful of blocks)
  3. length      for the top marker candidates: which integer after the marker equals
                 (distance to the next block) - constant in every block of every sample
  4. checksum    recovery.crc.guess_algorithm on the blocks, over each candidate range
  5. log         ready-to-run tools/log.py commands, accepted AND rejected, with numbers

The verdicts come from evidence.checker.evaluate (the all-samples rule), not from here.
"""
from __future__ import annotations

import argparse
import shlex
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from salvage.evidence import checker  # noqa: E402
from salvage.recovery.crc import ALGORITHMS, guess_algorithm  # noqa: E402
from survey import load  # noqa: E402

MIN_HITS = 3            # a marker must occur at least this often in every file
LEN_SCAN = 6            # length field may start up to this many bytes after the marker
INT_TYPES = [(n, e, c) for n, c in ((2, "H"), (4, "I"), (1, "B")) for e in ("le", "be")
             if not (n == 1 and e == "be")]


def uint(data: bytes, off: int, size: int, end: str) -> int | None:
    if off < 0 or off + size > len(data):
        return None
    return struct.unpack(("<" if end == "le" else ">") + {1: "B", 2: "H", 4: "I"}[size],
                         data[off:off + size])[0]


def tname(size: int, end: str) -> str:
    return "u8" if size == 1 else f"u{size * 8}{end}"


# --- 1. header --------------------------------------------------------------------

def common_prefix(blobs: list[bytes]) -> bytes:
    n = min(len(b) for b in blobs)
    i = 0
    while i < n and len({b[i] for b in blobs}) == 1:
        i += 1
    return blobs[0][:i]


def header_view(blobs: list[bytes], n: int = 32) -> list[str]:
    rows = []
    for off in range(0, n, 16):
        cells = []
        for i in range(off, off + 16):
            vals = {b[i] for b in blobs if i < len(b)}
            cells.append(f"{blobs[0][i]:02x}" if len(vals) == 1 and i < len(blobs[0]) else "..")
        rows.append(f"{off:08x}  {' '.join(cells)}")
    return rows


# --- 2. markers -------------------------------------------------------------------

def marker_candidates(blobs: list[bytes], skip: int, min_hits: int = MIN_HITS) -> list[tuple[bytes, int]]:
    """(pattern, fewest hits in any file) for patterns seen >= min_hits times in EVERY file,
    most frequent first. Bytes before `skip` (the magic) are ignored."""
    found: dict[bytes, int] = {}
    for width in (2, 4):
        per_file = []
        for b in blobs:
            c = Counter(b[i:i + width] for i in range(skip, len(b) - width + 1))
            per_file.append(c)
        for pat in per_file[0]:
            hits = min(c.get(pat, 0) for c in per_file)
            if hits >= min_hits:
                found[pat] = hits
    return sorted(found.items(), key=lambda t: (-t[1], -len(t[0]), t[0]))


# --- 3. length --------------------------------------------------------------------

@dataclass
class Layout:
    marker: bytes
    len_at: int          # length field offset, counted from the end of the marker
    size: int            # length field width in bytes
    end: str             # "le" | "be"
    const: int           # block size = stored length + const
    start: int           # offset of the first block (= header size)

    @property
    def len_type(self) -> str:
        return tname(self.size, self.end)

    def walk(self, data: bytes) -> list[tuple[int, int]] | None:
        """[(block_start, block_end)] if the chain lands exactly on a marker or on EOF every
        time, starting at the first marker; None as soon as it does not."""
        pos = data.find(self.marker, self.start)
        if pos != self.start:
            return None
        blocks = []
        while pos < len(data):
            if data[pos:pos + len(self.marker)] != self.marker:
                return None
            v = uint(data, pos + len(self.marker) + self.len_at, self.size, self.end)
            if v is None:
                return None
            end = pos + v + self.const
            if end <= pos or end > len(data):
                return None
            blocks.append((pos, end))
            pos = end
        return blocks


def length_layouts(blobs: list[bytes], marker: bytes) -> list[Layout]:
    """Every (position, type, constant) that walks EVERY sample from its first marker to EOF.
    The constant is taken from the first block of the first sample, then must hold everywhere."""
    first = blobs[0]
    start = first.find(marker)
    if start < 0 or any(b.find(marker) != start for b in blobs):
        return []
    nxt = first.find(marker, start + 1)
    out = []
    for at in range(LEN_SCAN + 1):
        for size, end, _ in INT_TYPES:
            v = uint(first, start + len(marker) + at, size, end)
            if v is None:
                continue
            dists = {nxt - start} if nxt > 0 else set()
            # a chance marker inside the first payload would give the wrong distance: also
            # try every later marker as "the next block" (the walk on all samples decides)
            i = nxt
            while i > 0:
                dists.add(i - start)
                i = first.find(marker, i + 1)
            dists.add(len(first) - start)
            for d in sorted(dists):        # smallest constant first: the nearest next block
                lay = Layout(marker, at, size, end, d - v, start)
                if lay.const > 0 and all(lay.walk(b) for b in blobs) and _varies(blobs, lay):
                    out.append(lay)
                    break
    return sorted(out, key=lambda l: (l.len_at + l.size, -l.size, l.const))


def _varies(blobs: list[bytes], lay: Layout) -> bool:
    """A "length" that is the same in every block proves nothing: with equal-size blocks any
    constant byte walks the file. Only a value that changes, and moves the next marker with
    it, is evidence of a length field."""
    vals = {uint(b, s + len(lay.marker) + lay.len_at, lay.size, lay.end) for b in blobs for s, _ in lay.walk(b)}
    return len(vals) > 1


def block_table(data: bytes, lay: Layout, limit: int = 12) -> list[str]:
    rows = ["  marker at  next at  distance  " + "  ".join(f"{tname(s, e):>6}" for s, e, _ in INT_TYPES)
            + f"   distance - {lay.len_type}@+{lay.len_at}"]
    for s, e in (lay.walk(data) or [])[:limit]:
        vals = [uint(data, s + len(lay.marker) + lay.len_at, sz, en) for sz, en, _ in INT_TYPES]
        v = uint(data, s + len(lay.marker) + lay.len_at, lay.size, lay.end)
        nxt = "EOF" if e == len(data) else str(e)
        rows.append(f"  {s:>9}  {nxt:>7}  {e - s:>8}  " + "  ".join(f"{x:>6}" for x in vals)
                    + f"   {e - s - v:>3}")
    return rows


# --- 4. checksum ------------------------------------------------------------------

def ranges(lay: Layout) -> dict[str, int]:
    """Candidate checksum coverage: name -> offset from block start where coverage begins."""
    m = len(lay.marker)
    named = {"payload": m + lay.len_at + lay.size, "length+payload": m + lay.len_at}
    if lay.len_at:
        named["fields+length+payload"] = m
    named["marker+...+payload"] = 0
    return named


def checksum_trials(blobs: list[bytes], lay: Layout) -> list[dict]:
    """One trial per (stored width/endianness, coverage). The stored checksum is the last
    `width` bytes of each block. guess_algorithm decides which algorithms match ALL blocks."""
    blocks = [(b, s, e) for b in blobs for s, e in lay.walk(b)]
    trials = []
    for size, end, _ in INT_TYPES:
        for rname, rstart in ranges(lay).items():
            pairs = []
            for b, s, e in blocks:
                if e - size < s + rstart:
                    pairs = []
                    break
                pairs.append((b[s + rstart:e - size], uint(b, e - size, size, end)))
            if not pairs:
                continue
            held = {name: sum(fn(p) == st for p, st in pairs) for name, fn in ALGORITHMS.items()}
            trials.append({"stored": tname(size, end), "range": rname, "blocks": len(pairs),
                           "match": guess_algorithm(pairs), "held": held, "size": size,
                           "end": end, "rstart": rstart})
    return trials


# --- 5. log -----------------------------------------------------------------------

def log_cmd(fmt: str, hyp: str, ev: str, outcome: str, by: str) -> str:
    return "python3 tools/log.py " + " ".join(shlex.quote(x) for x in (fmt, hyp, ev, outcome)) \
        + (f" --by {shlex.quote(by)}" if by else "")


def verdict(fmt: str, hyp: str, blobs: list[bytes], test) -> checker.Verdict:
    return checker.evaluate(fmt, hyp, blobs, test, log=False)


def probe(paths: list[Path], fmt: str, by: str, include_damaged: bool, min_hits: int = MIN_HITS) -> int:
    files = [(n, d) for n, d in load(paths) if include_damaged or ".damaged-" not in Path(n).name]
    if len(files) < 2:
        print(f"need at least 2 clean samples (all-samples rule), got {len(files)}")
        return 1
    blobs = [d for _, d in files]
    logs: list[tuple[str, str, str]] = []

    def record(hyp: str, test, extra: str = "") -> checker.Verdict:
        v = verdict(fmt, hyp, blobs, test)
        bad = [Path(files[i][0]).name for i in v.counterexamples]
        ev = f"held on {v.held}/{v.total} samples" + ("" if not bad else "; fails on every sample"
                                                      if len(bad) == v.total else f"; fails on {', '.join(bad)}")             + (f"; {extra}" if extra else "")
        logs.append((hyp, ev, v.outcome))
        return v

    print(f"{len(files)} samples: " + ", ".join(f"{Path(n).name} ({len(d)} B)" for n, d in files))

    # 1. header
    print("\n== 1. header: first 32 bytes, '..' = differs between samples")
    print("\n".join(header_view(blobs)))
    prefix = common_prefix(blobs)
    print(f"common prefix: {prefix!r} ({len(prefix)} bytes; the magic is the part before the first block)")

    # 2. markers
    print(f"\n== 2. patterns seen >= {min_hits} times in every file (fewest hits in any file)")
    cands = marker_candidates(blobs, 0, min_hits)
    for pat, hits in cands[:12]:
        print(f"  {pat.hex(' '):<12} {pat!r:<20} {hits}")
    if not cands:
        print("  none")
        return 0

    # 3. length. Every candidate is tried: text fragments ("temp=") repeat as often as a real
    # marker, so frequency alone cannot pick it; only a length field that walks every file can.
    print("\n== 3. block length: a field after the marker that walks every sample to EOF")
    layouts: list[Layout] = []
    for pat, hits in cands:
        found = length_layouts(blobs, pat)
        for l in found:
            print(f"  marker {pat.hex(' '):<12} length {l.len_type:<6} at marker+{l.len_at}   block = length + {l.const}")
        layouts += found
    print(f"  ({len(cands)} marker candidates tried, {len(layouts)} layout(s) walk every sample)")
    if not layouts:
        print("no marker candidate is explained by a length field; check the hex view "
              "(one damaged file breaks the walk, so leave damaged copies out)")
        return 0

    # 4. checksum, under EVERY surviving layout. Several length readings can walk the files by
    # accident (a u16be straddling a zero byte reads like a u8); a wrong one puts the payload
    # boundaries in the wrong place, so only the true layout lets a checksum match every block.
    print("\n== 4. checksum: guess_algorithm over every block of every sample, per layout")
    per_layout: list[tuple[Layout, list[dict]]] = []
    for lay in layouts:
        trials = checksum_trials(blobs, lay)
        per_layout.append((lay, trials))
        print(f"\n  layout: marker {lay.marker.hex(' ')}, length {lay.len_type} at marker+{lay.len_at}")
        print(f"    {'stored as':<9}  {'covers':<22}  {'blocks':>6}  matches all     best other")
        for t in trials:
            others = sorted(((h, n) for n, h in t["held"].items() if n not in t["match"]), reverse=True)
            best = f"{others[0][1]} {others[0][0]}/{t['blocks']}" if others else "-"
            print(f"    {t['stored']:<9}  {t['range']:<22}  {t['blocks']:>6}  {', '.join(t['match']) or '-':<14}  {best}")
    confirmed = [(l, t) for l, trials in per_layout for t in trials if t["match"]]
    with_crc = list({id(l): l for l, _ in confirmed}.values())

    if len(with_crc) == 1:
        lay = with_crc[0]
    else:
        print(f"\n{len(with_crc)} layouts have a matching checksum: "
              + ("ambiguous, look at the hex view" if with_crc else
                 "add the variant to recovery/crc.py, or run CRC RevEng at build time"))
        lay = layouts[0]
    m = lay.marker
    counts = [len(lay.walk(b)) for b in blobs]
    print(f"\nchosen: marker {m.hex(' ')}, first block at {lay.start}, length {lay.len_type} at marker+{lay.len_at},"
          f" block = length + {lay.const}")
    print(f"block table, {Path(files[0][0]).name}:")
    print("\n".join(block_table(blobs[0], lay)))

    # --- hypotheses, in the order a reader would check them ---
    # The magic stops where the first block starts: identical first-block bytes are data.
    magic = prefix[:lay.start]
    if magic:
        text = magic.decode("latin-1") if all(32 <= c < 127 for c in magic) else ""
        record(f"bytes 0-{len(magic) - 1} are the magic {magic.hex(' ').upper()}" + (f' ("{text}")' if text else ""),
               lambda b: b.startswith(magic))
    stray = [sum(1 for i in range(len(b)) if b.startswith(m, i)) - c for b, c in zip(blobs, counts)]
    record(f"{m.hex(' ').upper()} is the block marker; first block at offset {lay.start}",
           lambda b: lay.walk(b) is not None,
           f"{sum(counts)} blocks chain marker to marker to EOF; marker bytes inside payloads "
           f"{sum(stray)} times (resync must still check the CRC)")
    hdr_at = len(magic)
    if lay.start > hdr_at:
        print(f"\nheader bytes {hdr_at}-{lay.start - 1} after the magic, per sample: "
              + ", ".join(b[hdr_at:lay.start].hex(' ') for b in blobs))
        gap = lay.start - hdr_at
        for size, end, _ in INT_TYPES:
            if size > gap or (size == 1 and gap > 1):    # a u8 inside a wider gap adds nothing
                continue
            t = f"{tname(size, end)} at {hdr_at}"
            record(f"header {t} is the block count", lambda b, s=size, e=end: uint(b, hdr_at, s, e) == len(lay.walk(b)))
            record(f"header {t} is the file size", lambda b, s=size, e=end: uint(b, hdr_at, s, e) == len(b))
            record(f"header {t} is the same in every file",
                   lambda b, s=size, e=end: uint(b, hdr_at, s, e) == uint(blobs[0], hdr_at, s, e))
        vals = sorted({b[hdr_at:lay.start].hex(' ') for b in blobs})
        logs.append((f"header bytes {hdr_at}-{lay.start - 1}: meaning unknown",
                     f"values {', '.join(vals)}; not block count, file size or constant; keep unverified", "open"))

    for l, _ in per_layout:
        if l is not lay:
            logs.append((f"{l.len_type} at marker+{l.len_at} is the block length (block = length + {l.const})",
                         f"walks all {sum(counts)} blocks too, but no checksum algorithm matches every block "
                         f"under it, so its payload boundaries are wrong", "rejected"))
    record(f"{lay.len_type} at marker+{lay.len_at} is the payload length (block = length + {lay.const})",
           lambda b: lay.walk(b) is not None and lay in with_crc,
           f"{sum(counts)} blocks walk to EOF exactly and the checksum confirms the payload boundaries")

    covered_to = 0                         # fields between marker and length: a counter?
    for at in range(lay.len_at):
        if at < covered_to:                # already explained by a wider counter
            continue
        for size, end, _ in sorted(INT_TYPES, key=lambda t: -t[0]):
            if at + size > lay.len_at:
                continue
            def seq_ok(b, at=at, size=size, end=end):
                vals = [uint(b, s + len(m) + at, size, end) for s, _ in lay.walk(b)]
                return vals == list(range(vals[0], vals[0] + len(vals)))
            v = verdict(fmt, "", blobs, seq_ok)
            if v.held:
                record(f"{tname(size, end)} at marker+{at} is a block sequence number counting up by 1", seq_ok)
            if v.accepted:
                record(f"block sequence number ({tname(size, end)} at marker+{at}) starts at 0",
                       lambda b, at=at, size=size, end=end: uint(b, lay.start + len(m) + at, size, end) == 0)
                covered_to = at + size
                break

    trials = next(t for l, t in per_layout if l is lay)
    for stored in dict.fromkeys(t["stored"] for t in trials):
        bad = [t for t in trials if t["stored"] == stored and not t["match"]]
        if not bad or bad[0]["size"] == 1:
            continue
        h, name, rng = max((h, n, t["range"]) for t in bad for n, h in t["held"].items())
        best = f"best: {name} {h}/{bad[0]['blocks']} over {rng}" if h else             f"every algorithm 0/{bad[0]['blocks']}"
        logs.append((f"checksum stored as {stored} in the last {bad[0]['size']} bytes of the block",
                     f"no algorithm in recovery.crc ({', '.join(ALGORITHMS)}) matches every block over "
                     f"{' / '.join(t['range'] for t in bad)} ({best})", "rejected"))
    # payload shape, for the decoder: printable text? key=value pairs with the same keys?
    head = len(m) + lay.len_at + lay.size            # payload starts right after the length field

    def payloads(b):                                 # stored length = block size - const
        return [b[s + head:s + head + (e - s - lay.const)] for s, e in lay.walk(b)]
    if lay in with_crc and record("payload is printable ASCII text in every block",
                                  lambda b: all(all(32 <= c < 127 for c in p) for p in payloads(b))).accepted:
        def keys(p):
            pairs = [kv.split(b"=", 1) for kv in p.split(b";")]
            return tuple(k.decode() for k, *_ in pairs) if all(len(kv) == 2 for kv in pairs) else None
        first = keys(payloads(blobs[0])[0])
        if first:
            record(f"payload is ';'-separated key=value pairs with keys {', '.join(first)} in that order",
                   lambda b: all(keys(p) == first for p in payloads(b)))

    for t in (t for l, t in confirmed if l is lay):
        for name in t["match"]:
            def ok(b, t=t, fn=ALGORITHMS[name]):
                return all(fn(b[s + t["rstart"]:e - t["size"]]) == uint(b, e - t["size"], t["size"], t["end"])
                           for s, e in lay.walk(b))
            others = ", ".join(f"{n} {h}/{t['blocks']}" for n, h in sorted(t["held"].items()) if n != name)
            record(f"checksum = {name}, stored {t['stored']} in the last {t['size']} bytes of each block, "
                   f"over the {t['range']}", ok,
                   f"all {t['blocks']} blocks match (guess_algorithm); other algorithms: {others}")

    # 5. log
    print(f"\n== 5. log commands ({len(logs)} hypotheses; run them, or pass --log)")
    for hyp, ev, outcome in logs:
        print(log_cmd(fmt, hyp, ev, outcome, by))
    probe.logs = logs  # for --log and tests
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--format", default="lablog")
    ap.add_argument("--by", default="")
    ap.add_argument("--min-hits", type=int, default=MIN_HITS)
    ap.add_argument("--all", action="store_true", help="include *.damaged-* files")
    ap.add_argument("--log", action="store_true", help="also append every hypothesis to FIELD-LOG.md")
    a = ap.parse_args(argv)
    rc = probe(a.paths, a.format, a.by, a.all, a.min_hits)
    if a.log and rc == 0:
        from salvage.evidence import ledger
        for hyp, ev, outcome in getattr(probe, "logs", []):
            ledger.log(a.format, hyp, ev, outcome, a.by, force=True)
        print(f"logged {len(getattr(probe, 'logs', []))} rows to {ledger.LOG_PATH}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
