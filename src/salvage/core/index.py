"""Generic reader for index-table formats. OWNER: Preetika (core). Used by Khushi (VAULT, game archive).

Many archives start with a table of entries, each pointing at a blob elsewhere in the file:

    [header] [entry 0: offset, size, name...] [entry 1] ... [blob] [blob] ...

Describe one entry with FieldSpecs and call read_index():

    entry = [FieldSpec("name", "str", 12), FieldSpec("offset", "u32"), FieldSpec("size", "u32")]
    scan = read_index(data, start=16, count=header["count"].value, entry=entry)
    for e in scan.entries:          # e.ok: the entry is consistent with the file
        blob = e.blob               # b"" when not ok
    result.damage += scan.damage

What it checks, and what it reports:
- table runs past the end of the file      -> TRUNCATED, missing entries listed
- blob starts inside the header or table   -> BAD_OFFSET, entry not ok
- blob starts or ends past the end of file -> TRUNCATED when it continues the chain of blobs
                                              before it (file cut off), else BAD_OFFSET
- two blobs overlap                        -> INDEX_OVERLAP, both entries kept but UNVERIFIED
                                              (we cannot tell which one is right)
- gaps between blobs                       -> listed in scan.gaps (slack, not damage)

Offset/size fields are VERIFIED only when every entry is consistent and the blobs tile the
data area exactly (no gaps, no overlaps, nothing left over); otherwise they stay UNVERIFIED.
Blob CONTENT is never verified here: the caller does that (CRC, RLE round-trip, XOR key).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .model import DamageCause, DamageEntry, Field, FieldStatus
from .reader import ByteReader, OutOfBounds
from .spec import FieldSpec, decode_fields

ALIGN_SLACK = 16   # padding allowed between consecutive blobs when deciding 'truncated'


@dataclass
class IndexEntry:
    index: int
    fields: dict[str, Field]
    offset: int                  # absolute offset of the blob in the file
    size: int
    ok: bool = True
    note: str = ""
    blob: bytes = b""

    @property
    def end(self) -> int:
        return self.offset + self.size


@dataclass
class IndexScan:
    entries: list[IndexEntry] = field(default_factory=list)
    damage: list[DamageEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    gaps: list[tuple[int, int]] = field(default_factory=list)
    table_end: int = 0           # first byte after the table
    tiles_exactly: bool = False  # blobs cover the data area with no gaps or overlaps

    @property
    def good(self) -> list[IndexEntry]:
        return [e for e in self.entries if e.ok]


def read_index(data: bytes, start: int, count: int, entry: list[FieldSpec], endian: str = "little",
               offset_field: str = "offset", size_field: str = "size", size_is_end: bool = False,
               relative_to: int | str = 0, data_start: int | None = None, max_entries: int = 100_000) -> IndexScan:
    """Read `count` entries starting at `start` and check them against the file.

    relative_to: added to each stored offset. An int, or "table_end" when offsets count
                 from the first byte after the table.
    size_is_end: the size field actually stores the blob's end offset.
    data_start:  first byte blobs may use (default: end of the table).
    """
    scan = IndexScan()
    r = ByteReader(data, endian)
    r.seek(start)
    raw: list[tuple[int, dict[str, Field]]] = []
    if count < 0 or count > max_entries:
        scan.warnings.append(f"implausible entry count {count}; reading until the table stops making sense")
        count = max_entries
    for i in range(count):
        at = r.pos
        try:
            raw.append((i, decode_fields(r, entry)))
        except OutOfBounds:
            scan.damage.append(DamageEntry(at, len(data), DamageCause.TRUNCATED,
                                           f"index table cut off at entry {i} of {count}",
                                           [f"entry {j}" for j in range(i, count)]))
            break
    scan.table_end = r.pos if len(raw) == count else len(data)
    base = scan.table_end if relative_to == "table_end" else int(relative_to)
    floor = scan.table_end if data_start is None else data_start

    for i, fs in raw:
        off = fs[offset_field].value + base
        size = fs[size_field].value - (fs[offset_field].value if size_is_end else 0)
        scan.entries.append(IndexEntry(i, fs, off, size))

    # bounds. A blob past the end of the file means truncation only if it continues the chain
    # of blobs before it (the file was simply cut off); a blob far beyond that is a bad offset.
    inb = [e for e in scan.entries if e.size >= 0 and floor <= e.offset and e.end <= len(data)]
    chain = max((e.end for e in inb), default=floor)
    cut: set[int] = set()
    for e in sorted((e for e in scan.entries if e.size >= 0 and e.offset >= floor and e.end > len(data)),
                    key=lambda e: e.offset):
        if e.offset <= chain + ALIGN_SLACK:
            cut.add(e.index)
            chain = max(chain, e.end)
    for e in scan.entries:
        if e.size < 0:
            _bad(scan, e, DamageCause.BAD_LENGTH, f"negative size {e.size}")
        elif e.offset < floor:
            _bad(scan, e, DamageCause.BAD_OFFSET, f"blob offset {e.offset} points inside the header/table "
                                                  f"(data starts at {floor})")
        elif e.end > len(data):
            if e.index in cut:
                what = "file ends inside this blob" if e.offset < len(data) else "file ends before this blob"
                _bad(scan, e, DamageCause.TRUNCATED, what, start=min(e.offset, len(data)), end=len(data))
            else:
                _bad(scan, e, DamageCause.BAD_OFFSET, f"blob {e.offset}..{e.end} lies outside the file "
                                                      f"({len(data)} bytes)", start=len(data), end=len(data))

    # overlaps and gaps among the entries that are still in bounds
    inside = sorted((e for e in scan.entries if e.ok), key=lambda e: (e.offset, e.size))
    cursor, prev = floor, None
    overlaps = False
    for e in inside:
        if prev is not None and e.offset == prev.offset and e.size == prev.size:
            scan.warnings.append(f"entries {prev.index} and {e.index} point at the same blob (shared data?)")
            continue
        if prev is not None and e.offset < prev.end:
            overlaps = True
            for x in (prev, e):
                x.note = (x.note + "; " if x.note else "") + f"overlaps entry {e.index if x is prev else prev.index}"
            scan.damage.append(DamageEntry(e.offset, min(prev.end, e.end), DamageCause.INDEX_OVERLAP,
                                           f"entries {prev.index} and {e.index} overlap",
                                           [f"entry {prev.index}", f"entry {e.index}"]))
        elif e.offset > cursor:
            scan.gaps.append((cursor, e.offset))
        cursor = max(cursor, e.end)
        prev = e if prev is None or e.end >= prev.end else prev
    if cursor < len(data) and inside:
        scan.gaps.append((cursor, len(data)))

    scan.tiles_exactly = (not scan.damage and not scan.gaps and not overlaps
                          and len(scan.entries) == count and bool(scan.entries))
    status = FieldStatus.VERIFIED if scan.tiles_exactly else FieldStatus.UNVERIFIED
    for e in scan.entries:
        for f in e.fields.values():
            f.status = FieldStatus.LOST if not e.ok else status
            if f.status == FieldStatus.VERIFIED:
                f.note = "index entries tile the data area exactly"
        if e.ok:
            e.blob = data[e.offset:e.end]
    return scan


def _bad(scan: IndexScan, e: IndexEntry, cause: DamageCause, note: str,
         start: int | None = None, end: int | None = None) -> None:
    e.ok, e.note = False, note
    s = e.offset if start is None else start
    t = (e.end if end is None else end)
    s, t = max(0, min(s, t)), max(0, max(s, t))
    scan.damage.append(DamageEntry(s, t, cause, f"entry {e.index}: {note}", [f"entry {e.index}"]))


def index_structure_score(data: bytes, start: int, count: int, entry: list[FieldSpec], **kw) -> float:
    """For Decoder.structure_score(): 1.0 when the entries tile the rest of the file exactly."""
    if count <= 0:
        return 0.0
    try:
        scan = read_index(data, start, count, entry, **kw)
    except Exception:
        return 0.0
    return 1.0 if scan.tiles_exactly else 0.0
