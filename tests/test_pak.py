"""Game archive (Quake PAK): directory at the end, blobs tile the area before it. OWNER: Khushi.

On samples/pak clean files have every name, offset and size verified and right; blob contents
are never verified (no checksum covers them). Damaged copies may only be verified wrong where
the damage rewrote one name's bytes in place; every other kind of damage must never come out
verified wrong.
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
from salvage.core.registry import get

ROOT = Path(__file__).parent.parent
SAMPLES = ROOT / "samples" / "pak"
ANS = ROOT / "sample-answers" / "pak"
sys.path.insert(0, str(ROOT / "tools"))
import corrupt  # noqa: E402

DEC = get("pak")
CLEAN = sorted(p for p in SAMPLES.glob("*.pak") if ".damaged-" not in p.name)
GOOD = ("verified", "corrected")
FILES = [(b"maps/e1m1.bsp", b"\x01\x02\x03" * 10), (b"sound/hit.wav", bytes(range(40))),
         (b"cfg/autoexec.cfg", b"bind w +forward\n")]


def build(files=FILES, entries=None):
    blob = b"".join(c for _, c in files)
    if entries is None:
        entries, pos = [], 12
        for name, c in files:
            entries.append((name, pos, len(c)))
            pos += len(c)
    directory = b"".join(n.ljust(56, b"\0") + struct.pack("<ii", o, s) for n, o, s in entries)
    return b"PACK" + struct.pack("<ii", 12 + len(blob), len(directory)) + blob + directory


def decode(data: bytes) -> dict:
    return DEC.decode("x.pak", data).to_dict()


def fields(res, k):
    return [r["fields"][k] for r in res["records"]]


def answers(name: str) -> list[dict]:
    return json.loads((ANS / f"{name}.json").read_text())["entries"]


@pytest.mark.parametrize("path", CLEAN, ids=lambda p: p.name)
def test_clean_sample_verified_and_right(path):
    res = decode(path.read_bytes())
    truth = answers(path.name)
    assert not res["damage"] and res["error"] is None
    assert all(res["header"][k]["status"] == "verified" for k in ("magic", "dir_offset", "dir_length"))
    for rec, t in zip(res["records"], truth):
        f = rec["fields"]
        assert (f["name"]["value"], f["offset"]["value"], f["size"]["value"]) == (t["name"], t["offset"], t["size"])
        assert all(f[k]["status"] == "verified" for k in ("name", "offset", "size"))
        assert f["data"]["status"] == "unverified"                    # nothing covers the content
    assert len(res["records"]) == len(truth)


def test_blob_content_reported_never_verified():
    res = decode(build())
    data = fields(res, "data")
    assert data[2]["value"] == "bind w +forward\n" and data[0]["value"] == ("010203" * 10)
    assert {d["status"] for d in data} == {"unverified"}


def test_bytes_inserted_in_blob_area_directory_refound_at_end():
    data = build()
    bad = data[:20] + b"JUNK" + data[20:]                              # inside blob 0
    res = decode(bad)
    assert res["extra"]["directory_found_by"].startswith("end of file")
    names = fields(res, "name")
    assert [n["value"] for n in names] == [n.decode() for n, _ in FILES]
    assert names[0]["status"] == "unverified"                          # the shift could be in this name
    assert [n["status"] for n in names[1:]] == ["verified", "verified"]
    assert all(f["status"] != "verified" for f in fields(res, "offset"))
    assert any(d["cause"] == "bad_offset" and d["start"] == 12 for d in res["damage"])


def test_byte_deleted_inside_first_name_is_not_verified():
    data = build()
    d = 12 + sum(len(c) for _, c in FILES)
    bad = data[:d + 30] + data[d + 31:]                                # in entry 0's NUL padding
    res = decode(bad)
    assert fields(res, "name")[0]["status"] != "verified"


def test_directory_cut_off_is_truncation_and_never_raises():
    data = build()
    d = 12 + sum(len(c) for _, c in FILES)
    for cut in (d - 5, d + 10, d + 64 + 20):
        res = decode(data[:cut])
        assert res["error"] is None
        assert any(x["cause"] == "truncated" for x in res["damage"]), cut
        assert all(n["status"] != "verified" for n in fields(res, "name"))  # position unconfirmed


def test_entry_pointing_into_header_is_bad_offset():
    entries = [(b"a", 4, 30), (b"b", 42, 40), (b"c", 82, 16)]
    res = decode(build(entries=entries))
    assert any(d["cause"] == "bad_offset" and d["start"] == 4 for d in res["damage"])
    assert all(v["value"] is None for k, v in res["records"][0]["fields"].items() if k != "name")


def test_entry_past_eof_range_is_the_entry_itself():
    data = build()
    d = 12 + sum(len(c) for _, c in FILES)
    bad = bytearray(data)
    bad[d + 64 + 56:d + 64 + 60] = struct.pack("<i", 5000)            # entry 1 offset far past EOF
    res = decode(bytes(bad))
    r = [x for x in res["damage"] if "entry 1" in x["affected"]]
    assert r and r[0]["start"] == d + 64 and r[0]["end"] == d + 128 and r[0]["cause"] == "bad_offset"
    assert all(x["start"] < x["end"] for x in res["damage"])


def test_zeroed_name_is_lost_not_invented():
    data = bytearray(build())
    d = 12 + sum(len(c) for _, c in FILES)
    data[d:d + 56] = bytes(56)
    res = decode(bytes(data))
    n = fields(res, "name")[0]
    assert n["status"] == "lost" and n["value"] is None
    assert fields(res, "offset")[0]["status"] == "verified"            # the rest of the entry is fine


@pytest.mark.parametrize("n", [0, 4, 11])
def test_short_file_never_raises(n):
    res = decode(build()[:n])
    assert res["error"] is None and res["damage"][0]["cause"] == "truncated"


def test_damaged_magic_still_recognised():
    assert DEC.structure_score(b"XXXX" + build()[4:]) == 1.0
    assert DEC.structure_score(bytes(range(200))) == 0.0


def _silent(f: dict, info: dict) -> bool:
    lo, hi = f["offset"], f["offset"] + (f["length"] or 0)
    return (info["type"] == "bit_flip" and lo <= info["byte"] < hi) or \
        (info["type"] == "zeroed" and info["start"] < hi and lo < info["end"])


def _check(res: dict, truth: list[dict], info: dict | None) -> None:
    assert res["error"] is None
    assert all(d["start"] < d["end"] for d in res["damage"]), res["damage"]
    for rec in res["records"]:
        t = truth[rec["index"]] if rec["index"] < len(truth) else None
        for k in ("name", "offset", "size", "data"):
            f = rec["fields"][k]
            assert f["status"] != "lost" or f["value"] is None
            assert not (k == "data" and f["status"] in GOOD)
            if k != "data" and f["status"] in GOOD and (t is None or t[k] != f["value"]):
                assert info is not None and _silent(f, info), f"verified wrong: {k} {f} after {info}"


def test_committed_damaged_samples_through_cli(tmp_path):
    out = tmp_path / "out"
    assert main([str(SAMPLES), str(out)]) == 0
    manifest = {m["file"]: m for m in json.loads((ANS / "manifest.json").read_text())}
    for p in sorted(out.glob("*.json")):
        if p.name == "report.json":
            continue
        res = json.loads(p.read_text())
        name = res["source_file"]
        assert res["format"] == "pak", name
        info = manifest.get(name)
        _check(res, answers(info["source"] if info else name), info)
        if info and info["type"] in ("truncate", "inserted", "deleted"):
            assert res["damage"], f"{name}: structural damage must be reported"


@pytest.mark.parametrize("seed", range(6))
def test_fresh_corrupt_copies_never_lie_except_in_place(seed):
    rng = random.Random(seed)
    for path in CLEAN:
        truth = answers(path.name)
        for tag, (blob, info) in corrupt.variants(path.read_bytes(), rng).items():
            res = decode(blob)
            _check(res, truth, info)
            if info["type"] in ("truncate", "inserted", "deleted"):
                assert res["damage"], f"{path.name}.{tag}: structural damage must be reported"


def test_probe_on_synthetic_paks(tmp_path):
    spec = importlib.util.spec_from_file_location("archive_probe", ROOT / "tools" / "archive_probe.py")
    probe = importlib.util.module_from_spec(spec)
    sys.modules["archive_probe"] = probe
    spec.loader.exec_module(probe)
    for i, files in enumerate((FILES, FILES[:2], FILES[1:], FILES[::-1])):
        (tmp_path / f"p{i}.pak").write_bytes(build(files))
    assert probe.main([str(tmp_path)]) == 0
    got = {h: o for h, _, o in probe.probe.logs}
    assert got["directory = 64-byte entries; u32 at entry+56 is the blob offset, u32 at entry+60 its size"] == "accepted"
    assert got["entry bytes 0-55 are a plain NUL-padded name (printable text, then zeros)"] == "accepted"
    assert got["names are XOR-obfuscated (a non-zero key reads them best)"] == "rejected"
    assert any(h.startswith("u32 at 4 is the directory offset and u32 at 8 its length") and o == "accepted"
               for h, o in got.items())
