"""Declarative format specs. OWNER: Preetika (core). SHARED INTERFACE.

A format is described as data (FormatSpec), not as hand-written parsing code.
The same spec drives decoding, re-encoding (round-trip check) and FORMAT-SPEC.md.

Example:
    LIBRA98 = FormatSpec(
        name="libra98", magic=b"LIBR", endian="little",
        header=[FieldSpec("magic", "bytes", 4), FieldSpec("version", "u16"),
                FieldSpec("record_count", "u16")],
        record=[FieldSpec("roll_no", "u16"), FieldSpec("name", "str", 20),
                FieldSpec("exam_date", "dos_date")],
        record_count_field="record_count",
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .model import Field, FieldStatus
from .reader import ByteReader, ByteWriter, type_size


@dataclass
class FieldSpec:
    name: str
    type: str                  # see ByteReader.read for supported types
    length: int | None = None  # for bytes / str
    desc: str = ""             # shown in FORMAT-SPEC.md
    evidence: str = ""         # why we believe this (link to FIELD-LOG entry)


@dataclass
class FormatSpec:
    name: str
    magic: bytes | None = None
    magic_offset: int = 0
    endian: str = "little"
    header: list[FieldSpec] = field(default_factory=list)
    record: list[FieldSpec] = field(default_factory=list)
    record_count_field: str | None = None   # header field holding the record count, if any
    description: str = ""
    checksum: str = ""                      # e.g. "CRC-32 over each block, stored after payload"
    notes: list[str] = field(default_factory=list)

    def record_size(self) -> int | None:
        sizes = [type_size(f.type) or (f.length if f.type in ("bytes", "str") else None) for f in self.record]
        return None if any(s is None for s in sizes) else sum(sizes)


def decode_fields(reader: ByteReader, specs: list[FieldSpec],
                  default_status: FieldStatus = FieldStatus.UNVERIFIED) -> dict[str, Field]:
    """Decode a sequence of fields. Raises OutOfBounds on truncation (caller records damage).
    Fields start UNVERIFIED; checksum / round-trip / evidence code upgrades them."""
    out: dict[str, Field] = {}
    for s in specs:
        start = reader.pos
        value = reader.read(s.type, s.length)
        if isinstance(value, bytes):
            value = value.hex()
        out[s.name] = Field(s.name, value, default_status, offset=start, length=reader.pos - start)
    return out


def encode_fields(values: dict[str, Field], specs: list[FieldSpec], endian: str = "little") -> bytes:
    """Re-encode decoded fields. Used by the round-trip check."""
    w = ByteWriter(endian)
    for s in specs:
        v = values[s.name].value
        if s.type == "bytes" and isinstance(v, str):
            v = bytes.fromhex(v)
        w.write(s.type, v, s.length)
    return w.getvalue()


def round_trip_ok(raw: bytes, values: dict[str, Field], specs: list[FieldSpec], endian: str = "little") -> bool:
    try:
        return encode_fields(values, specs, endian) == raw
    except Exception:
        return False


def spec_to_markdown(spec: FormatSpec) -> str:
    """Render one FORMAT-SPEC.md section from a spec."""
    lines = [f"## {spec.name}", ""]
    if spec.description:
        lines += [spec.description, ""]
    magic = spec.magic.hex(" ") if spec.magic else "none"
    lines += [f"- Magic: `{magic}` at offset {spec.magic_offset}", f"- Endianness: {spec.endian}"]
    if spec.checksum:
        lines.append(f"- Checksum: {spec.checksum}")
    if spec.record_count_field:
        lines.append(f"- Record count: header field `{spec.record_count_field}`")
    lines.append("")
    for title, specs in (("Header", spec.header), ("Record", spec.record)):
        if not specs:
            continue
        lines += [f"### {title}", "", "| Field | Type | Length | Description | Evidence |", "| --- | --- | --- | --- | --- |"]
        for s in specs:
            n = s.length if s.length is not None else (type_size(s.type) or "var")
            lines.append(f"| {s.name} | {s.type} | {n} | {s.desc} | {s.evidence} |")
        lines.append("")
    for n in spec.notes:
        lines.append(f"- {n}")
    return "\n".join(lines).rstrip() + "\n"
