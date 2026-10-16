#!/usr/bin/env python3
"""Survey a set of samples of ONE format and propose a layout. OWNER: Preetika.

    python3 tools/survey.py <folder of one format's files>
    python3 tools/survey.py <folder> --log --by Preetika    # also writes FIELD-LOG rows

It only reports facts that hold on EVERY sample (the same all-samples rule as
evidence/checker.py), so anything it prints is a hypothesis worth checking, not a
guess from one file:

  1. magic       bytes identical at the start of every file
  2. constants   other header bytes identical in every file
  3. sizes       integers equal to the file size, or to the bytes after them
  4. layout      an integer N with  header + N * record_size == file size  in every file
  5. records     per-column facts inside the records (constant, counting up, text, dates)
  6. dates       header integers that decode as plausible dates in every file

It ends with a draft FormatSpec to paste into formats/<name>.py. Edit the names and
check each field in the hex view before trusting it.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

HEADER_SCAN = 128          # how far into the file to look for header fields
SIZES = (1, 2, 4)
ENDIANS = (("le", "<"), ("be", ">"))
CODES = {1: "B", 2: "H", 4: "I"}


SKIP_DIRS = {"answers", "out"}
SKIP_NAMES = {"README.md", "manifest.json"}


def load(paths: list[Path]) -> list[tuple[str, bytes]]:
    """Sample files only: skips hidden files, README/manifest, *.json and answers/ folders."""
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files += sorted(q for q in p.rglob("*") if q.is_file()
                            and not SKIP_DIRS & set(q.relative_to(p).parts[:-1]))
        else:
            files.append(p)
    return [(str(f), f.read_bytes()) for f in files
            if not f.name.startswith(".") and f.name not in SKIP_NAMES and f.suffix != ".json"]


def uint(data: bytes, off: int, size: int, e: str) -> int | None:
    if off + size > len(data):
        return None
    return struct.unpack(e + CODES[size], data[off:off + size])[0]


def _bits(t: str) -> int:
    return int("".join(c for c in t if c.isdigit()))


def type_name(size: int, end: str) -> str:
    return "u8" if size == 1 else f"u{size * 8}{end}"


# ---------- 1-2: magic and constants ----------

def common_prefix(blobs: list[bytes]) -> bytes:
    n = min(len(b) for b in blobs)
    i = 0
    while i < n and len({b[i] for b in blobs}) == 1:
        i += 1
    return blobs[0][:i]


def constant_runs(blobs: list[bytes], start: int, stop: int) -> list[tuple[int, bytes]]:
    n = min(stop, min(len(b) for b in blobs))
    runs, i = [], start
    while i < n:
        if len({b[i] for b in blobs}) == 1:
            j = i
            while j < n and len({b[j] for b in blobs}) == 1:
                j += 1
            runs.append((i, blobs[0][i:j]))
            i = j
        else:
            i += 1
    return runs


# ---------- 3-4: size fields and header + N * record layout ----------

def size_fields(blobs: list[bytes]) -> list[tuple[int, str, str]]:
    out = []
    for off in range(HEADER_SCAN):
        for size in (2, 4):
            for end, e in ENDIANS:
                vals = [uint(b, off, size, e) for b in blobs]
                if None in vals:
                    continue
                if all(v == len(b) for v, b in zip(vals, blobs)):
                    out.append((off, type_name(size, end), "file size"))
                elif all(v == len(b) - off - size for v, b in zip(vals, blobs)):
                    out.append((off, type_name(size, end), "bytes after this field"))
    return out


MIN_SUPPORT = 0.6   # share of files a layout must explain (the rest are reported as likely damaged)


def majority_prefix(blobs: list[bytes], share: float = MIN_SUPPORT) -> bytes:
    """Longest prefix whose every byte is the same in at least `share` of the files."""
    out = bytearray()
    for i in range(max(len(b) for b in blobs)):
        vals = [b[i] for b in blobs if len(b) > i]
        top = max(set(vals), key=vals.count)
        if vals.count(top) < share * len(blobs):
            break
        out.append(top)
    return bytes(out)


def count_layouts(blobs: list[bytes], min_support: float = MIN_SUPPORT) -> list[dict]:
    """Integers N where header + N * record == len(file), with one header size and one record
    size shared by the files. A layout must explain at least min_support of the files (and at
    least 2 with different N); files it does not explain are listed as likely damaged."""
    found = []
    need = max(2, -(-int(min_support * 100) * len(blobs) // 100))
    for off in range(HEADER_SCAN):
        for size in SIZES:
            for end, e in ENDIANS:
                if size == 1 and end == "be":
                    continue
                vals = [uint(b, off, size, e) for b in blobs]
                points = sorted({(v, len(b)) for v, b in zip(vals, blobs) if v is not None})
                if len({v for v, _ in points}) < 2:
                    continue
                proposals = set()
                for i, (v1, n1) in enumerate(points):
                    for v2, n2 in points[i + 1:]:
                        if v1 == v2 or (n1 - n2) % (v1 - v2):
                            continue
                        rec = (n1 - n2) // (v1 - v2)
                        hdr = n1 - v1 * rec
                        if rec > 0 and hdr >= off + size:
                            proposals.add((hdr, rec))
                best = None
                for hdr, rec in proposals:
                    fit = [i for i, (v, b) in enumerate(zip(vals, blobs)) if v is not None and hdr + v * rec == len(b)]
                    if len({vals[i] for i in fit}) >= 2 and (best is None or len(fit) > len(best[2])):
                        best = (hdr, rec, fit)
                if best and len(best[2]) >= need:
                    hdr, rec, fit = best
                    found.append({"offset": off, "type": type_name(size, end), "header": hdr, "record": rec,
                                  "endian": "little" if end == "le" else "big",
                                  "counts": [vals[i] for i in fit], "fit": fit})
    # most files explained first, then wider fields, little-endian, earlier offsets
    found.sort(key=lambda f: (-len(f["fit"]), -_bits(f["type"]), f["endian"] != "little", f["offset"]))
    return found


# ---------- 5: columns inside the records ----------

def printable(bs: bytes) -> bool:
    core = bs.rstrip(b"\x00 ")
    return bool(core) and all(32 <= c < 127 for c in core)


REC_SHARE = 0.9   # a column property must hold in this share of records (damaged ones may not)


def _share(flags) -> float:
    flags = list(flags)
    return sum(flags) / len(flags) if flags else 0.0


def _pct(x: float) -> str:
    return "every" if x == 1 else f"{x:.0%} of"


def record_columns(blobs: list[bytes], hdr: int, rec: int, e: str) -> list[str]:
    """Column facts that hold in most records (REC_SHARE) or most files (MIN_SUPPORT), so a
    damaged file in the set cannot hide them. The share is printed with each fact."""
    records = [b[hdr + i * rec: hdr + (i + 1) * rec] for b in blobs for i in range((len(b) - hdr) // rec)]
    if not records:
        return ["(no records)"]
    lines, off = [], 0
    textish = [_share(32 <= r[j] < 127 or r[j] == 0 for r in records) for j in range(rec)]
    while off < rec:
        # text run: printable or NUL padding in most records, real text in some
        j = off
        while j < rec and textish[j] >= REC_SHARE:
            j += 1
        if j - off >= 4 and any(printable(r[off:j]) for r in records):
            sample = next(r[off:j] for r in records if printable(r[off:j])).rstrip(b"\x00 ")
            lines.append(f"  +{off:<4} str  {j - off:<4} text, e.g. {sample.decode('latin-1')!r}")
            off = j
            continue
        done = False
        for size in (4, 2):
            if off + size > rec:
                continue
            vals = [struct.unpack(e + CODES[size], r[off:off + size])[0] for r in records]
            t = f"u{size * 8}"
            per_file = [[struct.unpack(e + CODES[size], b[hdr + i * rec + off: hdr + i * rec + off + size])[0]
                         for i in range((len(b) - hdr) // rec)] for b in blobs]
            multi = [p for p in per_file if len(p) > 1]
            seq = _share(all(y - x == 1 for x, y in zip(p, p[1:])) for p in multi)
            if multi and seq >= MIN_SUPPORT:
                starts = sorted({p[0] for p in multi if all(y - x == 1 for x, y in zip(p, p[1:]))})
                lines.append(f"  +{off:<4} {t:<4} counts up by 1 in {_pct(seq)} files (id / sequence), starts at {starts}")
                off += size
                done = True
                break
            unix = _share(_unix_ok(v) for v in vals)
            if size == 4 and len(set(vals)) > 1 and unix >= REC_SHARE:
                ok = [v for v in vals if _unix_ok(v)]
                lines.append(f"  +{off:<4} u32  plausible unix time in {_pct(unix)} records "
                             f"({_unix_str(min(ok))} .. {_unix_str(max(ok))})")
                off += size
                done = True
                break
            dos = _share(_dos_ok(v) for v in vals)
            years = sorted(v >> 9 for v in vals)
            # two small bytes (e.g. a grade and a flag) also "decode" as dates in 1980-81:
            # real date columns are rarely stuck at the very start of the DOS epoch
            if size == 2 and len(set(vals)) > 1 and dos >= REC_SHARE and years[len(years) // 2] >= 2:
                lines.append(f"  +{off:<4} u16  plausible DOS date in {_pct(dos)} records")
                off += size
                done = True
                break
        if done:
            continue
        col = [r[off] for r in records]
        if _mode_share(records, off) >= REC_SHARE:
            j = off
            while j < rec and _mode_share(records, j) >= REC_SHARE:
                j += 1
            const = bytes(_mode(records, k) for k in range(off, j))
            lines.append(f"  +{off:<4} -    {j - off} (nearly) constant byte(s) {const.hex()}")
            off = j
            continue
        vals1 = set(col)
        lines.append(f"  +{off:<4} u8   varies ({len(vals1)} distinct values, {min(vals1)}..{max(vals1)})")
        off += 1
    return lines


def _mode(records: list[bytes], j: int) -> int:
    col = [r[j] for r in records]
    return max(set(col), key=col.count)


def _mode_share(records: list[bytes], j: int) -> float:
    col = [r[j] for r in records]
    return col.count(_mode(records, j)) / len(col)


def _unix_ok(v: int) -> bool:
    try:
        return 1980 <= datetime.fromtimestamp(v, tz=timezone.utc).year <= 2038
    except (OverflowError, OSError, ValueError):
        return False


def _unix_str(v: int) -> str:
    return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d")


def _dos_ok(v: int) -> bool:
    m, d = (v >> 5) & 0xF, v & 0x1F
    return 1 <= m <= 12 and 1 <= d <= 31 and (v >> 9) <= 60


# ---------- 6: dates in the header ----------

def header_dates(blobs: list[bytes], stop: int, e: str, used: set[int]) -> list[str]:
    """Skips bytes already explained (magic, count) and never reports overlapping fields."""
    out, taken = [], set(used)
    for off in range(0, max(0, stop - 3)):
        if taken & set(range(off, off + 4)):
            continue
        vals = [uint(b, off, 4, e) for b in blobs]
        if None not in vals and len(set(vals)) > 1 and all(_unix_ok(v) for v in vals):
            out.append(f"  {off:<5} u32  plausible unix time in every file "
                       f"({_unix_str(min(vals))} .. {_unix_str(max(vals))})")
            taken |= set(range(off, off + 4))
    return out


# ---------- report ----------

def survey(paths: list[Path], name: str, log: bool, by: str) -> int:
    items = load(paths)
    if len(items) < 2:
        print("need at least 2 sample files of the same format")
        return 1
    blobs = [b for _, b in items]
    lengths = sorted(len(b) for b in blobs)
    print(f"{len(items)} files, sizes {lengths[0]}..{lengths[-1]} bytes\n")
    hyps: list[tuple[str, str, str]] = []   # (hypothesis, evidence, outcome)
    n = len(blobs)

    # Sample packs include damaged files. Find what MOST files agree on, then study only the
    # files that fit it, and list the rest as likely damaged.
    rough = majority_prefix(blobs)
    layouts = [f for f in count_layouts(blobs) if f["offset"] >= len(rough)]
    best = layouts[0] if layouts else None
    if best:
        core = best["fit"]
    else:
        core = [i for i, b in enumerate(blobs) if b.startswith(rough)] if rough else list(range(n))
    outliers = [items[i][0] for i in range(n) if i not in core]
    names = [items[i][0] for i in core]
    blobs = [blobs[i] for i in core]
    n_all, n = n, len(blobs)
    if outliers:
        print(f"Using the {n} files that agree; {len(outliers)} look damaged and are left out of the analysis:")
        for o in outliers[:12]:
            print(f"   {o}")
        if len(outliers) > 12:
            print(f"   ... and {len(outliers) - 12} more")
        print()

    magic = common_prefix(blobs)
    print("1. MAGIC")
    if magic:
        print(f"  {magic.hex(' ')}   {magic.decode('latin-1')!r}   ({len(magic)} bytes, same in all {n} agreeing files)")
        hyps.append((f"magic is {magic!r} at offset 0", f"identical in {n}/{n_all} samples", "accepted"))
    else:
        print("  none: the first byte already differs")

    if best:
        # recompute on the agreeing files only (offsets and counts are unchanged)
        best = dict(best, counts=[uint(b, best["offset"], _bits(best["type"]) // 8,
                                       "<" if best["endian"] == "little" else ">") for b in blobs])
    hdr_end = best["header"] if best else HEADER_SCAN
    used = set(range(len(magic)))
    if best:
        used |= set(range(best["offset"], best["offset"] + _bits(best["type"]) // 8))

    print("\n2. OTHER CONSTANT HEADER BYTES" + (f" (header is {hdr_end} bytes)" if best else ""))
    consts = constant_runs(blobs, len(magic), hdr_end)
    for off, bs in consts[:20]:
        print(f"  {off:<5} {bs.hex(' ')}")
    if not consts:
        print("  none")

    print("\n3. SIZE FIELDS")
    sizes = size_fields(blobs)
    for off, t, what in sizes:
        print(f"  {off:<5} {t:<6} == {what} in every file")
        hyps.append((f"{t} at offset {off} is the {what}", f"held on {n}/{n} samples", "accepted"))
    if not sizes:
        print("  none")

    print("\n4. HEADER + N x RECORD LAYOUTS (files explained / all files)")
    for f in layouts[:8]:
        print(f"  count {f['type']:<6} at {f['offset']:<4} header {f['header']:<5} record {f['record']:<5} "
              f"explains {len(f['fit'])}/{n_all}   counts {f['counts'][:6]}{' ...' if len(f['counts']) > 6 else ''}")
    if not layouts:
        print("  none fit every file (block or index format? try core.blocks / an index table)")
    if best:
        hyps.append((f"{best['type']} at offset {best['offset']} is the record count; header {best['header']} bytes, "
                     f"record {best['record']} bytes",
                     f"header + count*record == file size in {len(best['fit']) if 'fit' in best else n}/{n_all} samples; "
                     f"the others look damaged", "accepted"))
        if len(layouts) > 1:
            print("  several fit: the first is a guess; the others are listed so you can rule them out")

    e = "<" if not best or best["endian"] == "little" else ">"
    print("\n5. RECORD COLUMNS" + (f" (record {best['record']} bytes from offset {best['header']})" if best else ""))
    if best:
        for line in record_columns(blobs, best["header"], best["record"], e):
            print(line)
    else:
        print("  skipped: no layout")

    print("\n6. DATES IN THE HEADER")
    dates = header_dates(blobs, hdr_end, e, used)
    print("\n".join(dates) if dates else "  none")

    print("\n7. DRAFT SPEC (rename fields, check each one in tools/hexview.py)")
    print(draft_spec(name, magic, best))

    if log:
        os.environ["SALVAGE_LOG"] = "1"
        from salvage.evidence import ledger
        for h, ev, outcome in hyps:
            ledger.log(name, h, ev + " (tools/survey.py)", outcome, author=by)
        print(f"\nlogged {len(hyps)} hypotheses to FIELD-LOG.md")
    return 0


def draft_spec(name: str, magic: bytes, best: dict | None) -> str:
    head = [f'        FieldSpec("magic", "bytes", {len(magic)}, desc="file signature", evidence="survey: same in all samples"),']\
        if magic else []
    if best:
        pad = best["offset"] - len(magic)
        if pad > 0:
            head.append(f'        FieldSpec("unknown_{len(magic)}", "bytes", {pad}, desc="TODO"),')
        t = best["type"]
        head.append(f'        FieldSpec("record_count", "{t}", desc="number of records", '
                    f'evidence="survey: header + count*{best["record"]} == file size"),')
        size = _bits(t) // 8
        rest = best["header"] - best["offset"] - size
        if rest > 0:
            head.append(f'        FieldSpec("unknown_{best["offset"] + size}", "bytes", {rest}, desc="TODO"),')
    rec = f'        FieldSpec("raw", "bytes", {best["record"]}, desc="TODO: split into fields"),' if best else ""
    endian = best["endian"] if best else "little"
    return "\n".join([
        f'{name.upper()}_SPEC = FormatSpec(',
        f'    name="{name}",',
        f'    magic={magic!r},' if magic else '    magic=None,',
        f'    endian="{endian}",',
        f'    header=[', *head, '    ],',
        f'    record=[', rec, '    ],',
        f'    record_count_field={"record_count" if best else None!r},',
        ')',
    ])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+", type=Path, help="sample files or a folder of them")
    ap.add_argument("--name", help="format name for the draft spec (default: folder name)")
    ap.add_argument("--log", action="store_true", help="write the findings to FIELD-LOG.md")
    ap.add_argument("--by", default="", help="your name, for the log")
    a = ap.parse_args(argv)
    name = a.name or (a.paths[0].name if a.paths[0].is_dir() else a.paths[0].parent.name) or "format"
    return survey(a.paths, name.replace("-", "").lower(), a.log, a.by)


if __name__ == "__main__":
    sys.exit(main())
