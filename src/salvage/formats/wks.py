"""WKS: Lotus 1-2-3 worksheet (DOS, early 1990s). OWNER: Bhupesh (real-world format).

Public format, checked against real-samples s11-s13 and expected_outputs/s11 (FIELD-LOG.md).
The documentation is a starting hypothesis; where the bytes disagree, the bytes win.

  Records: u16 opcode, u16 length, body (little-endian). BOF (0x0000, version) first, EOF (0x0001) last.
  0x0006 RANGE    u16 first col, first row, last col, last row       -> metadata.declared_range
  0x0008 COLW     u16 col, u8 width                                  -> metadata.column_widths
  Cells start with u8 format, u16 col, u16 row:
  0x000C BLANK    -                                    0x000D INTEGER  i16
  0x000E NUMBER   f64                                  0x000F LABEL    prefix char + NUL text
  0x0010 FORMULA  f64 cached value, u16 length, formula bytes (kept as hex: formula_raw_hex)
  Label prefix: ' left, " right, ^ center, \\ repeat.
  Format byte: bit7 protected, bits 4-6 type (0 fixed, 1 sci, 2 currency, 3 percent, 4 comma,
  7 special), bits 0-3 decimals or special subtype (special 2/3/4 = dates, serial from 1899-12-30).

No checksum: a record is verified when its length is exactly right for its opcode and it lies
inside the file. A cell written twice keeps the last value (as 1-2-3 loads it) and is warned about.
"""
from __future__ import annotations

import datetime as dt
import struct

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec
from ._common import D, col_name, damage, record

BOF, EOF, RANGE, COLW, BLANK, INTEGER, NUMBER, LABEL, FORMULA = 0, 1, 6, 8, 0x0C, 0x0D, 0x0E, 0x0F, 0x10
KNOWN_OTHER = {0x02, 0x03, 0x04, 0x05, 0x07, 0x09, 0x0A, 0x0B, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E,
               0x1F, 0x20, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31}
ALIGN = {"'": "left", '"': "right", "^": "center", "\\": "repeat"}
FMT_TYPES = {0: "fixed", 1: "scientific", 2: "currency", 3: "percent", 4: "comma"}
SPECIAL = {0: "+/-", 1: "general", 2: "date_dd_mmm_yy", 3: "date_dd_mmm", 4: "date_mmm_yy", 5: "text",
           6: "hidden", 7: "time", 15: "default"}

WKS_SPEC = FormatSpec(
    name="WKS",
    magic=bytes.fromhex("00000200"),        # BOF opcode 0, length 2
    description="Lotus 1-2-3 worksheet: a stream of opcode/length/body records from BOF to EOF.",
    checksum="none (structure only)",
    header=[FieldSpec("bof", "u16", desc="opcode 0x0000, length 2", evidence="all samples"),
            FieldSpec("version_code", "u16", desc="0x0404 = WKS", evidence="expected s11")],
    record=[FieldSpec("opcode", "u16", desc="record type", evidence="Lotus documentation, checked on samples"),
            FieldSpec("length", "u16", desc="body length", evidence="records tile the file exactly"),
            FieldSpec("format", "u8", desc="cell format byte", evidence="0xFF default / 0x22 currency,2"),
            FieldSpec("col", "u16", desc="0-based column", evidence="expected s11"),
            FieldSpec("row", "u16", desc="0-based row", evidence="expected s11")],
)


def _number_format(fmt: int) -> str | None:
    kind, low = (fmt >> 4) & 7, fmt & 0x0F
    if fmt == 0xFF or (kind == 7 and low in (1, 15)):
        return None                                   # default / general
    if kind == 7:
        return SPECIAL.get(low, f"special_{low}")
    return f"{FMT_TYPES.get(kind, f'type_{kind}')}:{low}"


def _is_date(fmt: int) -> bool:
    return ((fmt >> 4) & 7) == 7 and (fmt & 0x0F) in (2, 3, 4)


def _serial_to_iso(v: float) -> str | None:
    try:
        days = int(v)
        if days <= 0:
            return None
        base = dt.date(1899, 12, 31) if days < 60 else dt.date(1899, 12, 30)   # 1-2-3's 1900 leap-year bug
        return (base + dt.timedelta(days=days)).isoformat()
    except (OverflowError, ValueError):
        return None


EXACT_LEN = {BOF: 2, EOF: 0, RANGE: 8, COLW: 3, BLANK: 5, INTEGER: 7, NUMBER: 13}


@register
class WksDecoder(Decoder):
    name = "WKS"
    spec = WKS_SPEC
    ready = True

    def sniff(self, data: bytes) -> float:
        if len(data) >= 6 and data[:4] == b"\x00\x00\x02\x00" and data[4:6] in (b"\x04\x04", b"\x05\x04", b"\x06\x04"):
            return 1.0
        return 0.0

    def near_magic(self, data: bytes, max_diff: int = 2):
        """The BOF signature (00 00 02 00) is too generic for damaged-magic matching: a run of
        zeros would 'nearly' match. WKS relies on sniff() (BOF + version code) only."""
        return None

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        meta: dict = {"version_code": None, "declared_range": None, "column_widths": {}}
        res.metadata = meta
        cells: dict[tuple[int, int], int] = {}
        p, seen_eof, n = 0, False, 0
        while p < len(b):
            if p + 4 > len(b):
                damage(res, D.TRUNCATED, p, len(b), f"file ends inside a record header at offset {p}")
                break
            op, L = struct.unpack_from("<HH", b, p)
            end = p + 4 + L
            if end > len(b):
                what = "a cell" if op in (BLANK, INTEGER, NUMBER, LABEL, FORMULA) else f"record 0x{op:04x}"
                damage(res, D.TRUNCATED, p, len(b), f"file ends inside {what} at offset {p}: "
                       f"{len(b) - p - 4} of {L} body bytes present")
                break
            body = b[p + 4:end]
            if op in EXACT_LEN and L != EXACT_LEN[op]:
                damage(res, D.BAD_LENGTH, p, end, f"record 0x{op:04x} has length {L}, expected {EXACT_LEN[op]}")
                p, n = end, n + 1
                continue
            if op == BOF:
                meta["version_code"] = f"0x{struct.unpack_from('<H', body)[0]:04x}"
                if n != 0:
                    res.warnings.append("BOF is not the first record")
            elif op == EOF:
                seen_eof = True
                if end < len(b):
                    damage(res, D.UNPARSED_BYTES, end, len(b), f"{len(b) - end} bytes after EOF", lossy=False)
                break
            elif op == RANGE:
                c0, r0, c1, r1 = struct.unpack_from("<HHHH", body)
                meta["declared_range"] = f"{col_name(c0)}{r0 + 1}:{col_name(c1)}{r1 + 1}"
            elif op == COLW:
                c, w = struct.unpack_from("<HB", body)
                meta["column_widths"][col_name(c)] = w
            elif op in (BLANK, INTEGER, NUMBER, LABEL, FORMULA):
                v = self._cell(op, body)
                if v is None:
                    damage(res, D.BAD_LENGTH, p, end, f"cell record 0x{op:04x} at {p} is malformed ({L} bytes)")
                else:
                    key = (v["row"], v["col"])
                    if key in cells:
                        res.warnings.append(f"cell {v['cell']} written twice; the later value is kept")
                        res.records[cells[key]] = record(len(res.records), p, v)
                        res.records[cells[key]].index = cells[key]
                    else:
                        cells[key] = len(res.records)
                        res.records.append(record(len(res.records), p, v))
            elif op not in KNOWN_OTHER:
                damage(res, D.UNKNOWN_RECORD, p, end, f"unknown record type 0x{op:04x} ({L} bytes) skipped",
                       lossy=False)
            p, n = end, n + 1
        if not seen_eof and not any(d.cause == D.TRUNCATED for d in res.damage):
            damage(res, D.TRUNCATED, len(b), len(b), "EOF record missing", lossy=False)
        if meta["version_code"] is None:
            res.status = "failed"
        return res

    @staticmethod
    def _cell(op: int, body: bytes) -> dict | None:
        if len(body) < 5:
            return None
        fmt, col, row = struct.unpack_from("<BHH", body)
        v: dict = {"cell": f"{col_name(col)}{row + 1}", "row": row, "col": col}
        rest = body[5:]
        if op == BLANK:
            v.update(type="blank", value=None)
        elif op == INTEGER:
            v.update(type="integer", value=struct.unpack("<h", rest)[0])
        elif op == NUMBER:
            v.update(type="number", value=struct.unpack("<d", rest)[0])
        elif op == LABEL:
            if not rest or rest[-1] != 0:
                return None
            text = rest[:-1].decode("cp437", "replace")
            pre = text[:1]
            v.update(type="label", value=text[1:] if pre in ALIGN else text,
                     alignment=ALIGN.get(pre, "left"))
        elif op == FORMULA:
            if len(rest) < 10:
                return None
            cached, flen = struct.unpack_from("<dH", rest)
            if len(rest) != 10 + flen:
                return None
            v.update(type="formula", cached_value=cached, formula_raw_hex=rest[10:10 + flen].hex())
        nf = _number_format(fmt)
        if nf and op != LABEL:
            v["number_format"] = nf
        if _is_date(fmt) and op in (INTEGER, NUMBER, FORMULA):
            v["iso_date"] = _serial_to_iso(v.get("value", v.get("cached_value")) or 0)
        return v
