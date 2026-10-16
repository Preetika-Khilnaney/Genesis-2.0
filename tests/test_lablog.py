"""LABLOG decoder: CRC gate, single-bit correction, resync, damage reports. OWNER: Khushi.

(a)-(g) follow the Task 2 checklist. On samples/lablog (STAND-IN layout) clean files are
100% verified and right; damaged copies (the committed ones and fresh tools/corrupt.py
copies) are never verified or corrected wrong. When the real samples arrive, keep these
tests and point them at the new spec.
"""
from __future__ import annotations

import json
import random
import struct
import sys
import zlib
from pathlib import Path

import pytest

from salvage.cli import main
from salvage.core.model import DamageCause, FieldStatus
from salvage.core.registry import get
from salvage.recovery.crc import single_bit_fix

ROOT = Path(__file__).parent.parent
SAMPLES = ROOT / "samples" / "lablog"
ANS = ROOT / "sample-answers" / "lablog"
sys.path.insert(0, str(ROOT / "tools"))
import corrupt  # noqa: E402

DEC = get("lablog")
CLEAN = sorted(p for p in SAMPLES.glob("*.lbl") if ".damaged-" not in p.name)
GOOD = ("verified", "corrected")


def block(seq: int, payload: bytes) -> bytes:
    return b"\xa5\x5a" + struct.pack("<HH", seq, len(payload)) + payload + struct.pack("<I", zlib.crc32(payload))


PAYLOADS = [b"t=10;temp=20.5;ph=7.01", b"t=25;temp=21.0;ph=6.95", b"t=40;temp=21.7;ph=7.10"]
STARTS = [6 + sum(len(block(j, p)) for j, p in enumerate(PAYLOADS[:i])) for i in range(len(PAYLOADS) + 1)]
FILE = b"LBLG\x07\x00" + b"".join(block(i, p) for i, p in enumerate(PAYLOADS))


def decode(data: bytes) -> dict:
    return DEC.decode("x.lbl", data).to_dict()


def statuses(res: dict, key: str = "payload") -> list[str]:
    return [r["fields"][key]["status"] for r in res["records"]]


def truth(name: str) -> dict[int, str]:
    return {r["seq"]: r["payload"] for r in json.loads((ANS / f"{name}.json").read_text())["records"]}


def assert_honest(res: dict, rows: dict[int, str]) -> None:
    """No lost field has a value; nothing verified/corrected disagrees with the truth."""
    for rec in res["records"]:
        f = rec["fields"]
        for name, fld in f.items():
            assert fld["status"] != "lost" or fld["value"] is None, (name, fld)
        if f["payload"]["status"] in GOOD:
            assert f["payload"]["value"] in rows.values(), f"payload verified wrong: {f['payload']}"
            assert f["length"]["value"] == len(f["payload"]["value"])
        if f["seq"]["status"] == "verified":
            assert rows.get(f["seq"]["value"]) == f["payload"]["value"], f"seq verified wrong: {f['seq']}"
    for d in res["damage"]:
        assert 0 <= d["start"] < d["end"], d


# (a) clean samples: every field verified, values match the answers ------------------------

@pytest.mark.parametrize("path", CLEAN, ids=lambda p: p.name)
def test_a_clean_sample_fully_verified(path):
    data = path.read_bytes()
    res = decode(data)
    rows = truth(path.name)
    assert not res["damage"] and res["error"] is None
    assert res["header"]["magic"]["status"] == "verified"
    assert res["header"]["unknown_4"]["status"] == "unverified"      # meaning not proven
    assert [r["fields"]["seq"]["value"] for r in res["records"]] == sorted(rows)
    for rec in res["records"]:
        f = rec["fields"]
        assert f["payload"]["value"] == rows[f["seq"]["value"]]
        assert all(fld["status"] == "verified" for fld in f.values()), f
    # the blocks re-encode to the exact original bytes (round trip)
    rebuilt = data[:6] + b"".join(block(r["fields"]["seq"]["value"], r["fields"]["payload"]["value"].encode())
                                  for r in res["records"])
    assert rebuilt == data
    assert res["extra"]["block_coverage"] == 1.0


