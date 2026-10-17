"""EBCDIC-DUMP: university mainframe tape dump (1999). OWNER: Bhupesh (real-world format).

Checked against real-samples s20-s22 and expected_outputs/s20 (FIELD-LOG.md). Text is EBCDIC
code page 037. IBM variable-length records: each record starts with an RDW (u16 big-endian length
including the 4-byte RDW, then 2 zero bytes). Some tapes also group records into blocks, each with
a BDW of the same shape (s21).

  H  header   'H', title (20), run date YYYYMMDD (8)
  D  detail   'D', student id (6), name (20), dob packed-decimal P5 (YYYYMMDD),
              gpa P3 (2 decimals), credits u16 big-endian binary, status (1), balance P4 (2 decimals,
              signed: sign nibble C/F = +, D = -), 2 filler bytes
  T  trailer  'T', record count P4, credits total P5

Verification: every packed field must have valid digits and sign; the trailer count and credits
total must agree with the detail records (they cross-check the whole file).
"""
from __future__ import annotations

import datetime as dt
import struct

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec
from ._common import D, damage, record

E = "cp037"
H, DET, T = 0xC8, 0xC4, 0xE3          # 'H' 'D' 'T' in EBCDIC
DETAIL_LEN, HEADER_LEN, TRAILER_LEN = 44, 29, 10

EBCDIC_SPEC = FormatSpec(
    name="EBCDIC-DUMP",
    description="Mainframe tape dump: EBCDIC (cp037) variable-length records with RDWs, optionally "
                "blocked with BDWs; header, student detail records with packed-decimal fields, trailer.",
    checksum="trailer: record count and credits total cross-check the detail records",
    record=[FieldSpec("rdw", "u16be", desc="record length incl. RDW, then 00 00", evidence="tiles s20/s22"),
            FieldSpec("type", "bytes", 1, "H / D / T", "all samples"),
            FieldSpec("student_id", "str", 6, "EBCDIC digits", "expected s20"),
            FieldSpec("name", "str", 20, "EBCDIC, space padded", "expected s20"),
            FieldSpec("dob", "bytes", 5, "packed decimal YYYYMMDD", "01 97 81 01 1F -> 1978-10-11"),
            FieldSpec("gpa", "bytes", 3, "packed decimal, 2 decimals", "00 26 3C -> 2.63"),
            FieldSpec("credits", "u16be", desc="binary", evidence="00 28 -> 40"),
            FieldSpec("status", "str", 1, "EBCDIC letter", "expected s20"),
            FieldSpec("balance", "bytes", 4, "packed decimal, 2 decimals, signed", "00 69 83 6C -> 698.36")],
    notes=["s21 wraps records in blocks: BDW (u16be length, 00 00) then RDW records.",
           "Trailer count and credits total equal the sums over detail records in s20 and s21."],
)


def packed(bs: bytes) -> tuple[int | None, bool]:
    """IBM packed decimal -> (integer, ok)."""
    if not bs:
        return None, False
    digits = []
    for i, c in enumerate(bs):
        hi, lo = c >> 4, c & 15
        if hi > 9:
            return None, False
        digits.append(hi)
        if i < len(bs) - 1:
            if lo > 9:
                return None, False
            digits.append(lo)
        else:
            sign = lo
    if sign not in (0xA, 0xB, 0xC, 0xD, 0xE, 0xF):
        return None, False
    v = int("".join(map(str, digits)) or "0")
    return (-v if sign in (0xB, 0xD) else v), True


def _date(v: int | None) -> str | None:
    if v is None:
        return None
    s = f"{v:08d}"
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8])).isoformat()
    except ValueError:
        return None


def _rdw_ok(b: bytes, p: int) -> bool:
    return p + 5 <= len(b) and b[p + 2:p + 4] == b"\0\0" and struct.unpack_from(">H", b, p)[0] >= 5


def _blocked(b: bytes) -> bool:
    """BDW + RDW at the start (s21) rather than an RDW straight away (s20, s22)."""
    return (_rdw_ok(b, 0) and b[4] not in (H, DET, T) and _rdw_ok(b, 4) and b[8] in (H, DET, T)
            and struct.unpack_from(">H", b, 4)[0] <= struct.unpack_from(">H", b, 0)[0] - 4)


