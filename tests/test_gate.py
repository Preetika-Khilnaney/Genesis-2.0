"""core.gate: which decoded record fields may be called verified."""
import struct

from salvage.core.gate import gate_records, layout_fits
from salvage.core.model import FieldStatus
from salvage.core.simple import decode_simple
from salvage.core.spec import FieldSpec, FormatSpec

SPEC = FormatSpec(name="g", magic=b"GT", header=[FieldSpec("magic", "bytes", 2), FieldSpec("count", "u16")],
                  record=[FieldSpec("id", "u16"), FieldSpec("v", "u8")], record_count_field="count")
CHECKS = {"id": lambda v, prev: prev is None or v == prev["id"] + 1, "v": lambda v, prev: v < 100}


def make(n, start=1):
    return b"GT" + struct.pack("<H", n) + b"".join(struct.pack("<HB", start + i, 10 + i) for i in range(n))


SAMPLES = [make(3), make(5), make(2)]


def run(data):
    res = decode_simple(SPEC, "x", data)
    summary = gate_records(res, data, SPEC, [data] + SAMPLES, CHECKS)
    return res, summary


def statuses(res):
    return [{f.status for f in r.fields.values()} for r in res.records]


def test_clean_file_all_verified():
    res, s = run(make(4))
    assert s.layout_proven and s.file_fits
    assert statuses(res) == [{FieldStatus.VERIFIED}] * 4


def test_one_bad_record_in_place_only_that_record_unverified():
    data = bytearray(make(4))
    data[4 + 3 * 1 + 2] = 200                        # record 1, v = 200 fails its check
    res, _ = run(bytes(data))
    assert statuses(res) == [{FieldStatus.VERIFIED}, {FieldStatus.UNVERIFIED},
                             {FieldStatus.VERIFIED}, {FieldStatus.VERIFIED}]


def test_deleted_byte_trusts_only_records_well_before_the_damage():
    data = make(5)
    data = data[:4 + 3 * 3 + 1] + data[4 + 3 * 3 + 2:]    # delete one byte inside record 3
    res, s = run(data)
    assert not s.file_fits and s.first_bad_record is not None
    st = statuses(res)
    assert st[0] == {FieldStatus.VERIFIED} and st[1] == {FieldStatus.VERIFIED}
    assert all(x == {FieldStatus.UNVERIFIED} for x in st[3:])
    assert any(d.cause.value in ("bad_length", "truncated") for d in res.damage)


def test_unproven_layout_verifies_nothing():
    data = make(3)
    res = decode_simple(SPEC, "x", data)
    gate_records(res, data, SPEC, [data], CHECKS)      # one sample: not enough evidence
    assert all(f.status == FieldStatus.UNVERIFIED for r in res.records for f in r.fields.values())


def test_layout_fits():
    assert layout_fits(SPEC, make(3)) and not layout_fits(SPEC, make(3)[:-1])
