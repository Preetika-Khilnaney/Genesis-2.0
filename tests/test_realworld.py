import glob
from pathlib import Path

import pytest

from salvage.core.model import FieldStatus
from salvage.core.registry import DecodeContext
from salvage.formats.realworld import RealWorldDecoder

FILES = sorted(glob.glob(str(Path(__file__).resolve().parents[1] / "samples" / "wks" / "wks_[0-5].wks")))
pytestmark = pytest.mark.skipif(len(FILES) < 3, reason="needs at least 3 wks samples")
DATA = [Path(p).read_bytes() for p in FILES]


def ctx_for(i):
    sib = [(FILES[j], DATA[j]) for j in range(len(DATA)) if j != i]
    return DecodeContext(format="realworld", siblings=sib)


def verified(res):
    return [f for r in res.records for f in r.fields.values() if f.status is FieldStatus.VERIFIED]


def test_clean_file_structure_verified_values_not():
    res = RealWorldDecoder().decode(FILES[0], DATA[0], ctx_for(0))
    assert not res.damage
    assert len(res.records) == 24
    assert res.records[2].fields["text"].value == "Item"
    assert verified(res)
    for r in res.records:
        for name in ("value", "text"):
            if name in r.fields:
                assert r.fields[name].status is not FieldStatus.VERIFIED


def test_every_clean_sample_decodes_without_damage():
    for i in range(len(DATA)):
        res = RealWorldDecoder().decode(FILES[i], DATA[i], ctx_for(i))
        assert not res.damage and res.records[-1].fields["type"].value == 1


def test_truncated_file_is_damage_not_crash_and_nothing_verified():
    res = RealWorldDecoder().decode(FILES[0], DATA[0][:200], ctx_for(0))
    assert any(d.cause.value == "truncated" for d in res.damage)
    assert not verified(res)


def test_bad_length_does_not_crash_and_nothing_verified():
    d = bytearray(DATA[0])
    d[8] = 9  # RANGE length 8 -> 9 shifts every later record
    res = RealWorldDecoder().decode(FILES[0], bytes(d), ctx_for(0))
    assert not verified(res)


def test_without_siblings_nothing_is_verified():
    res = RealWorldDecoder().decode(FILES[0], DATA[0], None)
    assert res.records and not verified(res)


def test_empty_file_does_not_crash():
    res = RealWorldDecoder().decode("empty.wks", b"", None)
    assert res.records == []
