"""Generic reader for block-structured formats. OWNER: Preetika (core). Used by Khushi.

Many formats are a sequence of blocks:

    [marker] [extra header fields] [length] [payload] [checksum]

Describe the layout once with BlockLayout and call read_blocks(). You get every block
with its status, plus DamageEntry records for everything that could not be trusted:

    layout = BlockLayout(marker=b"BLK", length_type="u16", checksum_algo="crc32",
                         checksum_type="u32", checksum_covers="payload",
                         extra=[FieldSpec("seq", "u16")])
    scan = read_blocks(data, layout, start=header_size)
    for b in scan.blocks:          # b.status: verified | corrected | lost
        ...decode b.payload with ByteReader...
    result.damage += scan.damage

Rules it enforces (same as everywhere else):
- A block is VERIFIED only if its checksum passes (UNVERIFIED if the format has no checksum).
- CORRECTED only when exactly one single-bit flip inside the payload fixes it.
- A failed block is LOST: its byte range is reported, and with a marker the reader resyncs
  on the next block whose checksum passes. Without a marker, the stored length is trusted
  to step forward, and a warning says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..recovery import crc
from .model import DamageCause, DamageEntry, Field, FieldStatus
from .reader import ByteReader, OutOfBounds
from .spec import FieldSpec, decode_fields


@dataclass
class BlockLayout:
    marker: bytes | None = None          # bytes every block starts with (enables resync)
    extra: list[FieldSpec] = field(default_factory=list)   # fields between marker and length
    length_type: str | None = "u16"      # type of the length field; None = fixed_size blocks
    fixed_size: int | None = None        # payload size when length_type is None
    length_counts: str = "payload"       # "payload": length = payload bytes; "block": whole block incl. marker
    length_adjust: int = 0               # add to the stored length (e.g. -2 if it counts itself)
    checksum_algo: str | None = None     # a name from recovery.crc.ALGORITHMS, or None
    checksum_type: str = "u32"           # how the stored checksum is encoded
    checksum_covers: str = "payload"     # "payload" or "all" (marker + extra + length + payload)
    endian: str = "little"
    max_payload: int = 16 * 1024 * 1024  # sanity cap: a larger length is treated as corrupt


@dataclass
class Block:
    index: int
    offset: int                          # first byte of the block (marker)
    end: int                             # one past the last byte (after checksum)
    payload_offset: int
    payload: bytes
    header: dict[str, Field]             # extra fields + length
    status: FieldStatus
    note: str = ""


@dataclass
class BlockScan:
    blocks: list[Block] = field(default_factory=list)
    damage: list[DamageEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def good(self) -> list[Block]:
        return [b for b in self.blocks if b.status in (FieldStatus.VERIFIED, FieldStatus.CORRECTED, FieldStatus.UNVERIFIED)]

    def coverage(self, total: int) -> float:
        """Share of `total` bytes inside verified or corrected blocks."""
        ok = sum(b.end - b.offset for b in self.blocks if b.status in (FieldStatus.VERIFIED, FieldStatus.CORRECTED))
        return ok / total if total else 0.0


class _Malformed(Exception):
    pass


def _parse(data: bytes, pos: int, L: BlockLayout) -> tuple[int, int, int, dict[str, Field], int | None, int]:
    """Parse one block at pos. Returns (payload_off, payload_len, end, header, stored_crc, crc_end).
    Raises OutOfBounds (truncated) or _Malformed (bad marker / implausible length)."""
    r = ByteReader(data, L.endian)
    r.seek(pos)
    if L.marker:
        if r.take(len(L.marker)) != L.marker:
            raise _Malformed("marker mismatch")
    header = decode_fields(r, L.extra)
    if L.length_type:
        lstart = r.pos
        raw_len = r.read(L.length_type)
        header["length"] = Field("length", raw_len, FieldStatus.UNVERIFIED, offset=lstart, length=r.pos - lstart)
        n = raw_len + L.length_adjust
        if L.length_counts == "block":
            ck = (_size(L.checksum_type) if L.checksum_algo else 0)
            n = n - (r.pos - pos) - ck
    else:
        if L.fixed_size is None:
            raise ValueError("BlockLayout needs length_type or fixed_size")
        n = L.fixed_size
    if n < 0 or n > L.max_payload:
        raise _Malformed(f"implausible payload length {n}")
    payload_off = r.pos
    r.take(n)                                   # bounds check on the payload
    stored = None
    crc_end = r.pos
    if L.checksum_algo:
        stored = r.read(L.checksum_type)
    return payload_off, n, r.pos, header, stored, crc_end


def _size(type_name: str) -> int:
    from .reader import type_size
    s = type_size(type_name)
    if s is None:
        raise ValueError(f"checksum type {type_name!r} must be fixed size")
    return s


def _covered(data: bytes, start: int, payload_off: int, crc_end: int, L: BlockLayout) -> tuple[bytes, int]:
    """Bytes the checksum covers, and where the payload starts inside them."""
    if L.checksum_covers == "all":
        return data[start:crc_end], payload_off - start
    return data[payload_off:crc_end], 0


def _valid_at(data: bytes, pos: int, L: BlockLayout) -> bool:
    try:
        payload_off, n, end, header, stored, crc_end = _parse(data, pos, L)
    except (OutOfBounds, _Malformed):
        return False
    if not L.checksum_algo:
        return True
    covered, _ = _covered(data, pos, payload_off, crc_end, L)
    return crc.check(L.checksum_algo, covered, stored)


def _resync(data: bytes, after: int, L: BlockLayout) -> int | None:
    i = after
    while True:
        i = data.find(L.marker, i)
        if i < 0:
            return None
        if _valid_at(data, i, L):
            return i
        i += 1


def read_blocks(data: bytes, layout: BlockLayout, start: int = 0, max_blocks: int = 1_000_000) -> BlockScan:
    L = layout
    scan = BlockScan()
    pos, idx = start, 0
    while pos < len(data) and idx < max_blocks:
        try:
            payload_off, n, end, header, stored, crc_end = _parse(data, pos, L)
        except OutOfBounds:
            # Either the file really ends here, or the length field is corrupt and points past
            # the end. A later valid block proves the second case.
            nxt = _resync(data, pos + 1, L) if L.marker else None
            if nxt is None:
                scan.damage.append(DamageEntry(pos, len(data), DamageCause.TRUNCATED,
                                               f"file ends inside block {idx}", [f"block {idx}"]))
                break
            scan.damage.append(DamageEntry(pos, nxt, DamageCause.BAD_LENGTH,
                                           f"block {idx} length runs past the end of the file; "
                                           f"resynced at offset {nxt}", [f"block {idx}"]))
            pos, idx = nxt, idx + 1
            continue
        except _Malformed as e:
            nxt = _resync(data, pos + 1, L) if L.marker else None
            stop = nxt if nxt is not None else len(data)
            scan.damage.append(DamageEntry(pos, stop, DamageCause.BAD_OFFSET,
                                           f"no valid block at offset {pos} ({e})"
                                           + ("" if nxt is not None else "; no further valid block"),
                                           [f"block {idx}"]))
            if nxt is None:
                break
            pos, idx = nxt, idx + 1
            continue

        payload = data[payload_off:payload_off + n]
        if not L.checksum_algo:
            status, note = FieldStatus.UNVERIFIED, "format has no checksum"
        else:
            covered, poff = _covered(data, pos, payload_off, crc_end, L)
            if crc.check(L.checksum_algo, covered, stored):
                status, note = FieldStatus.VERIFIED, f"{L.checksum_algo} ok"
            else:
                fix = crc.single_bit_fix(L.checksum_algo, covered, stored)
                if fix is not None and poff * 8 <= fix[1] < (poff + n) * 8:
                    fixed, bit = fix
                    payload = fixed[poff:poff + n]
                    status = FieldStatus.CORRECTED
                    note = f"single-bit fix at payload byte {bit // 8 - poff}, bit {bit % 8}"
                else:
                    status, note = FieldStatus.LOST, f"{L.checksum_algo} mismatch"

        if status == FieldStatus.LOST:
            # Payload cannot be trusted; neither can its length. Resync if we can.
            nxt = _resync(data, pos + 1, L) if L.marker else None
            if L.marker:
                stop = nxt if nxt is not None else len(data)
            else:
                stop = end
                scan.warnings.append(f"block {idx} failed its checksum; no marker, so its stored length was trusted to continue")
            scan.damage.append(DamageEntry(pos, stop, DamageCause.CRC_FAIL, note, [f"block {idx}"]))
            scan.blocks.append(Block(idx, pos, end, payload_off, b"", header, status, note))
            if L.marker and nxt is None:
                break
            pos = nxt if L.marker else end
            idx += 1
            continue

        for f in header.values():
            f.status = status if status != FieldStatus.CORRECTED else FieldStatus.VERIFIED
        scan.blocks.append(Block(idx, pos, end, payload_off, payload, header, status, note))
        pos, idx = end, idx + 1
    return scan


def block_structure_score(data: bytes, layout: BlockLayout, start: int = 0) -> float:
    """For Decoder.structure_score(): 1.0 when checksummed blocks cover all of data[start:]."""
    if not layout.checksum_algo or len(data) <= start:
        return 0.0
    scan = read_blocks(data, layout, start)
    if scan.damage:
        return 0.0
    return scan.coverage(len(data) - start) if len(data) - start else 0.0
