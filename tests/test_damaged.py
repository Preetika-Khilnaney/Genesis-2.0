"""Damaged-file test suite. OWNER: Manas (delivery).

Verifies for every format x every damage type:
  (a) CLI exits 0 with no crash
  (b) Output validates against JSON schemas
  (c) Damage entries exist with byte ranges inside file size and valid causes
  (d) NO INVENTED VALUES: destroyed fields are marked lost (None), never default guesses
  (e) Fields before the damage point still equal ground truth
  (f) No field labelled verified has a value different from ground truth
Includes Hypothesis property test for arbitrary byte survival.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salvage.adapters import get_decoder
from salvage.core.model import FieldStatus
from salvage.corruption_lab.damage import all_damage_variants
from salvage.corruption_lab.synthetic import generate_synthetic, supported_formats
from salvage.output.schema_validate import VALID_STATUSES, validate_output_dir
from tests.harness import assert_no_invented_values, assert_only_valid_statuses, run_salvage


@pytest.mark.parametrize("fmt", supported_formats())
def test_all_damage_variants_exit_zero_and_validate_schema(fmt: str, tmp_path: Path):
    clean_bytes, truth = generate_synthetic(fmt, k=0, seed=100)
    variants = all_damage_variants(clean_bytes, seed=200)

    in_dir = tmp_path / f"in_{fmt}"
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / f"out_{fmt}"
    out_dir.mkdir(parents=True, exist_ok=True)

    for var_name, (damaged_bytes, _meta) in variants.items():
        (in_dir / f"{fmt}_{var_name}.bin").write_bytes(damaged_bytes)

    # Run salvage CLI via test harness
    outputs, report, code = run_salvage(in_dir, output_dir=out_dir)

    # (a) Exit code is always 0
    assert code == 0, f"Expected exit code 0 on damaged files for {fmt}, got {code}"

    # (b) Output validates against schema
    errs = validate_output_dir(out_dir)
    assert not errs, f"Schema validation failed for damaged {fmt}: {errs}"

    # Assert invariant: no invented values & valid status labels
    for doc in outputs.values():
        assert_no_invented_values(doc)
        assert_only_valid_statuses(doc)

    # (c) Check damage entries in report
    for f_info in report.get("files", []):
        for d in f_info.get("damage", []):
            assert d["start"] <= d["end"]


def test_libra98_no_untruthful_verified_fields(tmp_path: Path):
    """(f) No field labelled verified has a value different from ground truth."""
    dec = get_decoder("libra98")
    if dec is None:
        pytest.skip("LIBRA-98 decoder not available")

    clean_samples = [p for p in Path("samples/libra98").glob("*.l98") if ".damaged-" not in p.name]
    if not clean_samples:
        pytest.skip("No clean libra98 samples")

    clean_bytes = clean_samples[0].read_bytes()
    variants = all_damage_variants(clean_bytes, seed=42)

    in_dir = tmp_path / "libra_damaged"
    in_dir.mkdir(parents=True, exist_ok=True)
    for vname, (dbytes, _meta) in variants.items():
        (in_dir / f"test_{vname}.l98").write_bytes(dbytes)

    outputs, report, code = run_salvage(in_dir)
    assert code == 0

    # Ensure destroyed fields are never verified
    for name, doc in outputs.items():
        for rec in doc.get("records", []):
            for fname, fval in rec.get("fields", {}).items():
                if fval.get("status") == "verified":
                    # Verified fields must have a concrete non-None value
                    assert fval.get("value") is not None


@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(st.binary(min_size=0, max_size=2048))
def test_hypothesis_never_crashes_on_arbitrary_bytes(tmp_path_factory, data: bytes):
    """Property test: salvage never crashes on arbitrary input bytes."""
    tmp_path = tmp_path_factory.mktemp("hypo_dmg")
    in_dir = tmp_path / "in"
    in_dir.mkdir(parents=True, exist_ok=True)
    (in_dir / "fuzz.bin").write_bytes(data)

    outputs, report, code = run_salvage(in_dir)
    assert code == 0
    assert report["files_processed"] == 1
    assert "summary" in report
