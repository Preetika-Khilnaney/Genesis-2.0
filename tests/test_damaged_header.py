"""Files whose magic/header is damaged are still identified, with the damage reported."""
import json

from salvage.cli import main
from salvage.core.fingerprint import identify_detailed
from salvage.core.reader import ByteWriter
from salvage.core.registry import DecodeContext, Decoder, register
from salvage.core.simple import decode_simple
from salvage.core.spec import FieldSpec, FormatSpec

MAGIC = b"TOYMAGIC"
SPEC = FormatSpec(
    name="toy_header", magic=MAGIC,
    header=[FieldSpec("magic", "bytes", 8), FieldSpec("count", "u16")],
    record=[FieldSpec("id", "u16"), FieldSpec("name", "str", 6)],
    record_count_field="count",
)


@register
class _ToyHeader(Decoder):
    name = "toy_header"
    spec = SPEC
    ready = True

    def decode(self, path, data, ctx: DecodeContext | None = None):
        return decode_simple(self.spec, path, data)


def make(n: int, magic: bytes = MAGIC) -> bytes:
    w = ByteWriter()
    w.write("bytes", magic)
    w.write("u16", n)
    for i in range(n):
        w.write("u16", i)
        w.write("str", f"n{i}", 6)
    return w.getvalue()


def test_exact_magic():
    ident = identify_detailed(make(3))
    assert ident.decoder.name == "toy_header" and ident.method == "magic"


def test_one_flipped_magic_byte_is_near_magic():
    data = bytearray(make(3))
    data[2] ^= 0x01                      # "TOYMAGIC" -> "TONMAGIC"
    ident = identify_detailed(bytes(data))
    assert ident.method == "near_magic" and ident.damaged_magic == [2]


def test_wiped_magic_identified_by_structure():
    ident = identify_detailed(make(3, magic=b"\x00" * 8))
    assert ident.decoder.name == "toy_header" and ident.method == "structure"


def test_unrelated_file_stays_unknown():
    assert identify_detailed(bytes(range(256)) * 4).decoder is None
    assert identify_detailed(b"").decoder is None


def test_cli_reports_bad_magic_and_never_verifies_damaged_bytes(tmp_path):
    inp, out = tmp_path / "in", tmp_path / "out"
    inp.mkdir()
    data = bytearray(make(2))
    data[0] ^= 0x20
    (inp / "flipped.bin").write_bytes(bytes(data))
    (inp / "wiped.bin").write_bytes(make(2, magic=b"\xff" * 8))
    assert main([str(inp), str(out)]) == 0

    flipped = json.loads((out / "flipped.bin.json").read_text())
    assert flipped["format"] == "toy_header"
    assert flipped["extra"]["identified_by"] == "near_magic"
    assert flipped["damage"][0]["cause"] == "bad_magic"
    assert flipped["header"]["magic"]["status"] == "unverified"
    assert flipped["header"]["count"]["status"] == "verified"
    assert len(flipped["records"]) == 2

    wiped = json.loads((out / "wiped.bin.json").read_text())
    assert wiped["extra"]["identified_by"] == "structure"
    assert "structure explains the whole file" in wiped["warnings"][0]
    assert wiped["damage"][0] == {"start": 0, "end": 8, "cause": "bad_magic",
                                  "detail": wiped["warnings"][0], "affected": ["magic"]}
    assert wiped["header"]["magic"]["status"] == "unverified"
    assert wiped["header"]["count"]["status"] == "verified"
