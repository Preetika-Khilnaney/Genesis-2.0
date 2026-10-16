"""Schema validation tests. OWNER: Manas (delivery).

Verifies:
  - all per-file outputs validate against schema/output.schema.json
  - report.json validates against schema/report.schema.json
  - receipts.jsonl entries validate against schema/receipt.schema.json
  - the four status labels are the ONLY ones used (never invent others)
  - a lost field never contains a non-None value
"""
from __future__ import annotations

import json

import pytest

try:
    import jsonschema  # noqa: F401
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

from salvage.core.model import FieldStatus
from salvage.output.schema_validate import FIELD_STATUSES, VALID_STATUSES, validate_output_dir
from tests.harness import (
    assert_no_invented_values,
    assert_only_valid_statuses,
    assert_schema_valid,
    run_salvage,
)

pytestmark = pytest.mark.skipif(
    not _HAS_JSONSCHEMA,
    reason="jsonschema not installed; run `pip install jsonschema` to enable these tests",
)


def test_valid_statuses_constant_matches_model():
    """Sanity: internal field statuses agree with the model; file statuses are the contract's five."""
    assert FIELD_STATUSES == {s.value for s in FieldStatus}
    assert VALID_STATUSES == {"ok", "partial", "unsupported", "unrecognized", "failed"}


def test_unknown_files_pass_schema(tmp_path):
    """Unknown and empty files should still produce schema-valid output."""
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "mystery.bin").write_bytes(bytes(range(256)) * 4)
    (inp / "empty.dat").write_bytes(b"")

    out = tmp_path / "out"
    outputs, report, code = run_salvage(inp, output_dir=out)

    assert code == 0
    assert_schema_valid(out)


def test_no_invented_values_in_unknown_file(tmp_path):
    """Unknown file output must not invent records or fill lost fields with values."""
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "mystery.bin").write_bytes(bytes(range(256)) * 4)
    out = tmp_path / "out"
    outputs, _, _ = run_salvage(inp, output_dir=out)
    for doc in outputs.values():
        assert_no_invented_values(doc)
        assert_only_valid_statuses(doc)
        # Unknown files must have empty records list
        assert doc.get("records") == [], f"Unknown file invented records: {doc.get('records')}"


def test_report_schema_valid(tmp_path):
    """report.json from a normal run validates against its schema."""
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "a.bin").write_bytes(b"\x00" * 64)
    out = tmp_path / "out"
    run_salvage(inp, output_dir=out)
    assert_schema_valid(out)


def test_illegal_status_label_is_caught(tmp_path):
    """validate_output_dir must report an error for an illegal status label."""
    out = tmp_path / "out"
    out.mkdir()
    doc = {"source_file": "x.bin", "format": "UNKNOWN", "status": "guessed", "metadata": {},
           "records": [], "damage": []}
    (out / "x.bin.json").write_text(json.dumps(doc))
    (out / "report.json").write_text(json.dumps(
        {"tool_version": "0", "files": [{"file": "x.bin", "format": "UNKNOWN", "status": "unrecognized",
                                         "records": 0, "damage": 0}], "totals": {}}))
    errs = validate_output_dir(out)
    assert any("guessed" in e for e in errs), f"Expected 'guessed' error, got: {errs}"


def test_receipts_validate(tmp_path):
    """receipts.jsonl entries must validate against the receipt schema."""
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "f.bin").write_bytes(b"\xAB" * 32)
    out = tmp_path / "out"
    run_salvage(inp, output_dir=out)
    assert_schema_valid(out)
