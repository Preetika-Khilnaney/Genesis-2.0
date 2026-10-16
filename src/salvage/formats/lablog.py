"""LABLOG: benchtop analytical-instrument data logger (early 1990s). OWNER: Khushi (recovery).

Layout, worked out from real-samples s05-s07 and expected_outputs/s05 (evidence in FIELD-LOG.md):

  Header (32 bytes, little-endian)
    0  4  magic "LLOG"            4  1  version            5  1  channel count
    6  2  sample interval in 10 ms units (50 -> 500 ms)
    8  16 instrument name, NUL padded
    24 4  start time, seconds since 1990-01-01 UTC
    28 2  declared block count    30 2  CRC-16/CCITT-FALSE of bytes 0..29
  Blocks (from offset 32)
    0xB1, u8 type, u16 length, payload, u16 CRC-16/CCITT-FALSE over (type, length, payload)
    type 3  channels: per channel  unit[4] (NUL padded), f32 scale, f32 offset
    type 1  data:  u16 first sample, u8 n, then n x channels i16 raw; value = raw*scale + offset;
            raw 0x8000 = dropout -> null
    type 2  event: u16 sample, u8 severity, u8 length + message

A block whose CRC fails is repaired only when exactly one flipped bit explains it (provable for
CRC-16 on blocks this size); otherwise its samples are output as verified=false. Truncated and
unknown blocks are reported; the parser resyncs on the next 0xB1 whose CRC checks out.
"""
from __future__ import annotations

import datetime as dt
import struct

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec
from ..recovery.crc import crc16_ccitt
from ._common import D, damage, record

MAGIC = b"LLOG"
MARKER = 0xB1
EPOCH = dt.datetime(1990, 1, 1, tzinfo=dt.timezone.utc)
DROPOUT = -32768
T_DATA, T_EVENT, T_CHANNELS = 1, 2, 3

LABLOG_SPEC = FormatSpec(
    name="LABLOG",
    magic=MAGIC,
    description=("Instrument log: 32-byte header with its own CRC-16, then CRC-16-protected blocks "
                 "(channels, data, events)."),
    checksum="CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF), little-endian, over type+length+payload; "
             "header CRC over bytes 0..29",
    header=[
        FieldSpec("magic", "bytes", 4, "'LLOG'", "all samples"),
        FieldSpec("version", "u8", desc="format version", evidence="1 in all samples"),
        FieldSpec("channels", "u8", desc="channel count", evidence="matches channel block size"),
        FieldSpec("interval", "u16", desc="sample interval / 10 ms", evidence="50 -> 500 ms (expected s05)"),
        FieldSpec("instrument", "str", 16, "instrument name", "expected s05"),
        FieldSpec("start", "u32", desc="seconds since 1990-01-01 UTC", evidence="-> 1992-10-11T05:07:43Z (expected s05)"),
        FieldSpec("declared_block_count", "u16", desc="blocks that follow", evidence="7 / 8 / 8, matches s05-s07"),
        FieldSpec("header_crc", "u16", desc="CRC-16/CCITT-FALSE of bytes 0..29", evidence="holds on s05-s07"),
    ],
    record=[
        FieldSpec("marker", "u8", desc="0xB1", evidence="every block"),
        FieldSpec("type", "u8", desc="1 data, 2 event, 3 channels", evidence="payload shapes"),
        FieldSpec("length", "u16", desc="payload length", evidence="tiles blocks exactly"),
        FieldSpec("crc", "u16", desc="CRC-16/CCITT-FALSE of type+length+payload", evidence="holds on 22 of 23 blocks"),
    ],
    notes=["Data payload: u16 first_sample, u8 n, n x channels i16; 0x8000 = dropout (null).",
           "Channels payload: per channel unit[4], f32 scale, f32 offset; value = raw*scale + offset."],
)


def _block_ok(b: bytes, p: int) -> bool:
    if p + 6 > len(b) or b[p] != MARKER:
        return False
    L = struct.unpack_from("<H", b, p + 2)[0]
    return p + 6 + L <= len(b) and crc16_ccitt(b[p + 1:p + 4 + L]) == struct.unpack_from("<H", b, p + 4 + L)[0]