def test_payload_keys_parsed_as_numbers():
    f = decode(FILE)["records"][0]["fields"]
    assert (f["t"]["value"], f["temp"]["value"], f["ph"]["value"]) == (10, 20.5, 7.01)
    assert FILE[f["temp"]["offset"]:f["temp"]["offset"] + f["temp"]["length"]] == b"20.5"
    # "7.10" would print back as 7.1: kept as text so nothing is changed
    assert decode(FILE)["records"][2]["fields"]["ph"]["value"] == "7.10"


# (b) one flipped bit -> corrected ------------------------------------------------------------

def test_b_single_bit_in_payload_corrected():
    data = bytearray(FILE)
    data[STARTS[1] + 6 + 3] ^= 0x04                       # block 1, payload byte 3, bit 2
    res = decode(bytes(data))
    assert statuses(res) == ["verified", "corrected", "verified"]
    f = res["records"][1]["fields"]
    assert f["payload"]["value"] == PAYLOADS[1].decode()
    assert "payload byte 3, bit 2" in f["payload"]["note"]
    assert f["seq"]["status"] == "verified" and not res["damage"]


def test_b_single_bit_in_stored_crc_corrected():
    data = bytearray(FILE)
    data[STARTS[2] - 2] ^= 0x80                            # block 1's stored CRC, its 3rd byte, top bit
    res = decode(bytes(data))
    assert statuses(res) == ["verified", "corrected", "verified"]
    f = res["records"][1]["fields"]
    assert f["payload"]["value"] == PAYLOADS[1].decode()
    assert "stored checksum, bit 23" in f["payload"]["note"]


def test_single_bit_fix_counts_checksum_bits_toward_exactly_one():
    p = b"abc"
    good = zlib.crc32(p)
    assert single_bit_fix("crc32", p, good ^ 1, stored_bits=32) == (p, 24)
    assert single_bit_fix("crc32", p, good ^ 1) is None                  # without the option: no fix
    assert single_bit_fix("crc32", p, good ^ 0b11, stored_bits=32) is None  # 2 bits wrong: no fix


# (c) two flipped bits -> that block lost, neighbours verified, exact range ------------------

def test_c_two_bits_in_one_block_lost_with_exact_range():
    data = bytearray(FILE)
    data[STARTS[1] + 6] ^= 0x01
    data[STARTS[1] + 9] ^= 0x10
    res = decode(bytes(data))
    assert statuses(res) == ["verified", "lost", "verified"]
    assert all(f["value"] is None for f in res["records"][1]["fields"].values())
    assert [(d["start"], d["end"], d["cause"]) for d in res["damage"]] == [(STARTS[1], STARTS[2], "crc_fail")]


def test_c_two_bit_errors_are_never_corrected_wrong():
    """CRC-32 over a ~30-byte block has Hamming distance >= 6, so no 2-bit error can look like a
    1-bit one. Measured, not assumed: 2,000 random 2-bit errors inside one block."""
    rng = random.Random(7)
    wrong = corrected = 0
    for _ in range(2000):
        i = rng.randrange(3)
        span = range(STARTS[i] + 6, STARTS[i + 1])         # payload + stored CRC
        a, b = rng.sample(list(span), 2)
        data = bytearray(FILE)
        data[a] ^= 1 << rng.randrange(8)
        data[b] ^= 1 << rng.randrange(8)
        res = decode(bytes(data))
        for rec in res["records"]:
            f = rec["fields"]["payload"]
            if f["status"] == "corrected":
                corrected += 1
                wrong += f["value"] not in [p.decode() for p in PAYLOADS]
    assert wrong == 0 and corrected == 0


# (d) truncated mid-block -> truncation, no exception ----------------------------------------

def test_d_truncated_mid_block():
    cut = STARTS[2] + 9
    res = decode(FILE[:cut])
    assert statuses(res) == ["verified", "verified"]
    assert [(d["start"], d["end"], d["cause"]) for d in res["damage"]] == [(STARTS[2], cut, "truncated")]


@pytest.mark.parametrize("n", [0, 1, 3, 5])
def test_f_empty_or_header_only_never_raises(n):
    res = decode(FILE[:n])
    assert res["records"] == [] and res["error"] is None
    assert res["damage"] and res["damage"][0]["cause"] == "truncated"


def test_f_header_only_file_has_no_damage_and_no_records():
    res = decode(FILE[:6])
    assert res["records"] == [] and res["damage"] == []


# (e) marker bytes inside a payload -> no false resync ---------------------------------------

