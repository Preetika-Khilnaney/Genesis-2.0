"""Generic index-table reader: bounds, truncation, overlaps, gaps, exact tiling."""
import struct

from salvage.core.index import index_structure_score, read_index
from salvage.core.model import DamageCause, FieldStatus
from salvage.core.spec import FieldSpec

ENTRY = [FieldSpec("name", "str", 8), FieldSpec("offset", "u32"), FieldSpec("size", "u32")]
HEADER = 4                       # b"ARC" + count
BLOBS = [b"alpha", b"bravo-bravo", b"c"]


def build(blobs=BLOBS, entries=None):
    table_len = len(blobs) * 16
    pos = HEADER + table_len
    if entries is None:
        entries = []
        for i, b in enumerate(blobs):
            entries.append((f"f{i}", pos, len(b)))
            pos += len(b)
    table = b"".join(n.encode().ljust(8, b"\0") + struct.pack("<II", o, s) for n, o, s in entries)
    return b"ARC" + bytes([len(entries)]) + table + b"".join(blobs)


def test_clean_archive_tiles_exactly_and_is_verified():
    data = build()
    scan = read_index(data, HEADER, 3, ENTRY)
    assert [e.blob for e in scan.entries] == BLOBS
    assert scan.tiles_exactly and not scan.damage and not scan.gaps
    assert all(f.status == FieldStatus.VERIFIED for e in scan.entries for f in e.fields.values())
    assert index_structure_score(data, HEADER, 3, ENTRY) == 1.0


def test_truncated_file_marks_last_blob_truncated():
    data = build()[:-3]                       # drops blob 2 (1 byte) and the last 2 bytes of blob 1
    scan = read_index(data, HEADER, 3, ENTRY)
    bad = [e for e in scan.entries if not e.ok]
    assert {e.index for e in bad} == {1, 2}
    assert all(d.cause == DamageCause.TRUNCATED for d in scan.damage)
    assert scan.entries[0].blob == b"alpha" and scan.entries[0].fields["offset"].status == FieldStatus.UNVERIFIED
    assert all(f.status == FieldStatus.LOST for f in scan.entries[2].fields.values())


def test_table_itself_cut_off():
    data = build()[:HEADER + 20]              # one full entry + part of the next
    scan = read_index(data, HEADER, 3, ENTRY)
    assert scan.damage[0].cause == DamageCause.TRUNCATED
    assert scan.damage[0].affected == ["entry 1", "entry 2"]


def test_offset_into_header_is_bad_offset():
    start = HEADER + 48
    data = build(entries=[("f0", 2, 5), ("f1", start + 5, 11), ("f2", start + 16, 1)])
    scan = read_index(data, HEADER, 3, ENTRY)
    assert not scan.entries[0].ok and scan.entries[0].blob == b""
    assert scan.damage[0].cause == DamageCause.BAD_OFFSET
    assert scan.entries[1].blob == b"bravo-bravo"


def test_wild_offset_in_the_middle_is_bad_offset_not_truncation():
    start = HEADER + 48
    data = build(entries=[("f0", start, 5), ("f1", 0xFFFF00, 11), ("f2", start + 16, 1)])
    scan = read_index(data, HEADER, 3, ENTRY)
    assert not scan.entries[1].ok
    assert scan.damage[0].cause == DamageCause.BAD_OFFSET
    assert scan.entries[2].blob == b"c"


def test_overlap_reported_and_fields_unverified():
    start = HEADER + 48
    data = build(entries=[("f0", start, 8), ("f1", start + 5, 11), ("f2", start + 16, 1)])
    scan = read_index(data, HEADER, 3, ENTRY)
    ov = [d for d in scan.damage if d.cause == DamageCause.INDEX_OVERLAP]
    assert len(ov) == 1 and ov[0].start == start + 5 and ov[0].end == start + 8
    assert not scan.tiles_exactly
    assert all(f.status == FieldStatus.UNVERIFIED for e in scan.entries for f in e.fields.values())
    assert index_structure_score(data, HEADER, 3, ENTRY) == 0.0


def test_gap_is_slack_not_damage():
    blobs = b"alpha" + b"XX" + b"bravo-bravo"
    table = b"".join(n.ljust(8, b"\0") + struct.pack("<II", o, s)
                     for n, o, s in [(b"f0", HEADER + 32, 5), (b"f1", HEADER + 32 + 7, 11)])
    data = b"ARC\x02" + table + blobs
    scan = read_index(data, HEADER, 2, ENTRY)
    assert not scan.damage and scan.gaps == [(HEADER + 37, HEADER + 39)]
    assert [e.blob for e in scan.entries] == [b"alpha", b"bravo-bravo"]


def test_relative_offsets():
    blobs = b"alpha" + b"bravo"
    table = b"".join(n.ljust(8, b"\0") + struct.pack("<II", o, s) for n, o, s in [(b"a", 0, 5), (b"b", 5, 5)])
    data = b"ARC\x02" + table + blobs
    scan = read_index(data, HEADER, 2, ENTRY, relative_to="table_end")
    assert [e.blob for e in scan.entries] == [b"alpha", b"bravo"] and scan.tiles_exactly