@register
class EbcdicDecoder(Decoder):
    name = "EBCDIC-DUMP"
    spec = EBCDIC_SPEC
    ready = True

    def sniff(self, data: bytes) -> float:
        if _rdw_ok(data, 0) and data[4] == H and data[5:25].decode(E, "replace").strip().isprintable():
            return 0.9
        if len(data) >= 9 and _blocked(data) and data[8] == H:
            return 0.9
        return 0.0

    def _records(self, res: FileResult, b: bytes):
        """Yield (offset, record bytes after the RDW, complete?) across blocked/unblocked layouts."""
        blocked = _blocked(b)
        res.metadata["blocked"] = blocked
        regions = []
        if blocked:
            p = 0
            while p + 4 <= len(b):
                bl = struct.unpack_from(">H", b, p)[0]
                if bl < 4 or b[p + 2:p + 4] != b"\0\0":
                    damage(res, D.BAD_LENGTH, p, len(b), f"invalid block descriptor at {p}")
                    break
                end = min(len(b), p + bl)
                if p + bl > len(b):
                    damage(res, D.TRUNCATED, p, len(b), f"file ends inside a block at {p}")
                regions.append((p + 4, end))
                p += bl
        else:
            regions.append((0, len(b)))
        for start, end in regions:
            p = start
            while p < end:
                if p + 4 > end:
                    damage(res, D.TRUNCATED, p, end, f"file ends inside a record descriptor at {p}")
                    return
                L = struct.unpack_from(">H", b, p)[0]
                if L < 5 or b[p + 2:p + 4] != b"\0\0":
                    damage(res, D.BAD_LENGTH, p, end, f"invalid record descriptor at {p}")
                    break
                if p + L > end:
                    damage(res, D.TRUNCATED, p, end, f"file ends inside a record at {p}: "
                           f"{end - p} of {L} bytes present")
                    yield p, b[p + 4:end], False
                    return
                yield p, b[p + 4:p + L], True
                p += L

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        meta = {"title": None, "run_date": None, "trailer_count": None, "trailer_credits_total": None}
        res.metadata = meta
        details, credits_sum, trailer_seen = 0, 0, False
        for p, rec, complete in self._records(res, data):
            t = rec[0] if rec else None
            if t == H:
                if len(rec) != HEADER_LEN and complete:
                    damage(res, D.BAD_LENGTH, p, p + 4 + len(rec), f"header record is {len(rec)} bytes")
                meta["title"] = rec[1:21].decode(E, "replace").strip()
                rd = rec[21:29].decode(E, "replace")
                meta["run_date"] = _date(int(rd)) if rd.isdigit() and len(rd) == 8 else None
            elif t == DET:
                v, issues = self._detail(rec)
                if not complete:
                    issues.append("truncated")
                elif len(rec) != DETAIL_LEN:
                    issues.append("bad_length")
                    damage(res, D.BAD_LENGTH, p, p + 4 + len(rec), f"detail record is {len(rec)} bytes, expected {DETAIL_LEN}")
                for i in issues:
                    if i == "invalid_value":
                        damage(res, D.INVALID_VALUE, p, p + 4 + len(rec),
                               f"detail {v.get('student_id')}: invalid packed-decimal field")
                        break
                res.records.append(record(details, p, v, verified=not issues, issues=issues))
                details += 1
                credits_sum += v["credits"] or 0
            elif t == T:
                trailer_seen = True
                cnt, ok1 = packed(rec[1:5])
                tot, ok2 = packed(rec[5:10])
                meta["trailer_count"], meta["trailer_credits_total"] = cnt, tot
                if not (ok1 and ok2):
                    damage(res, D.INVALID_VALUE, p, p + 4 + len(rec), "trailer packed fields are invalid")
                else:
                    if cnt != details:
                        damage(res, D.COUNT_MISMATCH, p, p + 4 + len(rec),
                               f"trailer counts {cnt} records, file holds {details}")
                    if tot != credits_sum:
                        damage(res, D.CHECKSUM_MISMATCH, p, p + 4 + len(rec),
                               f"trailer credits total {tot} != sum of details {credits_sum}")
            elif rec:
                damage(res, D.UNKNOWN_RECORD, p, p + 4 + len(rec), f"unknown record type {rec[:1].decode(E, 'replace')!r}",
                       lossy=False)
        bad_trailer = any(d.cause in (D.COUNT_MISMATCH, D.CHECKSUM_MISMATCH) for d in res.damage)
        if bad_trailer:
            # the trailer proves at least one detail is wrong or missing, but not which: none is verified
            for r in res.records:
                r.verified = False
                r.issues.append("checksum_mismatch")
        if not trailer_seen and not any(d.cause == D.TRUNCATED for d in res.damage):
            damage(res, D.TRUNCATED, len(data), len(data), "trailer record missing")
        meta.pop("blocked", None)
        return res

    @staticmethod
    def _detail(rec: bytes) -> tuple[dict, list[str]]:
        issues: list[str] = []
        v = {"student_id": rec[1:7].decode(E, "replace") if len(rec) >= 7 else None,
             "name": rec[7:27].decode(E, "replace").rstrip() if len(rec) >= 27 else None,
             "dob": None, "gpa": None, "credits": None, "status": None, "balance": None}
        if len(rec) >= 32:
            dob, ok = packed(rec[27:32])
            v["dob"] = _date(dob) if ok else None
            if not ok or v["dob"] is None:
                issues.append("invalid_value")
        if len(rec) >= 35:
            g, ok = packed(rec[32:35])
            v["gpa"] = g / 100 if ok else None
            if not ok:
                issues.append("invalid_value")
        if len(rec) >= 37:
            v["credits"] = struct.unpack_from(">H", rec, 35)[0]
        if len(rec) >= 38:
            v["status"] = rec[37:38].decode(E, "replace")
        if len(rec) >= 42:
            bal, ok = packed(rec[38:42])
            v["balance"] = bal / 100 if ok else None
            if not ok:
                issues.append("invalid_value")
        if not _plausible(v):
            issues.append("invalid_value")
        return v, issues


NAME_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ ,.'-")
STATUSES = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _plausible(v: dict) -> bool:
    """No per-record checksum, so check every value's shape: digits, letters, real dates, ranges."""
    sid, name = v.get("student_id") or "", v.get("name") or ""
    if not (len(sid) == 6 and sid.isdigit()):
        return False
    if not name or not all(c in NAME_OK for c in name) or "," not in name:
        return False
    if v.get("dob") and not ("1900" <= v["dob"][:4] <= "2010"):
        return False
    if v.get("gpa") is not None and not (0 <= v["gpa"] <= 4.0):
        return False
    if v.get("credits") is not None and v["credits"] > 400:
        return False
    if v.get("status") is not None and v["status"] not in STATUSES:
        return False
    if v.get("balance") is not None and abs(v["balance"]) > 100000:
        return False
    return True
