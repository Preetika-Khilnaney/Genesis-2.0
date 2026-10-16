"""Tests for report.json generation and atomic writing. OWNER: Manas (delivery).

Verifies:
  - Atomic writing via temp file + replace
  - Summary classification: ok / partial / unknown / failed
  - input_sha256 field inclusion
  - Full schema compliance of generated report.json
"""
from __future__ import annotations

import json
from pathlib import Path

from salvage.core.model import DamageCause, DamageEntry, Field, FieldStatus, FileResult, Record
from salvage.output import report
from salvage.output.schema_validate import validate_output_dir


def test_report_atomic_write(tmp_path: Path):
    res = FileResult(source_file="sample.bin", format="test_fmt", input_sha256="abc123")
    out_file = report.write(tmp_path, [res])

    assert out_file.exists()
    assert out_file.name == "report.json"
    # Ensure no leftover temp files exist
    assert not (tmp_path / "report.json.tmp").exists()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["files_processed"] == 1
    assert data["files"][0]["input_sha256"] == "abc123"


def test_report_summary_classification():
    # 1. OK file
    ok_res = FileResult(
        source_file="clean.bin",
        format="libra98",
        confidence=1.0,
        records=[Record(index=0, fields={"val": Field("val", 10, FieldStatus.VERIFIED)})],
    )

    # 2. Partial file (has damage)
    partial_res = FileResult(
        source_file="damaged.bin",
        format="libra98",
        confidence=0.8,
        damage=[DamageEntry(start=10, end=20, cause=DamageCause.TRUNCATED)],
    )

    # 3. Unknown file
    unknown_res = FileResult(
        source_file="unknown.bin",
        format="unknown",
        confidence=0.0,
    )

    # 4. Failed file (processing raised exception)
    failed_res = FileResult(
        source_file="crashed.bin",
        format="libra98",
        error="IndexError: out of range",
    )

    rep = report.build([ok_res, partial_res, unknown_res, failed_res])
    summary = rep["summary"]

    assert summary["ok"] == 1
    assert summary["partial"] == 1
    assert summary["unknown"] == 1
    assert summary["failed"] == 1
    assert rep["files_processed"] == 4


def test_report_schema_valid_with_summary(tmp_path: Path):
    r1 = FileResult(source_file="a.bin", format="unknown", input_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    r2 = FileResult(source_file="b.bin", format="test", damage=[DamageEntry(start=0, end=4, cause=DamageCause.CRC_FAIL)])
    report.write(tmp_path, [r1, r2])

    errs = validate_output_dir(tmp_path)
    assert not errs, f"Validation errors: {errs}"
