"""CVT: GEOS "Convert" file, a Commodore 64 disk-image conversion. OWNER: Bhupesh (real-world format).

Checked against real-samples s18-s19 and expected_outputs/s18 (FIELD-LOG.md). All text is PETSCII
(upper/lower case swapped versus ASCII, 0xA0 = padding, 0x0D = new line). Blocks are 254 bytes.

  Block 0  directory entry (30 bytes) + signature "PRG formatted GEOS file V1.0"
     0 file type   3..18 name (16, 0xA0 padded)   21 structure (0 seq, 1 vlir)   22 GEOS type
     23..27 year (19xx, 100+ = 20xx), month, day, hour, minute       28 u16 block count
  Block 1  info block: class name @0 (20 bytes), author @20 (20), description @40
  seq:  blocks 2.. are the data; text = data with trailing NULs removed      -> one record, slot 0
  vlir: block 2 is the record table: 127 x (u8 blocks, u8 bytes used in the last block);
        (0, 0xFF) = empty slot, (0, 0) = end. Records follow, each padded to whole blocks.
        Bytes used are taken as stored (NOT minus 1 as on a real 1541 disk): the samples prove it.

Verification: the signature must be present, the declared block count must match the blocks in
the file, and every vlir record must fit in the data that follows the table.
"""
from __future__ import annotations

from ..core.model import FileResult
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec
from ._common import D, damage, record

BLOCK = 254
SIGNATURE = b"PRG formatted GEOS file"

CVT_SPEC = FormatSpec(
    name="CVT",
    magic=SIGNATURE,
    magic_offset=30,
    description="GEOS Convert file: directory entry + signature block, info block, then data "
                "(seq) or a record table followed by records (vlir), in 254-byte blocks, PETSCII text.",
    checksum="none (structure: declared block count, record table)",
    header=[FieldSpec("file_type", "u8", desc="C64 file type", evidence="0x83 in samples"),
            FieldSpec("name", "bytes", 16, "PETSCII name, 0xA0 padded", "expected s18"),
            FieldSpec("structure", "u8", desc="0 seq, 1 vlir", evidence="expected s18 'seq'; s19 table"),
            FieldSpec("geos_type", "u8", desc="GEOS file type", evidence="expected s18 = 7"),
            FieldSpec("modified", "bytes", 5, "year, month, day, hour, minute", "expected s18"),
            FieldSpec("declared_blocks", "u16", desc="blocks after the directory block",
                      evidence="s18 4 = info + 3 data; s19 6 = info + table + 4 data")],
)


def petscii(bs: bytes) -> str:
    out = []
    for c in bs:
        if c == 0x0D:
            out.append("\n")
        elif 0x41 <= c <= 0x5A:
            out.append(chr(c + 32))
        elif 0x61 <= c <= 0x7A:
            out.append(chr(c - 32))
        elif 0xC1 <= c <= 0xDA:
            out.append(chr(c - 0x80))
        elif c == 0xA0:
            out.append(" ")
        elif 0x20 <= c < 0x41 or c in (0x5B, 0x5D):
            out.append(chr(c))
        elif c == 0x5C:
            out.append("£")
        elif c == 0x0A:
            out.append("\n")
        else:
            out.append("�")
    return "".join(out)


def _field(bs: bytes) -> str:
    return petscii(bs.split(b"\x00")[0].rstrip(b"\xa0")).rstrip()


@register
class CvtDecoder(Decoder):
    name = "CVT"
    spec = CVT_SPEC
    ready = True

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        b = data
        if len(b) < 30:
            res.status = "failed"
            damage(res, D.TRUNCATED, 0, len(b), "file ends inside the directory entry")
            return res
        d = b[:30]
        year = 1900 + d[23]                  # 91 -> 1991, 101 -> 2001 (s19)
        modified = f"{year:04d}-{d[24]:02d}-{d[25]:02d}T{d[26]:02d}:{d[27]:02d}"
        structure = {0: "seq", 1: "vlir"}.get(d[21], f"unknown_{d[21]}")
        declared = d[28] | d[29] << 8
        meta = {"name": _field(d[3:19]), "structure": structure, "geos_type": d[22], "modified": modified,
                "class_name": None, "author": None, "description": None, "declared_blocks": declared}
        res.metadata = meta
        if not (1 <= d[24] <= 12 and 1 <= d[25] <= 31 and d[26] < 24 and d[27] < 60):
            damage(res, D.INVALID_VALUE, 23, 28, f"impossible modification date {list(d[23:28])}", lossy=False)
        info = b[BLOCK:2 * BLOCK]
        if len(info) < 60:
            damage(res, D.TRUNCATED, BLOCK, len(b), "file ends inside the info block")
            return res
        meta["class_name"], meta["author"], meta["description"] = _field(info[0:20]), _field(info[20:40]), _field(info[40:100])

        nblocks = -(-(len(b) - BLOCK) // BLOCK)
        whole = (len(b) - BLOCK) % BLOCK == 0
        if not whole or nblocks != declared:
            lost = nblocks < declared or not whole
            damage(res, D.TRUNCATED if lost else D.COUNT_MISMATCH, len(b), len(b),
                   f"directory declares {declared} blocks after the first; file holds "
                   f"{(len(b) - BLOCK) / BLOCK:.2f}", lossy=lost)

        if structure == "seq":
            text = petscii(b[2 * BLOCK:].rstrip(b"\x00"))
            res.records.append(record(0, 2 * BLOCK, {"slot": 0, "text": text},
                                      verified=whole and nblocks == declared,
                                      issues=[] if whole and nblocks == declared else ["truncated"]))
        elif structure == "vlir":
            table, pos = b[2 * BLOCK:3 * BLOCK], 3 * BLOCK
            for slot in range(min(127, len(table) // 2)):
                nb, last = table[2 * slot], table[2 * slot + 1]
                if nb == 0 and last == 0:
                    break
                if nb == 0:
                    continue                      # empty slot (0, 0xFF)
                size = (nb - 1) * BLOCK + last
                chunk = b[pos:pos + size]
                ok = len(chunk) == size and last <= BLOCK
                if not ok:
                    damage(res, D.TRUNCATED if len(chunk) < size else D.BAD_LENGTH, pos, min(len(b), pos + size),
                           f"vlir slot {slot}: {len(chunk)} of {size} bytes present", affected=[f"slot {slot}"])
                res.records.append(record(slot, pos, {"slot": slot, "text": petscii(chunk.rstrip(b"\x00"))},
                                          verified=ok, issues=[] if ok else ["truncated"]))
                pos += nb * BLOCK
            if pos < len(b) and b[pos:].strip(b"\x00"):
                damage(res, D.UNPARSED_BYTES, pos, len(b), f"{len(b) - pos} bytes after the last vlir record",
                       lossy=False)
        else:
            damage(res, D.INVALID_VALUE, 21, 22, f"unknown structure byte {d[21]}")
            res.status = "failed"
        return res
