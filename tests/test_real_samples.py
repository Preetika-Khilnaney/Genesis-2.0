"""The organisers' participant kit (real-samples/): expected outputs, every file's status, repairs.

real-samples/ is the kit as published: samples/ (30 files + a nested/ folder that must be
skipped), expected_outputs/ (7 reference JSONs), OUTPUT-CONTRACT.md, HINTS.md."""
import importlib.util
import json
import random
from pathlib import Path

import pytest

from salvage.cli import main
from salvage.core.registry import get
from salvage.output.contract import to_contract

ROOT = Path(__file__).parent.parent
KIT = ROOT / "real-samples"
pytestmark = pytest.mark.skipif(not (KIT / "samples").is_dir(), reason="real-samples/ not present")

# Every file's status, as worked out from the bytes (see FIELD-LOG.md). Locks in regressions.
STATUS = {
    "s01.dat": ("LIBRA-98", "ok"), "s02.dat": ("LIBRA-98", "ok"), "s03.dat": ("LIBRA-98", "ok"),
    "s04.dat": ("LIBRA-98", "partial"),
    "s05.dat": ("LABLOG", "ok"), "s06.dat": ("LABLOG", "ok"), "s07.dat": ("LABLOG", "ok"),
    "s08.dat": ("VAULT", "ok"), "s09.dat": ("VAULT", "ok"), "s10.dat": ("VAULT", "ok"),
    "s11.wks": ("WKS", "ok"), "s12.wks": ("WKS", "ok"), "s13.wks": ("WKS", "partial"),
    "s14.wpd": ("WPD", "ok"), "s15.wpd": ("WPD", "partial"),
    "s16.bravo": ("BRAVO", "ok"), "s17.bravo": ("BRAVO", "partial"),
    "s18.cvt": ("CVT", "ok"), "s19.cvt": ("CVT", "ok"),
    "s20.000": ("EBCDIC-DUMP", "ok"), "s21.000": ("EBCDIC-DUMP", "ok"), "s22.000": ("EBCDIC-DUMP", "partial"),
    "s23.wad": ("WAD", "ok"), "s24.pak": ("PAK", "ok"),
    "s25_random.bin": ("UNKNOWN", "unrecognized"), "s26_empty.dat": ("UNKNOWN", "unrecognized"),
    "s27_notes.txt": ("UNKNOWN", "unrecognized"), "s28_tiny.dat": ("UNKNOWN", "unrecognized"),
    "s29_almost_libra.dat": ("LIBRA-98", "failed"), "s30_png_like.dat": ("UNKNOWN", "unrecognized"),
}


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    o = tmp_path_factory.mktemp("real")
    assert main([str(KIT / "samples"), str(o)]) == 0
    return o


def test_all_expected_outputs_match(out):
    spec = importlib.util.spec_from_file_location("check_expected", ROOT / "tools" / "check_expected.py")
    ce = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ce)
    for e in sorted((KIT / "expected_outputs").glob("*.json")):
        errs = ce.check(json.loads(e.read_text()), json.loads((out / e.name).read_text()))
        assert not errs, f"{e.name}: {errs}"


def test_every_file_status_and_nothing_else(out):
    rep = json.loads((out / "report.json").read_text())
    got = {f["file"]: (f["format"], f["status"]) for f in rep["files"]}
    assert got == STATUS                                   # nested/readme_ignore.txt is skipped
    assert not (out / "readme_ignore.txt.json").exists()


def test_proven_single_bit_repairs(out):
    s07 = json.loads((out / "s07.dat.json").read_text())
    s10 = json.loads((out / "s10.dat.json").read_text())
    for doc in (s07, s10):
        assert [(d["kind"], d["lossy"]) for d in doc["damage"]] == [("crc_mismatch", False)]
        assert "exactly one flipped bit" in doc["damage"][0]["detail"]
    assert len(s07["records"]) == 28 and all(r.get("verified") is not False for r in s07["records"])


def test_damage_is_reported_not_hidden(out):
    s22 = json.loads((out / "s22.000.json").read_text())
    assert s22["damage"][0]["kind"] == "truncated" and s22["records"][-1]["verified"] is False
    s29 = json.loads((out / "s29_almost_libra.dat.json").read_text())
    assert s29["records"] == [] and s29["damage"][0]["kind"] == "truncated"
    s15 = json.loads((out / "s15.wpd.json").read_text())
    assert s15["records"][-1] == {"index": 3, "type": "paragraph", "text": "Please note: deadline",
                                  "verified": False, "issues": ["truncated"]}


def test_no_false_recoveries_on_lablog_bit_flips():
    """LABLOG is CRC-protected end to end: a damaged copy must never yield a wrong verified record."""
    rng, dec = random.Random(3), get("LABLOG")
    b = (KIT / "samples" / "s05.dat").read_bytes()
    truth = {r["sample"]: r for r in to_contract(dec.decode("s05.dat", b))["records"]}
    for _ in range(150):
        c = bytearray(b)
        for _ in range(rng.choice([1, 2])):
            c[rng.randrange(len(c))] ^= 1 << rng.randrange(8)
        for r in to_contract(dec.decode("s05.dat", bytes(c)))["records"]:
            if r.get("verified") is not False:
                assert {k: v for k, v in r.items() if k != "issues"} == truth[r["sample"]]
