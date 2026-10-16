"""LABLOG. OWNER: Khushi (recovery).

Checksummed blocks: every block's payload is VERIFIED by its CRC-32, a provable single-bit
error is CORRECTED, and every other bad block is LOST with an exact byte range and cause.
The block walk (CRC gate, single-bit fix, resync, truncation) is core.blocks.read_blocks;
this module only describes the layout and turns blocks into records.

STAND-IN LAYOUT: worked out from samples/lablog/ (our demo data, invented layout) with
tools/lablog_probe.py. Redo it from real-samples/lablog/ when the real samples arrive
(`python3 tools/lablog_probe.py real-samples/lablog/ --by Khushi --log`); the record
building, the seq/length evidence rules and the tests carry over. Every fact below is a
FIELD-LOG row (format "lablog"):

    0   4C 42 4C 47     magic "LBLG"
    4   u16             meaning unknown (one value per file): always UNVERIFIED
    6   blocks until EOF:
        A5 5A | u16 seq | u16 length N | N payload bytes | u32 crc32(payload)

The CRC covers the payload only, so seq and length need their own evidence:
  - length is VERIFIED when the CRC passed over exactly that many bytes;
  - seq is VERIFIED when it continues the count (0, 1, 2 ...) from an adjacent good block,
    or is 0 on the block right after the header. Otherwise UNVERIFIED: a flipped bit there
    would go unnoticed by the CRC.
"""
from __future__ import annotations

from ..core.blocks import Block, BlockLayout, block_structure_score, read_blocks
from ..core.model import DamageCause, DamageEntry, Field, FieldStatus, FileResult, Record
from ..core.reader import ByteReader, OutOfBounds
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec, decode_fields

MAGIC = b"LBLG"
HEADER_SIZE = 6
KEYS = ("t", "temp", "ph")       # payload keys, in order (FIELD-LOG: same keys in every block)

LAYOUT = BlockLayout(
    marker=b"\xa5\x5a",
    extra=[FieldSpec("seq", "u16")],
    length_type="u16",
    length_counts="payload",
    checksum_algo="crc32",
    checksum_type="u32",
    checksum_covers="payload",
    endian="little",
)

LABLOG_SPEC = FormatSpec(
    name="lablog",
    magic=MAGIC,
    endian="little",
    description=("A 6-byte header, then checksummed blocks back to back until the end of the file. "
                 "Each block is a 2-byte marker A5 5A, a sequence number, a payload length, the payload "
                 "(text like t=89;temp=24.9;ph=6.81) and a CRC-32 of the payload. "
                 "STAND-IN layout from our own samples; redo from the real samples."),
    checksum="CRC-32 (zlib.crc32) of the payload only, stored as u32 little-endian after the payload",
    header=[
        FieldSpec("magic", "bytes", 4, desc="file signature 'LBLG'",
                  evidence="FIELD-LOG: same in all 6 samples"),
        FieldSpec("unknown_4", "u16", desc="meaning unknown; one value per file (40-45 seen)",
                  evidence="FIELD-LOG: not the block count, the file size or a constant (open)"),
    ],
    record=[
        FieldSpec("seq", "u16", desc="block sequence number, 0, 1, 2 ... (after marker A5 5A)",
                  evidence="FIELD-LOG: counts up by 1 from 0 in every sample"),
        FieldSpec("length", "u16", desc="payload length in bytes; block = length + 10",
                  evidence="FIELD-LOG: walks all 37 blocks to EOF; the CRC rejects 2 rival readings"),
        FieldSpec("payload", "bytes", desc="printable ASCII text, ';'-separated key=value pairs",
                  evidence="FIELD-LOG: printable in every block; crc32 matches all 37 blocks"),
        FieldSpec("t", "str", desc="payload key t (number)", evidence="FIELD-LOG: key order t, temp, ph"),
        FieldSpec("temp", "str", desc="payload key temp (number)", evidence="FIELD-LOG: key order t, temp, ph"),
        FieldSpec("ph", "str", desc="payload key ph (number)", evidence="FIELD-LOG: key order t, temp, ph"),
    ],
    notes=["Blocks: A5 5A | u16 seq | u16 length N | N payload bytes | u32 crc32(payload).",
           "The CRC does not cover seq or length; see the module docstring for how they are verified.",
           "unknown_4 stays unverified until its meaning is proven."],
)

GOOD = (FieldStatus.VERIFIED, FieldStatus.CORRECTED)


def _number(text: str):
    """int or float when it prints back to exactly the same text, else the text itself."""
    for conv in (int, float):
        try:
            v = conv(text)
        except ValueError:
            continue
        if str(v) == text:
            return v
    return text


