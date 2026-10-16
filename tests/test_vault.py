"""VAULT decoder: index table checks, RLE pinned by round trip, XOR key by the all-samples rule.
OWNER: Khushi.

On samples/vault (STAND-IN layout) clean files are 100% verified and right. VAULT has no
checksum, so damaged copies may only be verified wrong where the damage rewrote bytes in
place inside one name or one literal blob byte (nothing in the file can show that); every
other kind of damage must never come out verified wrong. When the real samples arrive, keep
these tests and point them at the new spec.
"""
from __future__ import annotations

import importlib.util
import json
import random
import struct
import sys
from pathlib import Path

import pytest

from salvage.cli import main
from salvage.core.registry import DecodeContext, get
from salvage.recovery import rle
from salvage.recovery.xor import choose_key, xor

ROOT = Path(__file__).parent.parent
SAMPLES = ROOT / "samples" / "vault"
ANS = ROOT / "sample-answers" / "vault"
sys.path.insert(0, str(ROOT / "tools"))
import corrupt  # noqa: E402

DEC = get("vault")
CLEAN = sorted(p for p in SAMPLES.glob("*.vlt") if ".damaged-" not in p.name)
SIBS = [(p.name, p.read_bytes()) for p in CLEAN]
GOOD = ("verified", "corrected")
KEY = 0x5C


def build(items, key=KEY, encode=rle.encode_pairs, entries=None):
    """A VAULT file from (name, content) pairs; `entries` overrides (name, offset, size, raw)."""
    blobs = [encode(c) for _, c in items]
    pos = 6 + 24 * len(items)
    if entries is None:
        entries = []
        for (name, content), b in zip(items, blobs):
            entries.append((name, pos, len(b), len(content)))
            pos += len(b)
    table = b"".join(xor(n.ljust(12, b"\0"), bytes([key])) + struct.pack("<III", o, s, r) for n, o, s, r in entries)
    return b"VALT" + struct.pack("<H", len(entries)) + table + b"".join(blobs)


ITEMS = [(b"A.DAT", b"hello   world\n"), (b"BB.DAT", b"xxxxxxxxxxyz\n"), (b"CCC.DAT", b"end of file\n")]


def ctx_of(*files):
    return DecodeContext("vault", [(f"s{i}", d) for i, d in enumerate(files)])


SIB_CTX = ctx_of(build(ITEMS), build(ITEMS[:2]), build(ITEMS[1:]))


def decode(data: bytes, ctx=SIB_CTX) -> dict:
    return DEC.decode("x.vlt", data, ctx).to_dict()


def field(res, i, k):
    return res["records"][i]["fields"][k]


def answers(name: str) -> list[dict]:
    return json.loads((ANS / f"{name}.json").read_text())["entries"]


# clean samples -------------------------------------------------------------------------------

@pytest.mark.parametrize("path", CLEAN, ids=lambda p: p.name)
def test_clean_sample_fully_verified_and_right(path):
    data = path.read_bytes()
    res = DEC.decode(path.name, data, DecodeContext("vault", [s for s in SIBS if s[0] != path.name])).to_dict()
    truth = answers(path.name)
    assert not res["damage"] and res["error"] is None
    assert res["extra"]["rle_variant"] == "pairs" and res["extra"]["xor_key"] == "0x5C"
    assert res["extra"]["xor_key_agreed"] is True
    assert res["header"]["count"]["status"] == "verified" and res["header"]["count"]["value"] == len(truth)
    for rec, t in zip(res["records"], truth):
        f = rec["fields"]
        assert all(x["status"] == "verified" for x in f.values()), f
        assert (f["name"]["value"], f["offset"]["value"], f["size"]["value"], f["raw_size"]["value"],
                f["data"]["value"]) == (t["name"], t["offset"], t["size"], t["raw_size"], t["content"])
    # round trip: the records rebuild the exact file
    rebuilt = build([(f["name"]["value"].encode(), f["data"]["value"].encode())
                     for f in (r["fields"] for r in res["records"])])
    assert rebuilt == data


# index table checks (the guide's trace: overlap, past EOF, into the index) ----------------

def test_overlap_marks_both_entries_unverified():
    data = build(ITEMS)
    o1 = 6 + 72 + len(rle.encode_pairs(ITEMS[0][1]))
    s1 = len(rle.encode_pairs(ITEMS[1][1]))
    entries = [(b"A.DAT", 78, len(rle.encode_pairs(ITEMS[0][1])), len(ITEMS[0][1])),
               (b"BB.DAT", o1 - 4, s1, len(ITEMS[1][1])),           # starts 4 bytes inside blob 0
               (b"CCC.DAT", o1 + s1, len(rle.encode_pairs(ITEMS[2][1])), len(ITEMS[2][1]))]
    res = decode(build(ITEMS, entries=entries)[:len(data)])
    causes = [d["cause"] for d in res["damage"]]
    assert "index_overlap" in causes
    assert field(res, 0, "data")["status"] != "verified" and field(res, 1, "data")["status"] != "verified"


