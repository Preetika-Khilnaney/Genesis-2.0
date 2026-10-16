"""tools/lablog_probe.py finds marker, length field and checksum of a block format from bytes alone.

The made-up format here is deliberately NOT LABLOG (other magic, marker, field order,
endianness and checksum coverage), so the probe cannot pass by knowing the samples.
"""
import importlib.util
import struct
import sys
import zlib
from pathlib import Path

spec = importlib.util.spec_from_file_location("lablog_probe", Path(__file__).parent.parent / "tools" / "lablog_probe.py")
probe = importlib.util.module_from_spec(spec)
sys.modules["lablog_probe"] = probe   # @dataclass looks its module up while the file runs
spec.loader.exec_module(probe)


def block(seq: int, payload: bytes) -> bytes:
    """marker 'BK', u8 seq, u16be length, payload, u32be crc32 over marker..payload."""
    body = b"BK" + bytes([seq]) + struct.pack(">H", len(payload)) + payload
    return body + struct.pack(">I", zlib.crc32(body))


def make(n: int, tag: int) -> bytes:
    payloads = [f"id={tag * 10 + i};v={i * 7 % 13}".encode() for i in range(n)]
    payloads[1] += b";note=" + b"x" * 300      # one length > 255, so a u8 reading cannot walk the file
    return b"SYNTH" + bytes([tag]) + b"".join(block(i, p) for i, p in enumerate(payloads))


def outcomes() -> dict[str, str]:
    return {h: o for h, _, o in probe.probe.logs}


def test_probe_finds_layout_and_checksum(tmp_path, capsys):
    for i, n in enumerate((5, 4, 7)):
        (tmp_path / f"s{i}.bin").write_bytes(make(n, i))
    (tmp_path / "s0.damaged-trunc90.bin").write_bytes(make(5, 0)[:-9])   # skipped by default
    assert probe.main([str(tmp_path), "--format", "synth", "--by", "Test"]) == 0
    out = capsys.readouterr().out
    assert "3 samples" in out

    got = outcomes()
    assert got['bytes 0-4 are the magic 53 59 4E 54 48 ("SYNTH")'] == "accepted"
    assert got["42 4B is the block marker; first block at offset 6"] == "accepted"
    assert got["u16be at marker+1 is the payload length (block = length + 9)"] == "accepted"
    assert got["u8 at marker+0 is a block sequence number counting up by 1"] == "accepted"
    assert got["checksum = crc32, stored u32be in the last 4 bytes of each block, "
               "over the marker+...+payload"] == "accepted"
    # rejected hypotheses are logged too
    assert "rejected" in got.values()
    assert "python3 tools/log.py synth" in out and "--by Test" in out


def test_checksum_breaks_a_tie_between_length_readings(tmp_path):
    # seq is u16le and every length < 256, so u16be at marker+1 and u8 at marker+2 also walk
    # every file. Only the true reading puts the payload where the CRC matches.
    def blk(seq, p):
        return b"\xa5\x5a" + struct.pack("<HH", seq, len(p)) + p + struct.pack("<I", zlib.crc32(p))
    for i, n in enumerate((4, 6, 5)):
        data = b"HDR!" + b"".join(blk(j, f"x={i}{j * 37};y=ok".encode()) for j in range(n))
        (tmp_path / f"f{i}.lbl").write_bytes(data)
    assert probe.main([str(tmp_path)]) == 0
    got = outcomes()
    assert got["u16le at marker+2 is the payload length (block = length + 10)"] == "accepted"
    assert got["u16be at marker+1 is the block length (block = length + 10)"] == "rejected"
    assert got["u8 at marker+2 is the block length (block = length + 10)"] == "rejected"
    assert got["u16le at marker+0 is a block sequence number counting up by 1"] == "accepted"
    assert got["payload is ';'-separated key=value pairs with keys x, y in that order"] == "accepted"


def test_probe_needs_enough_clean_samples(tmp_path, capsys):
    (tmp_path / "only.bin").write_bytes(make(5, 0))
    assert probe.main([str(tmp_path)]) == 1
    assert f"need at least {probe.checker.MIN_SAMPLES} clean samples" in capsys.readouterr().out


def test_probe_never_writes_the_log_without_flag(tmp_path, monkeypatch):
    log = tmp_path / "LOG.md"
    log.write_text("")
    monkeypatch.setenv("SALVAGE_FIELD_LOG", str(log))
    for i, n in enumerate((3, 4, 5)):
        (tmp_path / f"s{i}.bin").write_bytes(make(n, i))
    assert probe.main([str(tmp_path)]) == 0
    assert log.read_text() == ""
