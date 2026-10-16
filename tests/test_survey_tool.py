"""tools/survey.py finds magic, record count, header/record sizes and record columns."""
import importlib.util
import struct
from pathlib import Path

spec = importlib.util.spec_from_file_location("survey", Path(__file__).parent.parent / "tools" / "survey.py")
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


def make(n: int, day: int) -> bytes:
    hdr = b"DEMO\x00" + struct.pack("<HI", n, 900000000 + day * 86400) + b"\x00" * 3
    recs = b"".join(struct.pack("<I", 1 + i) + f"name{i}".encode().ljust(12, b"\x00") for i in range(n))
    return hdr + recs


def test_survey_finds_layout(tmp_path, capsys):
    for i, n in enumerate((2, 5, 3)):
        (tmp_path / f"s{i}.bin").write_bytes(make(n, i))
    assert survey.main([str(tmp_path), "--name", "demo"]) == 0
    out = capsys.readouterr().out
    assert "'DEMO\\x00'" in out
    assert "count u16le  at 5    header 14    record 16" in out
    assert "counts up by 1" in out and "text, e.g." in out
    assert "plausible unix time in every file" in out
    assert 'record_count_field=\'record_count\'' in out


def test_survey_needs_two_files(tmp_path, capsys):
    (tmp_path / "only.bin").write_bytes(make(2, 0))
    assert survey.main([str(tmp_path)]) == 1
