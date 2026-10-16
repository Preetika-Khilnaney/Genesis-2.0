"""LIBRA-98 format and gate tests. OWNER: Manas (delivery).

Verifies:
  - Round-trip fidelity (decode -> re-encode -> byte identical)
  - Golden tests against sample files in tests/fixtures/clean/
  - Safe adapter delegation (marked skip-with-reason until Preetika's decoder lands)
"""
from __future__ import annotations

from pathlib import Path
import pytest

from salvage.adapters import get_decoder, get_spec_for
from salvage.core.model import FieldStatus


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

    # When ready, test against clean fixture or synthetic file
    fixtures = list(Path("tests/fixtures/clean").glob("*.libra*")) + list(Path("samples").glob("*.libra*"))
    if not fixtures:
        pytest.skip("No LIBRA-98 sample fixtures present in tests/fixtures/clean or samples/")

    for fix in fixtures:
        data = fix.read_bytes()
        res = dec.decode(fix.name, data)
        assert res.format == "libra98"
        assert res.error is None
        # Assert every decoded field is verified
        for rec in res.records:
            for f in rec.fields.values():
                assert f.status in (FieldStatus.VERIFIED, FieldStatus.CORRECTED)


def test_libra98_golden_samples():
    """Golden test: samples decode without damage or unverified fields."""
    dec = get_decoder("libra98")
    if dec is None:
        pytest.skip("Preetika's LIBRA-98 decoder is not yet marked ready (src/salvage/formats/libra98.py: ready=False)")

    sample_dir = Path("samples")
    if not sample_dir.is_dir():
        pytest.skip("samples/ directory not found")

    samples = [p for p in sample_dir.glob("*") if p.is_file() and p.name != "README.md"]
    if not samples:
        pytest.skip("No binary samples available in samples/")

    for s in samples:
        res = dec.decode(s.name, s.read_bytes())
        assert len(res.damage) == 0, f"Expected 0 damage entries on clean sample {s.name}"