def test_e_marker_inside_payload_is_not_a_block():
    trap = b"t=1;temp=\xa5\x5a\x00\x00\x03\x00abc;ph=7.0"           # looks like a tiny block
    payloads = [PAYLOADS[0], trap, PAYLOADS[2]]
    data = bytearray(b"LBLG\x07\x00" + b"".join(block(i, p) for i, p in enumerate(payloads)))
    b1 = 6 + len(block(0, payloads[0]))
    data[b1 + 6] ^= 0xFF                                     # break block 1 beyond repair
    res = decode(bytes(data))
    assert statuses(res) == ["verified", "lost", "verified"]
    assert res["records"][2]["fields"]["payload"]["value"] == PAYLOADS[2].decode()
    b2 = b1 + len(block(1, trap))
    assert [(d["start"], d["end"]) for d in res["damage"]] == [(b1, b2)]   # skipped the fake marker


def test_seq_flip_is_not_verified():
    """seq is outside the CRC: a flipped bit there must not come out verified."""
    data = bytearray(FILE)
    data[STARTS[1] + 2] ^= 0x08                              # block 1 seq 1 -> 9
    res = decode(bytes(data))
    seq = [r["fields"]["seq"] for r in res["records"]]
    assert seq[1]["value"] == 9 and seq[1]["status"] == "unverified"
    assert seq[0]["status"] == "verified"                    # 0 right after the header
    assert seq[2]["status"] == "unverified"                  # its only neighbour says 9, not 1
    assert statuses(res) == ["verified"] * 3                 # the payloads are still proven


def test_damaged_header_still_recognised():
    """Magic wiped: the CRC-checked blocks explain the whole file, so it is still LABLOG."""
    assert DEC.structure_score(b"\x00" * 4 + FILE[4:]) == 1.0
    assert DEC.structure_score(bytes(range(200))) == 0.0


# (g) the committed damaged samples and fresh corrupt.py copies match the truth --------------

def test_g_committed_samples_through_cli(tmp_path):
    out = tmp_path / "out"
    assert main([str(SAMPLES), str(out)]) == 0
    manifest = {m["file"]: m for m in json.loads((ANS / "manifest.json").read_text())}
    seen = 0
    for p in sorted(out.glob("*.json")):
        if p.name == "report.json":
            continue
        res = json.loads(p.read_text())
        name = res["source_file"]
        assert res["format"] == "lablog" and res["error"] is None, name
        m = manifest.get(name)
        assert_honest(res, truth(m["source"] if m else name))
        if m and m["type"] in ("truncate", "inserted", "deleted", "zeroed"):
            assert res["damage"], f"{name}: damage must be reported"
        seen += 1
    assert seen == len(list(SAMPLES.glob("*.lbl")))


def test_g_exact_ranges_on_committed_samples(tmp_path):
    out = tmp_path / "out"
    assert main([str(SAMPLES), str(out)]) == 0
    got = {json.loads(p.read_text())["source_file"]: [(d["start"], d["end"], d["cause"]) for d in
                                                      json.loads(p.read_text())["damage"]]
           for p in out.glob("*.json") if p.name != "report.json"}
    # each lost range is exactly the damaged block(s) [start, end), or the cut-off tail
    assert got["lablog_0.damaged-zeroed_209_235.lbl"] == [(203, 236, "crc_fail")]
    assert got["lablog_0.damaged-inserted_44_13.lbl"] == [(38, 84, "crc_fail")]
    assert got["lablog_0.damaged-trunc90.lbl"] == [(236, 242, "truncated")]
    assert got["lablog_1.damaged-flip0_bit797.lbl"] == []        # corrected, nothing lost
    assert got["lablog_0.damaged-flip0_bit21.lbl"] == [(2, 3, "bad_magic")]


@pytest.mark.parametrize("seed", range(8))
def test_g_fresh_corrupt_copies_never_lie(seed):
    rng = random.Random(seed)
    for path in CLEAN:
        rows = truth(path.name)
        for tag, (blob, info) in corrupt.variants(path.read_bytes(), rng).items():
            res = decode(blob)
            assert res["error"] is None, tag
            assert_honest(res, rows)
            if info["type"] in ("truncate", "inserted", "deleted"):
                assert res["damage"], f"{path.name}.{tag}: structural damage must be reported"
