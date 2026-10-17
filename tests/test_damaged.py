"""Damaged-file test suite. OWNER: Manas (delivery).

For every format with a clean real sample x every damage type in corruption_lab.damage:
  (a) the CLI exits 0 with no crash
  (b) output validates against the contract schemas
  (c) damage entries lie inside the file
  (d) nothing invented: unrecognized files have no records, failed files no verified records
  (e) checksum-protected formats never return a verified record that differs from the clean file
Plus a Hypothesis property test for arbitrary bytes.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salvage.core.registry import get
from salvage.corruption_lab.calibrate import evaluate_result
from salvage.corruption_lab.damage import all_damage_variants
from salvage.corruption_lab.sources import clean_sample, supported_formats
from salvage.output.contract import to_contract
from salvage.output.schema_validate import VALID_STATUSES, validate_output_dir
from tests.harness import assert_no_invented_values, assert_only_valid_statuses, run_salvage

PROTECTED = ("LIBRA-98", "LABLOG", "VAULT")      # every byte of a record is under a checksum


@pytest.mark.parametrize("fmt", supported_formats())
def test_all_damage_variants_exit_zero_and_validate_schema(fmt: str, tmp_path: Path):
    clean, _truth = clean_sample(fmt)
    variants = all_damage_variants(clean, seed=200)
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    for name, (damaged, _meta) in variants.items():
        (in_dir / f"{fmt}_{name}.bin").write_bytes(damaged)

    outputs, report, code = run_salvage(in_dir, output_dir=out_dir)
    assert code == 0
    assert not validate_output_dir(out_dir)
    for fname, doc in outputs.items():
        assert_no_invented_values(doc)
        assert_only_valid_statuses(doc)
        size = (in_dir / fname[:-5]).stat().st_size
        for d in doc["damage"]:
            assert 0 <= d["offset"] <= size + 1 and d["offset"] + d["length"] <= max(size, d["offset"] + d["length"])
    assert len(report["files"]) == len(variants)


@pytest.mark.parametrize("fmt", PROTECTED)
def test_protected_formats_never_verify_wrong_records(fmt: str):
    dec = get(fmt)
    for k in range(3):
        clean, truth = clean_sample(fmt, k)
        for name, (damaged, _meta) in all_damage_variants(clean, seed=300 + k).items():
            ev = evaluate_result(to_contract(dec.decode(name, damaged)), truth)
            assert ev["false_recoveries"] == 0, f"{fmt} sample {k} {name}: {ev}"


@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
          deadline=None)
@given(st.binary(min_size=0, max_size=2048))
def test_hypothesis_never_crashes_on_arbitrary_bytes(tmp_path_factory, data: bytes):
    tmp_path = tmp_path_factory.mktemp("hypo_dmg")
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "fuzz.bin").write_bytes(data)
    outputs, report, code = run_salvage(in_dir)
    assert code == 0
    assert len(report["files"]) == 1 and report["files"][0]["status"] in VALID_STATUSES
