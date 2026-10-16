"""CLI contract: always exit 0, always write report.json, never crash on odd input."""
import json

from salvage.cli import main
from salvage.output.receipts import verify_chain


def test_unknown_and_empty_files(tmp_path):
    inp, out = tmp_path / "in", tmp_path / "out"
    inp.mkdir()
    (inp / "mystery.bin").write_bytes(bytes(range(256)) * 4)
    (inp / "empty.dat").write_bytes(b"")
    assert main([str(inp), str(out)]) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["files_processed"] == 2
    assert report["unknown_files"] == 2
    per_file = json.loads((out / "mystery.bin.json").read_text())
    assert per_file["format"] == "unknown"
    assert per_file["records"] == []                  # nothing invented
    assert "entropy_map" in per_file["extra"]
    assert verify_chain(out / "receipts.jsonl")


def test_missing_input_dir_still_exits_zero(tmp_path):
    out = tmp_path / "out"
    assert main([str(tmp_path / "nope"), str(out)]) == 0
    assert json.loads((out / "report.json").read_text())["fatal"]


def test_bad_arguments_exit_zero():
    assert main([]) == 0
