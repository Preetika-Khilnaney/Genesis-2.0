"""Tests for report.json (OUTPUT-CONTRACT.md shape) and atomic writing. OWNER: Manas (delivery)."""
from __future__ import annotations

import json
from pathlib import Path

from salvage.core.model import DamageCause, DamageEntry, Field, FieldStatus, FileResult, Record
from salvage.output import report
from salvage.output.schema_validate import validate_output_dir


def test_report_atomic_write(tmp_path: Path):
    res = FileResult(source_file="sample.bin", format="LIBRA-98", input_sha256="abc123")
    out_file = report.write(tmp_path, [res])
    assert out_file.exists() and out_file.name == "report.json"
    assert not (tmp_path / "report.json.tmp").exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["files"] == [{"file": "sample.bin", "format": "LIBRA-98", "status": "ok", "records": 0, "damage": 0}]


def test_report_status_classification():
    ok = FileResult(source_file="clean.bin", format="LIBRA-98",
                    records=[Record(index=0, fields={"val": Field("val", 10, FieldStatus.VERIFIED)})])
    partial = FileResult(source_file="damaged.bin", format="LIBRA-98",
                         damage=[DamageEntry(start=10, end=20, cause=DamageCause.TRUNCATED)])
    repaired = FileResult(source_file="fixed.bin", format="LABLOG",
                          damage=[DamageEntry(start=0, end=4, cause=DamageCause.CRC_MISMATCH, lossy=False)])
    unknown = FileResult(source_file="unknown.bin", format="unknown")
    failed = FileResult(source_file="crashed.bin", format="LIBRA-98", error="IndexError: out of range")
    unsupported = FileResult(source_file="locked.wpd", format="WPD", status="unsupported")
    rep = report.build([ok, partial, repaired, unknown, failed, unsupported])
    status = {f["file"]: f["status"] for f in rep["files"]}
    assert status == {"clean.bin": "ok", "damaged.bin": "partial", "fixed.bin": "ok",
                      "unknown.bin": "unrecognized", "crashed.bin": "failed", "locked.wpd": "unsupported"}
    assert rep["totals"] == {"ok": 2, "partial": 1, "unsupported": 1, "unrecognized": 1, "failed": 1}


def test_report_schema_valid(tmp_path: Path):
    r1 = FileResult(source_file="a.bin", format="unknown")
    r2 = FileResult(source_file="b.bin", format="VAULT",
                    damage=[DamageEntry(start=0, end=4, cause=DamageCause.CRC_FAIL)])
    report.write(tmp_path, [r1, r2])
    errs = validate_output_dir(tmp_path)
    assert all("not found" not in e and "report.json" not in e for e in errs), errs