def test_entry_past_eof_is_truncation():
    data = build(ITEMS)
    cut = len(data) - 3
    res = decode(data[:cut])
    assert field(res, 2, "data")["status"] == "lost" and field(res, 2, "data")["value"] is None
    assert any(d["cause"] == "truncated" and d["end"] == cut for d in res["damage"])
    # the file no longer matches its index: nothing proves the other blobs sit in place
    assert field(res, 0, "data")["status"] == "unverified"
    assert field(res, 0, "data")["value"] == ITEMS[0][1].decode()           # value kept, not invented


def test_entry_pointing_into_the_index_is_bad_offset():
    blobs = [rle.encode_pairs(c) for _, c in ITEMS]
    pos = [78, 78 + len(blobs[0]), 78 + len(blobs[0]) + len(blobs[1])]
    entries = [(b"A.DAT", pos[0], len(blobs[0]), len(ITEMS[0][1])),
               (b"BB.DAT", 10, 16, len(ITEMS[1][1])),                       # inside the table
               (b"CCC.DAT", pos[2], len(blobs[2]), len(ITEMS[2][1]))]
    res = decode(build(ITEMS, entries=entries))
    assert any(d["cause"] == "bad_offset" and d["start"] == 10 and d["end"] == 26 for d in res["damage"])
    assert all(f["value"] is None for k, f in res["records"][1]["fields"].items() if k != "name")


def test_count_overflowing_the_file_never_raises():
    data = bytearray(build(ITEMS))
    data[4:6] = b"\xff\xff"
    res = decode(bytes(data))
    assert res["error"] is None and res["damage"]


# RLE: variant pinned by round trip, size checked against the index -------------------------

def test_rle_variant_pinned_from_samples_packbits_too():
    pk = [build(ITEMS, encode=rle.encode_packbits), build(ITEMS[:2], encode=rle.encode_packbits),
          build(ITEMS[1:], encode=rle.encode_packbits)]
    res = decode(pk[0], ctx_of(*pk[1:]))
    assert res["extra"]["rle_variant"] == "packbits"
    assert field(res, 1, "data")["value"] == ITEMS[1][1].decode() and field(res, 1, "data")["status"] == "verified"


def test_packbits_trace_from_the_guide():
    assert rle.decode_packbits(bytes.fromhex("FC410042")) == b"AAAAAB"
    assert rle.encode_packbits(b"AAAAAB") == bytes.fromhex("FC410042")


def test_size_mismatch_is_bad_length_and_unverified():
    data = bytearray(build(ITEMS))
    data[78] += 1                                    # first pair's count: decodes one byte longer
    res = decode(bytes(data))
    f = field(res, 0, "data")
    assert f["status"] == "unverified" and "index says" in f["note"]
    assert any(d["cause"] == "bad_length" and d["start"] == 78 for d in res["damage"])
    assert field(res, 1, "data")["status"] == "verified"     # the others are untouched and still proven


def test_zeroed_entry_with_empty_blob_is_not_verified():
    blobs = [rle.encode_pairs(c) for _, c in ITEMS]
    entries = [(b"A.DAT", 78, len(blobs[0]), len(ITEMS[0][1])),
               (b"\0" * 6, 0, 0, 0), (b"CCC.DAT", 78 + len(blobs[0]), len(blobs[2]), len(ITEMS[2][1]))]
    data = build([ITEMS[0], (b"", b""), ITEMS[2]], entries=entries)
    res = decode(data)
    assert all(f["status"] != "verified" for f in res["records"][1]["fields"].values())


# XOR names: key by the all-samples rule ----------------------------------------------------

def test_key_disagreement_leaves_names_unverified():
    other = build(ITEMS, key=0x33)
    res = decode(build(ITEMS), ctx_of(other, other))
    assert field(res, 0, "name")["status"] == "unverified" and field(res, 0, "name")["value"] == "A.DAT"
    assert "disagree" in field(res, 0, "name")["note"]


def test_no_readable_key_is_bad_key_and_lost():
    data = bytearray(build(ITEMS))
    for i in range(3):                               # scramble every name: no key reads them
        data[6 + 24 * i:6 + 24 * i + 12] = bytes(range(200 + i, 212 + i))
    res = decode(bytes(data))
    assert all(field(res, i, "name")["status"] == "lost" and field(res, i, "name")["value"] is None for i in range(3))
    assert [d["cause"] for d in res["damage"]].count("bad_key") == 3
    assert field(res, 0, "data")["status"] == "verified"     # blobs do not depend on the names


