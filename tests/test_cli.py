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
    assert [f["file"] for f in report["files"]] == ["empty.dat", "mystery.bin"]
    assert report["totals"]["unrecognized"] == 2
    per_file = json.loads((out / "mystery.bin.json").read_text())
    assert per_file["format"] == "UNKNOWN" and per_file["status"] == "unrecognized"
    assert per_file["records"] == []                  # nothing invented
    assert per_file["metadata"]["size"] == 1024 and "entropy" in per_file["metadata"]
    assert verify_chain(out / "receipts.jsonl")


def test_subdirectories_are_skipped(tmp_path):
    """OUTPUT-CONTRACT.md: every file in input_dir, non-recursive; directories are skipped."""
    inp, out = tmp_path / "in", tmp_path / "out"
    (inp / "nested").mkdir(parents=True)
    (inp / "top.bin").write_bytes(b"x")
    (inp / "nested" / "deep.bin").write_bytes(b"y")
    assert main([str(inp), str(out)]) == 0
    assert (out / "top.bin.json").exists() and not (out / "deep.bin.json").exists()
    assert [f["file"] for f in json.loads((out / "report.json").read_text())["files"]] == ["top.bin"]


def test_missing_input_dir_still_exits_zero(tmp_path):
    out = tmp_path / "out"
    assert main([str(tmp_path / "nope"), str(out)]) == 0
    assert json.loads((out / "report.json").read_text())["fatal"]


def test_bad_arguments_exit_zero():
    assert main([]) == 0
