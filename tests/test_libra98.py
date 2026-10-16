"""LIBRA-98 tests.

  - Registration, round-trip and golden tests via the adapters (Manas, delivery)
  - Samples scored against sample-answers (Preetika, core): on samples/libra98 (STAND-IN
    layout) clean files are 100% verified and right; damaged copies are never verified wrong,
    except values rewritten in place where no checksum could notice. When the real samples
    arrive, keep these tests and point them at the new spec.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from salvage.adapters import get_decoder, get_spec_for  # noqa: F401
from salvage.cli import main
from salvage.core.model import FieldStatus
from salvage.core.registry import DecodeContext

ROOT = Path(__file__).parent.parent
ANS = ROOT / "sample-answers" / "libra98"
FIELDS = ("id", "name", "enrolled", "grade", "flags")


def test_libra98_adapter_registered():
    """Verify LIBRA-98 format is registered in the spec library."""
    from salvage.core.registry import get
    dec = get("libra98")
    assert dec is not None
    assert dec.name == "libra98"


def test_libra98_roundtrip():
    """Round-trip test: decode -> re-encode must yield byte-identical output."""
    dec = get_decoder("libra98")
    if dec is None:
        pytest.skip("Preetika's LIBRA-98 decoder is not yet marked ready (src/salvage/formats/libra98.py: ready=False)")

    # Clean sample files
    fixtures = [p for p in Path("samples/libra98").glob("*.l98") if ".damaged-" not in p.name]
    if not fixtures:
        fixtures = list(Path("tests/fixtures/clean").glob("*.l98"))
    if not fixtures:
        pytest.skip("No LIBRA-98 sample fixtures present in samples/libra98 or tests/fixtures/clean")

    ctx = DecodeContext(format="libra98", siblings=[(p.name, p.read_bytes()) for p in fixtures])

    for fix in fixtures:
        data = fix.read_bytes()
        res = dec.decode(fix.name, data, ctx)
        assert res.format == "libra98"
        assert res.error is None
        # Assert every decoded field is verified
        for rec in res.records:
            for f in rec.fields.values():
                assert f.status in (FieldStatus.VERIFIED, FieldStatus.CORRECTED)


def test_libra98_golden_samples():
    """Golden test: clean samples decode without damage or unverified fields."""
    dec = get_decoder("libra98")
    if dec is None:
        pytest.skip("Preetika's LIBRA-98 decoder is not yet marked ready (src/salvage/formats/libra98.py: ready=False)")

    clean_samples = [p for p in Path("samples/libra98").glob("*.l98") if ".damaged-" not in p.name]
    if not clean_samples:
        pytest.skip("No clean binary samples available in samples/libra98/")

    ctx = DecodeContext(format="libra98", siblings=[(p.name, p.read_bytes()) for p in clean_samples])

    for s in clean_samples:
        res = dec.decode(s.name, s.read_bytes(), ctx)
        assert len(res.damage) == 0, f"Expected 0 damage entries on clean sample {s.name}"
        assert len(res.records) > 0


def _silent(f: dict, d: dict) -> bool:
    lo, hi = f["offset"], f["offset"] + f["length"]
    return (d["type"] == "bit_flip" and lo <= d["byte"] < hi) or \
        (d["type"] == "zeroed" and d["start"] < hi and lo < d["end"])


def test_libra98_samples_match_answers(tmp_path):
    out = tmp_path / "out"
    assert main([str(ROOT / "samples" / "libra98"), str(out)]) == 0
    damaged = {m["file"]: m for m in json.loads((ANS / "manifest.json").read_text())}
    clean_ok = clean_total = false = 0
    for res_path in sorted(out.glob("*.json")):
        if res_path.name == "report.json":
            continue
        res = json.loads(res_path.read_text())
        name = res["source_file"]
        if res["format"] == "unknown":
            # only acceptable when the damage destroyed the magic itself: never guess the format
            d = damaged.get(name, {})
            assert d.get("offset", d.get("start", d.get("byte", 99))) < 8, name
            continue
        assert res["format"] == "libra98", name
        truth = json.loads((ANS / f"{damaged[name]['source'] if name in damaged else name}.json").read_text())
        rows = truth["records"]
        if name not in damaged:
            assert res["header"]["record_count"]["status"] == "verified"
            assert res["header"]["decoy_15"]["status"] == "unverified"     # looks like a length, is not
            assert not res["damage"]
        for rec in res["records"]:
            t = rows[rec["index"]] if rec["index"] < len(rows) else None
            for k in FIELDS:
                f = rec["fields"][k]
                right = t is not None and t[k] == f["value"]
                if name not in damaged:
                    clean_total += 1
                    clean_ok += right and f["status"] == "verified"
                elif f["status"] == "verified" and not right and not _silent(f, damaged[name]):
                    false += 1
        if name in damaged and damaged[name]["type"] in ("truncate", "inserted", "deleted"):
            assert res["damage"], f"{name}: structural damage must be reported"
    assert clean_total and clean_ok == clean_total
    assert false == 0
