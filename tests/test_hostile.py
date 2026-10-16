"""Phase 5: Hostile directory and determinism verification.
OWNER: Manas (delivery).

Verifies:
  1. CLI runs cleanly (exit 0) on hostile inputs:
     - 0-byte file
     - nested subdirectories
     - empty subdirectories
     - broken symlink / symlink loop
     - unreadable file (permission denied)
     - huge file
     - wrong extensions (misleading extensions)
  2. Output validates strictly against JSON schemas.
  3. No invented values: lost fields are null, records are empty for unknown files.
  4. DETERMINISM: Same input directory processed twice produces byte-identical outputs.
"""
from __future__ import annotations

import filecmp
import json
import os
import stat
from pathlib import Path
import pytest

from salvage.output.receipts import verify_chain
from salvage.output.schema_validate import validate_output_dir
from tests.harness import assert_no_invented_values, assert_only_valid_statuses, run_salvage


def create_hostile_dir(root: Path) -> Path:
    """Populate root with an adversarial assortment of hostile files."""
    root.mkdir(parents=True, exist_ok=True)

    # 1. 0-byte empty file
    (root / "zero_byte.bin").write_bytes(b"")

    # 2. Nested directory with file
    nested_dir = root / "deep" / "sub" / "folder"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (nested_dir / "nested_payload.dat").write_bytes(b"NESTED_DATA_HERE" * 16)

    # 3. Empty subdirectory
    (root / "completely_empty_subdir").mkdir(parents=True, exist_ok=True)

    # 4. Wrong extensions
    (root / "fake_image.jpg").write_bytes(b"NOT_A_JPEG_FILE" * 8)
    (root / "fake_archive.zip").write_bytes(b"\x50\x4B\x05\x06" + b"\x00" * 18)
    (root / "wrong_extension.l98").write_bytes(b"RANDOM_NOISE_NOT_LIBRA" * 4)

    # 5. Huge file (>2MB synthetic block)
    (root / "huge_file.bin").write_bytes(b"\xAA\xBB\xCC\xDD" * (512 * 1024))

    # 6. Unreadable file (chmod 000)
    unreadable = root / "unreadable_file.bin"
    unreadable.write_bytes(b"SECRET_DATA")
    try:
        unreadable.chmod(0)
    except Exception:
        pass

    # 7. Broken symlink / symlink loop (if supported by OS/filesystem)
    try:
        broken_link = root / "broken_symlink.bin"
        if not broken_link.exists():
            broken_link.symlink_to(root / "nonexistent_target.bin")
    except Exception:
        pass

    return root


def test_hostile_directory_processing_and_determinism(tmp_path: Path):
    hostile_in = create_hostile_dir(tmp_path / "hostile_in")
    out1 = tmp_path / "out_run1"
    out2 = tmp_path / "out_run2"

    try:
        # Run 1
        outputs1, report1, code1 = run_salvage(hostile_in, output_dir=out1)
        assert code1 == 0, f"Run 1 failed with exit code {code1}"

        # Run 2 (same input directory)
        outputs2, report2, code2 = run_salvage(hostile_in, output_dir=out2)
        assert code2 == 0, f"Run 2 failed with exit code {code2}"

        # Schema validation on both runs
        errs1 = validate_output_dir(out1)
        assert not errs1, f"Schema validation failed on out1: {errs1}"
        errs2 = validate_output_dir(out2)
        assert not errs2, f"Schema validation failed on out2: {errs2}"

        # Audit receipt chain verification
        assert verify_chain(out1 / "receipts.jsonl") is True
        assert verify_chain(out2 / "receipts.jsonl") is True

        # Invariant checks
        for doc in outputs1.values():
            assert_no_invented_values(doc)
            assert_only_valid_statuses(doc)

        # DETERMINISM: every output file in out1 must match out2 byte-for-byte
        files1 = sorted(p.name for p in out1.iterdir())
        files2 = sorted(p.name for p in out2.iterdir())
        assert files1 == files2, f"Files differ between runs: {files1} != {files2}"

        for fname in files1:
            content1 = (out1 / fname).read_bytes()
            content2 = (out2 / fname).read_bytes()
            assert content1 == content2, f"Non-deterministic output in {fname}!"

    finally:
        # Restore permissions for unreadable file so tmp_path teardown succeeds
        unreadable = hostile_in / "unreadable_file.bin"
        if unreadable.exists():
            try:
                unreadable.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass
