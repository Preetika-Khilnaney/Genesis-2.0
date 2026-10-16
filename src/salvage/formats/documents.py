"""WPD (WordPerfect 5.x) and BRAVO (Xerox Alto editor) documents. OWNER: Bhupesh (real-world format).

Checked against real-samples s14-s17 (FIELD-LOG.md).

WPD
  Header: 0xFF "WPC", u32 text start, u8 product, u8 file type, u8 major, u8 minor,
          u16 encryption key (non-zero = password-protected -> status "unsupported"), u16 reserved.
  Packet index at 16: u16 type, u16 length, u32 offset (type 1 = document summary).
  Text from the text start to the first packet: 0x0A hard return (ends a paragraph), 0x0D soft
  return (a space), 0x0C hard page (page_break record), 0x09 tab, 0xA0 hard space, 0xA9-0xAB hard
  hyphen, 0xAC-0xAE soft hyphen (dropped), 0xC0-0xCF fixed-length codes (C3 xx C3 / C4 xx C4 =
  attribute on / off), 0xD0-0xFF variable-length codes (code, subcode, u16 length, body).
  s15's index says the text runs to byte 223 but the file is 136 bytes: truncated.

BRAVO
  Plain text, paragraphs terminated by CR (0x0D), then ^Z (0x1A), then the format runs:
  pad to an even file offset, u16 big-endian word count, runs of 6 bytes: u16 start, u16 length,
  u8 looks (bit1 bold, bit2 italic), u8 font (all big-endian). s16: "Alto users" bold,
  "Bold and italic" bold+italic. s17 declares 12 words but holds 15 bytes: last run cut off.
"""
from __future__ import annotations

import struct

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec
from ._common import D, damage, record

WPD_SPEC = FormatSpec(
    name="WPD", magic=b"\xffWPC",
    description="WordPerfect 5.x document: 16-byte prefix, packet index, text stream with function codes.",
    checksum="none (structure: text start, packet offsets inside the file)",
    header=[FieldSpec("ident", "bytes", 4, "FF 'WPC'", "s14, s15"),
            FieldSpec("text_start", "u32", desc="first text byte", evidence="48 in both samples"),
            FieldSpec("product", "u8", desc="1 = WordPerfect", evidence="s14"),
            FieldSpec("file_type", "u8", desc="0x0A = document", evidence="s14"),
            FieldSpec("major", "u8", desc="major version", evidence="s14"),
            FieldSpec("minor", "u8", desc="minor version", evidence="s14"),
            FieldSpec("encryption", "u16", desc="0 = not protected", evidence="0 in both samples")],
)
BRAVO_SPEC = FormatSpec(
    name="BRAVO",
    description="Xerox Alto Bravo document: CR-terminated paragraphs, ^Z, then big-endian format runs.",
    checksum="none (structure: run table length)",
    record=[FieldSpec("start", "u16be", desc="run start in the text", evidence="s16 4 = 'Alto users'"),
            FieldSpec("length", "u16be", desc="run length", evidence="s16 10, 15"),
            FieldSpec("looks", "u8", desc="bit1 bold, bit2 italic", evidence="s16 6 on 'Bold and italic'"),
            FieldSpec("font", "u8", desc="font number", evidence="0 in samples")],
)

FIXED_LEN = {0xC0: 4, 0xC1: 9, 0xC2: 11, 0xC3: 3, 0xC4: 3, 0xC5: 5, 0xC6: 6, 0xC7: 7}
ATTRS = {0x0C: "bold", 0x0E: "underline", 0x08: "italic", 0x0D: "double underline", 0x05: "small caps"}


@register
class WpdDecoder(Decoder):
    name = "WPD"
    spec = WPD_SPEC
    ready = True

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        if len(b) < 16:
            res.status = "failed"
            damage(res, D.TRUNCATED, 0, len(b), "file ends inside the 16-byte prefix")
            return res
        start = struct.unpack_from("<I", b, 4)[0]
        product, ftype, major, minor = b[8:12]
        key = struct.unpack_from("<H", b, 12)[0]
        meta = {"product": product, "file_type": ftype, "version": f"{major}.{minor}",
                "encrypted": bool(key), "text_offset": start}
        res.metadata = meta
        if key:
            res.status = "unsupported"
            damage(res, D.ENCRYPTED, 12, 14, "document is password-protected (non-zero encryption key); "
                   "the text is not decoded", lossy=True)
            return res
        if start < 16 or start > len(b):
            damage(res, D.OOB_POINTER, 4, 8, f"text start {start} is outside the file")
            res.status = "failed"
            return res
        # packet index: (type, length, offset) entries between 16 and the text start
        text_end, packets = len(b), []
        for o in range(16, start - 7, 2):
            t, ln, off = struct.unpack_from("<HHI", b, o)
            if t == 1 and start <= off and ln:
                packets.append((t, ln, off))
                break
        truncated = False
        if packets:
            _, ln, off = packets[0]
            if off > len(b):
                truncated = True
                damage(res, D.TRUNCATED, len(b), off, f"index says the text runs to byte {off} and a "
                       f"{ln}-byte summary follows, but the file is {len(b)} bytes")
            else:
                text_end = off
                if off + ln > len(b):
                    damage(res, D.TRUNCATED, off, len(b), "document summary cut off", lossy=False)
                else:
                    pk = b[off + 2:off + ln].split(b"\0")
                    meta["summary"] = [s.decode("cp437", "replace") for s in pk if s]
        self._text(res, b[start:text_end], start, truncated)
        return res

    @staticmethod
    def _text(res: FileResult, t: bytes, base: int, truncated: bool) -> None:
        cur, idx, i = [], 0, 0
        para_start = base

        def flush(kind="paragraph", complete=True):
            nonlocal cur, idx, para_start
            vals = {"index": idx, "type": kind, "text": "".join(cur) if kind == "paragraph" else ""}
            res.records.append(record(idx, para_start, vals, verified=complete,
                                      issues=[] if complete else ["truncated"]))
            idx, cur, para_start = idx + 1, [], base + i + 1

        while i < len(t):
            c = t[i]
            if c == 0x0A:
                flush()
            elif c == 0x0C:
                if cur:
                    flush()
                flush("page_break")
            elif c == 0x0D:
                cur.append(" ")
            elif c == 0x09:
                cur.append("\t")
            elif 0x20 <= c < 0x7F:
                cur.append(chr(c))
            elif c == 0xA0:
                cur.append(" ")
            elif c in (0xA9, 0xAA, 0xAB):
                cur.append("-")
            elif c in FIXED_LEN:
                n = FIXED_LEN[c]
                if c == 0xC0 and i + 3 < len(t):
                    ch = t[i + 1]
                    cur.append(chr(ch) if 0x20 <= ch < 0x7F else "�")
                if i + n > len(t):
                    damage(res, D.TRUNCATED, base + i, base + len(t), f"function code 0x{c:02X} cut off")
                    break
                i += n
                continue
            elif c >= 0xD0:
                if i + 4 > len(t):
                    damage(res, D.TRUNCATED, base + i, base + len(t), f"function code 0x{c:02X} cut off")
                    break
                ln = struct.unpack_from("<H", t, i + 2)[0]
                if i + 4 + ln > len(t):
                    damage(res, D.TRUNCATED, base + i, base + len(t), f"function code 0x{c:02X} cut off")
                    break
                i += 4 + ln
                continue
            # 0x00-0x1F others, 0x7F-0xBF single-byte codes: no text
            i += 1
        if cur:
            flush(complete=not truncated)


def _looks(v: int) -> list[str]:
    names = {1: "bit0", 2: "bold", 4: "italic", 8: "underline"}
    return [names.get(1 << k, f"bit{k}") for k in range(8) if v & (1 << k)]


@register
class BravoDecoder(Decoder):
    name = "BRAVO"
    spec = BRAVO_SPEC
    ready = True

    def sniff(self, data: bytes) -> float:
        z = data.find(b"\x1a")
        if z < 4 or b"\r" not in data[:z] or b"\n" in data[:z]:
            return 0.0
        text = data[:z]
        if not all(32 <= c < 127 or c in (9, 13) for c in text):
            return 0.0
        tail = data[z + 1:]
        return 0.7 if len(tail) <= 4096 else 0.0

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        z = b.find(b"\x1a")
        if z < 0:
            z = len(b)
            res.warnings.append("no ^Z terminator: no format runs")
        text = b[:z].decode("latin-1")
        paras = text.split("\r")
        tail_unterminated = paras[-1] if paras else ""
        paras = paras[:-1]
        for i, ptxt in enumerate(paras):
            res.records.append(record(i, None, {"index": i, "text": ptxt}))
        if tail_unterminated:
            res.records.append(record(len(paras), None, {"index": len(paras), "text": tail_unterminated},
                                      verified=False, issues=["truncated"]))
            damage(res, D.TRUNCATED, len(text) - len(tail_unterminated), len(text),
                   "last paragraph is not CR-terminated", lossy=False)
        runs: list[dict] = []
        res.metadata = {"text_length": z, "paragraphs": len(res.records), "format_runs": runs}
        if z >= len(b):
            return res
        p = z + 1
        if p % 2:
            p += 1                              # runs start at an even offset
        if p + 2 > len(b):
            if p < len(b) or z + 1 < len(b):
                damage(res, D.TRUNCATED, z + 1, len(b), "format run table header cut off")
            return res
        words = struct.unpack_from(">H", b, p)[0]
        want, have = words * 2, len(b) - p - 2
        q = p + 2
        while q + 6 <= p + 2 + min(want, have):
            s, ln, looks, font = struct.unpack_from(">HHBB", b, q)
            ok = s + ln <= z
            runs.append({"start": s, "length": ln, "looks": _looks(looks), "font": font})
            if not ok:
                damage(res, D.OOB_POINTER, q, q + 6, f"format run {s}+{ln} is past the end of the text",
                       lossy=False)
            q += 6
        if have < want:
            damage(res, D.TRUNCATED, q, len(b), f"format runs declare {want} bytes, {have} present; "
                   "the last run is cut off")
        elif have > want:
            damage(res, D.UNPARSED_BYTES, p + 2 + want, len(b), f"{have - want} bytes after the format runs",
                   lossy=False)
        return res