def test_choose_key_rules():
    n = lambda s, k: xor(s.ljust(12, b"\0"), bytes([k]))
    a = [n(b"AB.DAT", 0x5C), n(b"CD.DAT", 0x5C)]
    assert choose_key([a, a, a]) == (0x5C, True, "key 0x5C wins on all 3 samples that name a key")
    assert choose_key([a, [b"\x01" * 12]])[1] is False                    # too few samples name a key
    assert choose_key([a, [n(b"XY.DAT", 0x11)] * 2])[:2] == (0x5C, False)  # disagreement
    assert choose_key([[b"\x01" * 12] * 2, a])[0] is None


# robustness -------------------------------------------------------------------------------

@pytest.mark.parametrize("n", [0, 3, 5])
def test_empty_or_short_file_never_raises(n):
    res = decode(build(ITEMS)[:n])
    assert res["error"] is None and res["records"] == [] and res["damage"][0]["cause"] == "truncated"


def test_damaged_magic_still_recognised():
    data = build(ITEMS)
    assert DEC.structure_score(b"XXXX" + data[4:]) == 1.0
    assert DEC.structure_score(bytes(range(150))) == 0.0


def _silent(f: dict, info: dict) -> bool:
    """Damage that rewrote this field's own bytes in place: no checksum can show it."""
    lo, hi = f["offset"], f["offset"] + (f["length"] or 0)
    return (info["type"] == "bit_flip" and lo <= info["byte"] < hi) or \
        (info["type"] == "zeroed" and info["start"] < hi and lo < info["end"])


def _check(res: dict, truth: list[dict], info: dict | None) -> int:
    silent = 0
    for rec in res["records"]:
        t = truth[rec["index"]] if rec["index"] < len(truth) else None
        for k, tk in (("name", "name"), ("data", "content"), ("offset", "offset"), ("size", "size"),
                      ("raw_size", "raw_size")):
            f = rec["fields"][k]
            assert f["status"] != "lost" or f["value"] is None, (k, f)
            if f["status"] in GOOD and (t is None or t[tk] != f["value"]):
                assert info is not None and _silent(f, info), f"verified wrong: {k} {f} after {info}"
                silent += 1
    return silent


def test_committed_damaged_samples_through_cli(tmp_path):
    out = tmp_path / "out"
    assert main([str(SAMPLES), str(out)]) == 0
    manifest = {m["file"]: m for m in json.loads((ANS / "manifest.json").read_text())}
    for p in sorted(out.glob("*.json")):
        if p.name == "report.json":
            continue
        res = json.loads(p.read_text())
        name = res["source_file"]
        assert res["format"] == "vault" and res["error"] is None, name
        info = manifest.get(name)
        _check(res, answers(info["source"] if info else name), info)
        if info and info["type"] in ("truncate", "inserted", "deleted"):
            assert res["damage"], f"{name}: structural damage must be reported"


@pytest.mark.parametrize("seed", range(6))
def test_fresh_corrupt_copies_never_lie_except_in_place(seed):
    rng = random.Random(seed)
    for path in CLEAN:
        truth = answers(path.name)
        ctx = DecodeContext("vault", [s for s in SIBS if s[0] != path.name])
        for tag, (blob, info) in corrupt.variants(path.read_bytes(), rng).items():
            res = DEC.decode(tag, blob, ctx).to_dict()
            assert res["error"] is None, tag
            _check(res, truth, info)
            if info["type"] in ("truncate", "inserted", "deleted"):
                assert res["damage"], f"{path.name}.{tag}: structural damage must be reported"


# the probe finds the layout from bytes alone --------------------------------------------

def _probe():
    spec = importlib.util.spec_from_file_location("vault_probe", ROOT / "tools" / "vault_probe.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["vault_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_probe_on_synthetic_vaults(tmp_path):
    probe = _probe()
    for i, items in enumerate((ITEMS, ITEMS[:2], ITEMS[1:], ITEMS[::-1])):
        (tmp_path / f"v{i}.vlt").write_bytes(build(items))
    assert probe.main([str(tmp_path)]) == 0
    got = {h: o for h, _, o in probe.probe.logs}
    assert got["u32 at entry+12 is the blob offset and u32 at entry+16 the stored blob size"] == "accepted"
    assert got["blobs are RLE 'pairs': encode(decode(blob)) == blob for every blob"] == "accepted"
    assert got["blobs are RLE 'packbits': encode(decode(blob)) == blob for every blob"] == "rejected"
    assert got["u32 at entry+20 is the decoded ('pairs') size of the blob"] == "accepted"
    assert got["the XOR key is the same in every file (not one key per file)"] == "accepted"
    assert any(h.startswith("entry bytes 0-11 are a name XORed with the single-byte key 0x5C") and o == "accepted"
               for h, o in got.items())
