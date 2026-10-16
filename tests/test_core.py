"""Core tests: reader, writer, generic decoder. Keep these green before every merge."""
import struct

import pytest

from salvage.core.model import DamageCause, FieldStatus
from salvage.core.reader import ByteReader, ByteWriter, OutOfBounds
from salvage.core.simple import decode_simple
from salvage.core.spec import FieldSpec, FormatSpec, spec_to_markdown

TOY = FormatSpec(
    name="toy", magic=b"TOY1", endian="little",
    header=[FieldSpec("magic", "bytes", 4), FieldSpec("count", "u16")],
    record=[FieldSpec("id", "u16"), FieldSpec("name", "str", 8), FieldSpec("date", "dos_date")],
    record_count_field="count",
)


def make_toy(n: int) -> bytes:
    w = ByteWriter("little")
    w.write("bytes", b"TOY1")
    w.write("u16", n)
    for i in range(n):
        w.write("u16", i + 1)
        w.write("str", f"rec{i}", 8)
        w.write("dos_date", "1998-04-0%d" % (i + 1))
    return w.getvalue()


def test_reader_types_and_endianness():
    r = ByteReader(struct.pack("<HI", 0x1234, 7) + struct.pack(">H", 0x1234))
    assert r.read("u16") == 0x1234
    assert r.read("u32") == 7
    assert r.read("u16be") == 0x1234


def test_reader_bounds():
    r = ByteReader(b"\x01")
    with pytest.raises(OutOfBounds):
        r.read("u32")


def test_round_trip_and_verified():
    res = decode_simple(TOY, "toy.bin", make_toy(3))
    assert len(res.records) == 3
    assert res.records[2].fields["name"].value == "rec2"
    assert res.records[0].fields["date"].value == "1998-04-01"
    assert all(f.status == FieldStatus.VERIFIED for f in res.header.values())
    assert not res.damage


def test_truncation_reports_damage_not_guesses():
    data = make_toy(3)[:-5]
    res = decode_simple(TOY, "toy.bin", data)
    assert len(res.records) == 2
    assert res.damage and res.damage[0].cause == DamageCause.TRUNCATED
    assert res.damage[0].affected == ["record 2"]


def test_spec_markdown_renders():
    md = spec_to_markdown(TOY)
    assert "## toy" in md and "| name | str | 8 |" in md