def _parse_payload(payload: bytes) -> dict[str, tuple[str, int]] | None:
    """key -> (value text, offset inside the payload), or None if not key=value text."""
    if not payload or not all(32 <= c < 127 for c in payload):
        return None
    out, pos = {}, 0
    for part in payload.decode("ascii").split(";"):
        key, sep, val = part.partition("=")
        if not sep or not key or key in out:
            return None
        out[key] = (val, pos + len(key) + 1)
        pos += len(part) + 1
    return out


def _seq_ok(blocks: list[Block], i: int) -> bool:
    """Does block i's seq continue the count from an adjacent good block (no gap between)?"""
    b = blocks[i]
    seq = b.header["seq"].value
    if b.offset == HEADER_SIZE and seq == 0:
        return True
    prev = blocks[i - 1] if i > 0 else None
    nxt = blocks[i + 1] if i + 1 < len(blocks) else None
    if prev and prev.status in GOOD and prev.end == b.offset and seq == prev.header["seq"].value + 1:
        return True
    if nxt and nxt.status in GOOD and b.end == nxt.offset and nxt.header["seq"].value == seq + 1:
        return True
    return False


def _record(index: int, blocks: list[Block], i: int) -> Record:
    b = blocks[i]
    rec = Record(index=index, offset=b.offset)
    seq_off, len_off = b.offset + 2, b.offset + 4
    if b.status == FieldStatus.LOST:
        # nothing in a failed block can be trusted, not even its seq or length: no values
        for s in LABLOG_SPEC.record:
            rec.add(Field(s.name, None, FieldStatus.LOST, note=b.note))
        return rec

    good = b.status in GOOD
    seq = b.header["seq"]
    if good and _seq_ok(blocks, i):
        seq_status, seq_note = FieldStatus.VERIFIED, "continues the 0, 1, 2 ... count from an adjacent good block"
    else:
        seq_status, seq_note = FieldStatus.UNVERIFIED, "not covered by the CRC and not confirmed by a neighbour"
    rec.add(Field("seq", seq.value, seq_status, seq_off, 2, seq_note))

    length = b.header["length"]
    if good:
        rec.add(Field("length", length.value, FieldStatus.VERIFIED, len_off, 2,
                      "the CRC passed over exactly this many bytes"))
    else:
        rec.add(Field("length", length.value, FieldStatus.UNVERIFIED, len_off, 2, b.note))

    pairs = _parse_payload(b.payload)
    text = b.payload.decode("ascii") if pairs is not None else b.payload.hex()
    note = b.note if pairs is not None else f"{b.note}; not key=value text, shown as hex"
    rec.add(Field("payload", text, b.status, b.payload_offset, len(b.payload), note))
    for key in KEYS:
        if pairs is None or key not in pairs:
            rec.add(Field(key, None, FieldStatus.LOST, note="key not present in the payload"))
            continue
        val, at = pairs[key]
        rec.add(Field(key, _number(val), b.status, b.payload_offset + at, len(val), b.note))
    return rec


@register
class LablogDecoder(Decoder):
    name = "lablog"
    spec = LABLOG_SPEC
    ready = True

    def structure_score(self, data: bytes) -> float:
        # header damaged: still LABLOG if CRC-checked blocks explain every byte after it
        return block_structure_score(data, LAYOUT, HEADER_SIZE)

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        try:
            res.header = decode_fields(ByteReader(data, "little"), LABLOG_SPEC.header)
        except OutOfBounds:
            res.damage.append(DamageEntry(0, len(data), DamageCause.TRUNCATED,
                                          "file ends inside the 6-byte header", ["header"]))
            return res
        magic = res.header["magic"]
        if data[:len(MAGIC)] == MAGIC:
            magic.status, magic.note = FieldStatus.VERIFIED, "matches 'LBLG' (same in every sample)"
        else:
            magic.note = "does not match 'LBLG'"
        res.header["unknown_4"].note = "meaning unknown (FIELD-LOG: open)"

        scan = read_blocks(data, LAYOUT, start=HEADER_SIZE)
        res.damage += scan.damage
        res.warnings += scan.warnings
        res.records = [_record(i, scan.blocks, i) for i in range(len(scan.blocks))]
        res.extra["blocks"] = {s.value: sum(b.status == s for b in scan.blocks) for s in FieldStatus}
        res.extra["block_coverage"] = round(scan.coverage(max(len(data) - HEADER_SIZE, 0)), 4)
        return res
