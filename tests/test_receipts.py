"""Tests for hash-chained receipts. OWNER: Manas (delivery).

Verifies:
  1. Empty directory produces valid chain.
  2. Multi-file run produces an unbroken hash chain with GENESIS as first prev.
  3. receipts.jsonl passes schema validation against schema/receipt.schema.json.
  4. Modifying any field (tampering) causes verify_chain to return False.
  5. Deleting an entry breaks the chain.
  6. Reordering entries breaks the chain.
  7. Non-existent file returns False.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from salvage.output.receipts import GENESIS, verify_chain, write_chain
from salvage.output.schema_validate import validate_output_dir
from tests.harness import run_salvage


def test_empty_receipt_chain(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    run_salvage(in_dir, output_dir=out_dir)
    receipts_file = out_dir / "receipts.jsonl"
    assert receipts_file.exists()
    assert verify_chain(receipts_file) is True


def test_receipt_chain_structure_and_genesis(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "file_a.bin").write_bytes(b"HELLO_WORLD_A")
    (in_dir / "file_b.bin").write_bytes(b"HELLO_WORLD_B")
    (in_dir / "file_c.bin").write_bytes(b"HELLO_WORLD_C")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    run_salvage(in_dir, output_dir=out_dir)

    receipts_file = out_dir / "receipts.jsonl"
    assert receipts_file.exists()
    assert verify_chain(receipts_file) is True

    lines = [json.loads(line) for line in receipts_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 3

    # First entry has GENESIS prev
    assert lines[0]["prev"] == GENESIS
    assert len(lines[0]["hash"]) == 64

    # Second entry links to first entry's hash
    assert lines[1]["prev"] == lines[0]["hash"]

    # Third entry links to second entry's hash
    assert lines[2]["prev"] == lines[1]["hash"]

    # All entries have spec_version and valid field_status
    for entry in lines:
        assert "spec_version" in entry
        assert "field_status" in entry
        assert "input_sha256" in entry
        assert entry["input_sha256"] is not None

    # Strict schema validation
    errs = validate_output_dir(out_dir)
    assert not errs, f"Schema validation errors: {errs}"


def test_tampering_breaks_chain(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "file_1.bin").write_bytes(b"SAMPLE1")
    (in_dir / "file_2.bin").write_bytes(b"SAMPLE2")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    run_salvage(in_dir, output_dir=out_dir)

    receipts_file = out_dir / "receipts.jsonl"
    assert verify_chain(receipts_file) is True

    # Tamper with second line's content without updating hash
    lines = receipts_file.read_text(encoding="utf-8").splitlines()
    entry1 = json.loads(lines[1])
    entry1["format"] = "TAMPERED_FORMAT"
    tampered_lines = [lines[0], json.dumps(entry1)]
    receipts_file.write_text("\n".join(tampered_lines) + "\n", encoding="utf-8")

    assert verify_chain(receipts_file) is False


def test_reordering_breaks_chain(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "file_1.bin").write_bytes(b"SAMPLE1")
    (in_dir / "file_2.bin").write_bytes(b"SAMPLE2")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    run_salvage(in_dir, output_dir=out_dir)

    receipts_file = out_dir / "receipts.jsonl"
    lines = receipts_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    # Swap line order
    reordered = [lines[1], lines[0]]
    receipts_file.write_text("\n".join(reordered) + "\n", encoding="utf-8")

    assert verify_chain(receipts_file) is False


def test_deleting_line_breaks_chain(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "file_1.bin").write_bytes(b"SAMPLE1")
    (in_dir / "file_2.bin").write_bytes(b"SAMPLE2")
    (in_dir / "file_3.bin").write_bytes(b"SAMPLE3")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    run_salvage(in_dir, output_dir=out_dir)

    receipts_file = out_dir / "receipts.jsonl"
    lines = receipts_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3

    # Delete middle line (line 1)
    deleted_lines = [lines[0], lines[2]]
    receipts_file.write_text("\n".join(deleted_lines) + "\n", encoding="utf-8")

    assert verify_chain(receipts_file) is False


def test_nonexistent_receipts_file_returns_false(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist.jsonl"
    assert verify_chain(nonexistent) is False
