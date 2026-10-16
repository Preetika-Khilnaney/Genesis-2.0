"""The practice files decode with the shared helpers and match their answer files.

This is also a worked example of how a real decoder uses the helpers."""
import importlib.util
import json
import struct
from pathlib import Path

from salvage.core.blocks import BlockLayout, read_blocks
from salvage.core.index import read_index
from salvage.core.model import FieldStatus
from salvage.core.spec import FieldSpec
from salvage.evidence.checker import evaluate
from salvage.recovery.rle import decode_pairs, find_variant
from salvage.recovery.xor import rank_single_byte_keys, xor

_spec = importlib.util.spec_from_file_location("practice", Path(__file__).parent.parent / "tools" / "practice.py")
practice = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(practice)


def generate(tmp_path):
    practice.main(["--out", str(tmp_path), "--count", "4"])
    return tmp_path


def answers(folder: Path, f: Path) -> dict:
    return json.loads((folder / "answers" / f"{f.name}.json").read_text())


def test_plog_blocks_match_answers(tmp_path):
    d = generate(tmp_path) / "plog"
    layout = BlockLayout(marker=b"\xA5\x5A", extra=[FieldSpec("seq", "u16")], length_type="u16",
                         checksum_algo="crc32", checksum_type="u32")
    for f in sorted(d.glob("*.log")):
        scan = read_blocks(f.read_bytes(), layout, start=6)
        assert not scan.damage
        assert all(b.status == FieldStatus.VERIFIED for b in scan.blocks)
        assert [b.payload.decode() for b in scan.blocks] == [r["payload"] for r in answers(d, f)["records"]]


def test_parc_index_rle_xor_match_answers(tmp_path):
    d = generate(tmp_path) / "parc"
    entry = [FieldSpec("name", "bytes", 12), FieldSpec("offset", "u32"), FieldSpec("size", "u32"),
             FieldSpec("raw_size", "u32")]
    files = sorted(d.glob("*.arc"))
    scans = [read_index(f.read_bytes(), 6, struct.unpack_from("<H", f.read_bytes(), 4)[0], entry) for f in files]
    assert all(s.tiles_exactly for s in scans)
    assert find_variant([e.blob for s in scans for e in s.entries]) == ["pairs"]
    names = [bytes.fromhex(e.fields["name"].value) for s in scans for e in s.entries]   # bytes fields are hex text
    key = rank_single_byte_keys(names)[0][0]
    assert key == practice.PARC_KEY
    for f, s in zip(files, scans):
        want = answers(d, f)["entries"]
        got = [{"name": xor(bytes.fromhex(e.fields["name"].value), bytes([key])).rstrip(b"\x00").decode(),
                "content": decode_pairs(e.blob).decode()} for e in s.entries]
        assert got == [{"name": w["name"], "content": w["content"]} for w in want]


def test_prec_decoy_is_not_a_length(tmp_path):
    """Some fields look like lengths but are not: the all-samples check must reject it."""
    d = generate(tmp_path) / "prec"
    samples = [f.read_bytes() for f in sorted(d.glob("*.rec"))]
    real_count = evaluate("prec", "u16 at 9 is the record count", samples,
                          lambda b: 20 + struct.unpack_from("<H", b, 9)[0] * 30 == len(b), log=False)
    decoy_len = evaluate("prec", "u16 at 15 is the length of the records", samples,
                         lambda b: struct.unpack_from("<H", b, 15)[0] == len(b) - 20, log=False)
    assert real_count.accepted and decoy_len.outcome == "rejected"