def _single_bit_fix(covered: bytes, stored: int) -> tuple[bytes, int] | None:
    hits = []
    for bit in range(len(covered) * 8):
        c = bytearray(covered)
        c[bit // 8] ^= 1 << (bit % 8)
        if crc16_ccitt(bytes(c)) == stored:
            hits.append((bytes(c), bit))
            if len(hits) > 1:
                return None
    return hits[0] if hits else None


@register
class LablogDecoder(Decoder):
    name = "LABLOG"
    spec = LABLOG_SPEC
    ready = True

    def structure_score(self, data: bytes) -> float:
        return 1.0 if _block_ok(data, 32) and len(data) >= 38 else 0.0

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        if len(b) < 32:
            res.status = "failed"
            damage(res, D.TRUNCATED, 0, len(b), f"file is {len(b)} bytes; the LABLOG header needs 32")
            return res
        ver, nch, iv = b[4], b[5], struct.unpack_from("<H", b, 6)[0]
        inst = b[8:24].split(b"\0")[0].decode("latin-1")
        start, nblocks, hcrc = struct.unpack_from("<IHH", b, 24)
        interval = iv * 10
        meta = {"version": ver, "instrument": inst, "sample_interval_ms": interval, "channels": [],
                "start_time_utc": (EPOCH + dt.timedelta(seconds=start)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "declared_block_count": nblocks, "events": []}
        res.metadata = meta
        header_ok = crc16_ccitt(b[:30]) == hcrc
        if not header_ok:
            damage(res, D.HEADER_CHECKSUM, 0, 32, "header CRC does not match; header values (interval, "
                   "channel count, start time) and everything computed from them are unverified")
        channels_ok = False

        scales: list[tuple[float, float]] = []
        p, nblk, seen, truncated = 32, 0, set(), False
        pending_data: list[tuple[int, bytes, bool, list[str]]] = []
        while p < len(b):
            if b[p] != MARKER:
                nxt = next((q for q in range(p + 1, len(b)) if _block_ok(b, q)), None)
                stop = nxt if nxt is not None else len(b)
                damage(res, D.UNPARSED_BYTES, p, stop, f"{stop - p} bytes at offset {p} are not a valid block")
                if nxt is None:
                    break
                p = nxt
                continue
            if p + 4 > len(b):
                damage(res, D.TRUNCATED, p, len(b), f"file ends inside block {nblk} header")
                truncated = True
                break
            t, L = b[p + 1], struct.unpack_from("<H", b, p + 2)[0]
            end = p + 6 + L
            if end > len(b):
                nxt = next((q for q in range(p + 1, len(b)) if _block_ok(b, q)), None)
                if nxt is not None:      # length is corrupt, not the file: skip to the next good block
                    damage(res, D.BAD_LENGTH, p, nxt, f"block {nblk}: length {L} runs past the end; resynced")
                    p, nblk = nxt, nblk + 1
                    continue
                damage(res, D.TRUNCATED, p, len(b), f"file ends inside block {nblk} (type {t}): "
                       f"{len(b) - p} of {L + 6} bytes present", affected=[f"block {nblk}"])
                if t == T_DATA:
                    pending_data.append((p, b[p + 4:], False, ["truncated"]))
                truncated = True
                break
            covered, stored = b[p + 1:p + 4 + L], struct.unpack_from("<H", b, p + 4 + L)[0]
            ok, issues = crc16_ccitt(covered) == stored, []
            payload = b[p + 4:p + 4 + L]
            if not ok:
                fix = _single_bit_fix(covered, stored)
                if fix is not None:
                    fixed, bit = fix
                    t = fixed[0]                     # the repaired type byte, not the damaged one
                    payload = fixed[3:]
                    issues = ["crc_mismatch"]
                    damage(res, D.CRC_MISMATCH, p, end, f"block {nblk}: CRC mismatch repaired: exactly one "
                           f"flipped bit (block byte {bit // 8 + 1}, bit {bit % 8}) explains it", lossy=False)
                    ok = True
                else:
                    issues = ["crc_mismatch"]
                    damage(res, D.CRC_MISMATCH, p, end, f"block {nblk} (type {t}): CRC mismatch; "
                           "its values are output unverified", affected=[f"block {nblk}"])
            if t == T_CHANNELS:
                channels_ok = ok
                scales = []
                meta["channels"] = []
                for i in range(L // 12):
                    unit = payload[12 * i:12 * i + 4].split(b"\0")[0].decode("latin-1")
                    sc, of = struct.unpack_from("<ff", payload, 12 * i + 4)
                    scales.append((sc, of))
                    meta["channels"].append({"index": i, "unit": unit})
                if len(scales) != nch:
                    damage(res, D.COUNT_MISMATCH, p, end, f"header says {nch} channels, channel block has "
                           f"{len(scales)}", lossy=False)
            elif t == T_DATA:
                pending_data.append((p, payload, ok, issues))
            elif t == T_EVENT and len(payload) >= 4:
                ml = payload[3]
                meta["events"].append({"sample": struct.unpack_from("<H", payload, 0)[0],
                                       "severity": payload[2],
                                       "message": payload[4:4 + ml].decode("latin-1")})
            else:
                damage(res, D.UNKNOWN_RECORD, p, end, f"block {nblk}: unknown block type {t} ({L} bytes) skipped",
                       lossy=not ok)
            p, nblk = end, nblk + 1

        nchan = len(scales) or nch
        if nchan == 0:
            if pending_data:
                damage(res, D.INVALID_VALUE, 5, 6, "channel count is 0: data blocks cannot be split into values")
            return res
        if not scales:
            scales = [(1.0, 0.0)] * nch
            damage(res, D.INDEX_MISSING, 32, 32, "no channel block: values are raw, uncalibrated")
        for p0, payload, verified, issues in pending_data:
            if len(payload) < 3:
                continue
            first, n = struct.unpack_from("<H", payload, 0)[0], payload[2]
            have = (len(payload) - 3) // (2 * nchan)
            if have < n and "truncated" not in issues:
                issues = issues + ["bad_length"]
                verified = False
            if not header_ok and "header_checksum" not in issues:
                issues = issues + ["header_checksum"]
                verified = False
            if not channels_ok and "index_missing" not in issues:
                issues = issues + ["index_missing"]      # calibration (channel block) missing or unverified
                verified = False
            for i in range(min(n, have)):
                s = first + i
                vals = []
                for c in range(nchan):
                    raw = struct.unpack_from("<h", payload, 3 + 2 * (i * nchan + c))[0]
                    sc, of = scales[c] if c < len(scales) else (1.0, 0.0)
                    vals.append(None if raw == DROPOUT else round(raw * sc + of, 6))
                dup = s in seen
                seen.add(s)
                rec_issues = list(issues) + (["invalid_value"] if dup else [])
                res.records.append(record(s, p0, {"sample": s, "time_ms": s * interval, "values": vals},
                                          verified=verified and not dup and "truncated" not in issues,
                                          issues=rec_issues))
        if nblk != nblocks and not truncated:
            damage(res, D.COUNT_MISMATCH, 28, 30, f"header declares {nblocks} blocks, file holds {nblk}",
                   lossy=nblk < nblocks)
        return res
