"""Game archive: Quake PACK (.PAK). OWNER: Khushi (recovery).

Chosen at H12 because its samples are in hand and it is shaped like VAULT (an index table
pointing at blobs); it is also a real, publicly documented format. Every fact below is a
FIELD-LOG row (format "pak"), found with tools/archive_probe.py:

    0    50 41 43 4B     magic "PACK"
    4    i32             directory offset
    8    i32             directory length in bytes (offset + length == file size)
    12   blobs, back to back, up to the directory
    dir  length / 64 entries:  56-byte NUL-padded name | i32 offset | i32 size

There is no checksum, no compression and no packed size, so:
  - offset / size are VERIFIED only when the blobs tile [12, directory) exactly;
  - names are VERIFIED when they are clean NUL-padded text read from a directory whose
    position is confirmed (the header agrees with the file size, or it is found at the end);
  - blob CONTENT is at most UNVERIFIED: nothing in the file can prove those bytes.
Recovery: when bytes were inserted or deleted before the directory, the header's offset goes
stale. The directory is always at the end (all-samples rule), so it is looked for there.
"""
from __future__ import annotations

from ..core.index import IndexEntry, read_index
from ..core.model import DamageCause, DamageEntry, Field, FieldStatus, FileResult, Record
from ..core.reader import ByteReader, OutOfBounds
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec, decode_fields
from ..recovery.index_damage import anchor_empty_ranges
from ..recovery.xor import is_clean_fixed_string

MAGIC = b"PACK"
HEADER_SIZE = 12
ENTRY_SIZE = 64
NAME_LEN = 56
MAX_ENTRIES = 100_000

ENTRY = [FieldSpec("name", "bytes", NAME_LEN), FieldSpec("offset", "i32"), FieldSpec("size", "i32")]

PAK_SPEC = FormatSpec(
    name="pak",
    magic=MAGIC,
    endian="little",
    description=("Quake PACK archive: a 12-byte header pointing at a directory stored at the END of the "
                 "file; the blobs sit between the header and the directory. No checksum and no "
                 "compression, so blob contents are reported but never verified. Real public format; "
                 "check it against the real samples."),
    header=[
        FieldSpec("magic", "bytes", 4, desc="file signature 'PACK'", evidence="FIELD-LOG: same in all 6 samples"),
        FieldSpec("dir_offset", "i32", desc="offset of the directory",
                  evidence="FIELD-LOG: dir_offset + dir_length == file size in every sample"),
        FieldSpec("dir_length", "i32", desc="directory length in bytes (64 per entry)",
                  evidence="FIELD-LOG: varies between files; a multiple of 64"),
    ],
    record=[
        FieldSpec("name", "str", NAME_LEN, desc="file path, NUL-padded",
                  evidence="FIELD-LOG: clean NUL-padded text in every entry; not XORed"),
        FieldSpec("offset", "i32", desc="blob offset", evidence="FIELD-LOG: blobs tile 12..directory exactly"),
        FieldSpec("size", "i32", desc="blob size", evidence="FIELD-LOG: sizes vary; blobs tile exactly"),
        FieldSpec("data", "bytes", desc="blob content (text when printable, else hex); never verified",
                  evidence="FIELD-LOG: no checksum, compression or packed size covers it"),
    ],
    notes=["The directory is found at the end of the file when the header's offset disagrees with the file size.",
           "Blob contents stay unverified: nothing in the format can prove them."],
)


def _text(raw: bytes) -> str:
    if raw and all(32 <= c < 127 or c in (9, 10, 13) for c in raw):
        return raw.decode("ascii")
    return raw.hex()


def _names_clean(data: bytes, at: int, count: int) -> bool:
    if count <= 0 or at < HEADER_SIZE or at + count * ENTRY_SIZE > len(data):
        return False
    return all(is_clean_fixed_string(data[at + k * ENTRY_SIZE:at + k * ENTRY_SIZE + NAME_LEN]) for k in range(count))


def _chain_end(data: bytes, at: int, count: int) -> int | None:
    """Where the blobs of the directory at `at` end, if sorted by offset they start at 12 and
    touch end to start; None otherwise."""
    spans = []
    for k in range(count):
        e = at + k * ENTRY_SIZE + NAME_LEN
        spans.append((int.from_bytes(data[e:e + 4], "little", signed=True),
                      int.from_bytes(data[e + 4:e + 8], "little", signed=True)))
    pos = HEADER_SIZE
    for o, sz in sorted(spans):
        if o != pos or sz < 0:
            return None
        pos = o + sz
    return pos


def _locate(data: bytes, d: int, n: int) -> tuple[int, int, str, bool]:
    """(directory offset, entry count, how it was found, position confirmed?)."""
    count = n // ENTRY_SIZE if 0 <= n <= MAX_ENTRIES * ENTRY_SIZE else 0
    if n >= 0 and n % ENTRY_SIZE == 0 and d >= HEADER_SIZE and d + n == len(data):
        return d, count, "header (offset + length == file size)", True
    end = len(data) - n
    # Bytes inserted/deleted before the directory leave it intact at the end of the file, and its
    # entries still tile [12, d) as they did before. Clean names alone are not enough: a directory
    # read one byte off can still look like text when the shift falls in the padding.
    if n > 0 and n % ENTRY_SIZE == 0 and _names_clean(data, end, count) and             _chain_end(data, end, count) in (d, end):
        return end, count, "end of file (the header's offset disagrees with the file size)", True
    return d, count, "header (unconfirmed: offset + length != file size)", False


def _layout(data: bytes):
    if len(data) < HEADER_SIZE:
        return None
    d = int.from_bytes(data[4:8], "little", signed=True)
    n = int.from_bytes(data[8:12], "little", signed=True)
    at, count, how, confirmed = _locate(data, d, n)
    scan = read_index(data, at, count, ENTRY, data_start=HEADER_SIZE) if 0 <= at <= len(data) else None
    return d, n, at, count, how, confirmed, scan


def _tiles(scan, at: int, count: int) -> bool:
    if scan is None or scan.damage or len(scan.entries) != count or not count:
        return False
    pos = HEADER_SIZE
    for e in sorted(scan.entries, key=lambda e: e.offset):
        if not e.ok or e.offset != pos:
            return False
        pos = e.end
    return pos == at


@register
class PakDecoder(Decoder):
    name = "pak"
    spec = PAK_SPEC
    ready = True

    def structure_score(self, data: bytes) -> float:
        # magic damaged: still PAK if the header's directory sits at the end and the blobs tile up to it
        try:
            lay = _layout(data)
        except Exception:
            return 0.0
        if not lay:
            return 0.0
        d, n, at, count, how, confirmed, scan = lay
        return 1.0 if confirmed and at == d and _tiles(scan, at, count) else 0.0

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        try:
            res.header = decode_fields(ByteReader(data, "little"), PAK_SPEC.header)
        except OutOfBounds:
            res.damage.append(DamageEntry(0, len(data), DamageCause.TRUNCATED,
                                          "file ends inside the 12-byte header", ["header"]))
            return res
        d, n, at, count, how, confirmed, scan = _layout(data)
        h = res.header
        if data[:4] == MAGIC:
            h["magic"].status, h["magic"].note = FieldStatus.VERIFIED, "matches 'PACK'"
        header_ok = confirmed and at == d
        for k in ("dir_offset", "dir_length"):
            h[k].status = FieldStatus.VERIFIED if header_ok and _tiles(scan, at, count) else FieldStatus.UNVERIFIED
            h[k].note = "directory found where the header says, blobs tile up to it" if \
                h[k].status == FieldStatus.VERIFIED else f"directory located by: {how}"
        res.extra.update({"directory_offset": at, "directory_found_by": how, "entries": count})

        if n < 0 or n % ENTRY_SIZE or n > MAX_ENTRIES * ENTRY_SIZE:
            res.warnings.append(f"directory length {n} is not a multiple of {ENTRY_SIZE}; read {count} entries")
        if confirmed and at != d:
            delta = at - d
            res.damage.append(DamageEntry(HEADER_SIZE, min(at + NAME_LEN, len(data)), DamageCause.BAD_OFFSET,
                                          f"the directory is {abs(delta)} bytes {'later' if delta > 0 else 'earlier'} "
                                          f"than the header says: bytes were {'inserted' if delta > 0 else 'deleted'} "
                                          "in the blob area or in the first entry's name (or the header offset is "
                                          "damaged); blob boundaries after that point and the first name are "
                                          "unreliable", ["blobs", "entry 0 name"]))
        if scan is None:
            # no directory to read: the blobs that are here cannot be located or named
            if at > len(data):
                # the blob area that is left, or (header only) the header fields that point past the end
                lo, hi = (HEADER_SIZE, len(data)) if len(data) > HEADER_SIZE else (4, HEADER_SIZE)
                res.damage.append(DamageEntry(lo, hi, DamageCause.TRUNCATED,
                                              f"file ends at {len(data)}, before the directory at {at}; "
                                              "the blobs present cannot be located without it", ["directory"]))
            else:
                res.damage.append(DamageEntry(4, 8, DamageCause.BAD_OFFSET,
                                              f"directory offset {d} is negative", ["directory"]))
            return res

        res.damage += anchor_empty_ranges(scan.damage, at, ENTRY_SIZE)
        res.warnings += scan.warnings
        for e in scan.entries:
            if e.ok and e.offset < at + n and e.end > at:
                e.ok, e.note = False, f"blob {e.offset}..{e.end} runs into the directory at {at}"
                res.damage.append(DamageEntry(max(e.offset, at), min(e.end, at + n), DamageCause.BAD_OFFSET,
                                              f"entry {e.index}: {e.note}", [f"entry {e.index}"]))
        tiles = _tiles(scan, at, count)
        if not tiles and scan.entries:
            res.warnings.append("the blobs do not tile the area between the header and the directory exactly: "
                                "offsets and sizes stay unverified")
        # Directory re-found at the end, but its entries still tile up to the header's offset: the
        # shift lies between the blobs' start and entry 0's offset field. A shift inside any LATER
        # name would misalign the entries before it, so only entry 0's name can hold it.
        first_suspect = confirmed and at != d
        for e in scan.entries:
            res.records.append(self._record(e, at, confirmed and not (first_suspect and e.index == 0), tiles))
        return res

    def _record(self, e: IndexEntry, at: int, confirmed: bool, tiles: bool) -> Record:
        rec = Record(index=e.index, offset=at + e.index * ENTRY_SIZE)
        f = e.fields
        raw = bytes.fromhex(f["name"].value)
        clean = is_clean_fixed_string(raw)
        name = raw.rstrip(b"\0").decode("latin-1") if clean else None
        if clean and confirmed:
            rec.add(Field("name", name, FieldStatus.VERIFIED, f["name"].offset, NAME_LEN,
                          "clean NUL-padded text in a directory whose position is confirmed"))
        elif clean:
            rec.add(Field("name", name, FieldStatus.UNVERIFIED, f["name"].offset, NAME_LEN,
                          "the directory's position is not confirmed, or bytes may have moved inside this name"))
        else:
            rec.add(Field("name", None, FieldStatus.LOST, f["name"].offset, NAME_LEN,
                          "not NUL-padded text: the name bytes are damaged"))
        if not e.ok:
            for k in ("offset", "size", "data"):
                rec.add(Field(k, None, FieldStatus.LOST, f[k].offset if k in f else None,
                              f[k].length if k in f else None, e.note))
            return rec
        status = FieldStatus.VERIFIED if tiles else FieldStatus.UNVERIFIED
        note = "the blobs tile the area up to the directory exactly" if tiles else \
            (e.note or "the blobs do not tile the area up to the directory exactly")
        for k in ("offset", "size"):
            rec.add(Field(k, f[k].value, status, f[k].offset, f[k].length, note))
        rec.add(Field("data", _text(e.blob), FieldStatus.UNVERIFIED, e.offset, e.size,
                      "no checksum or compression covers blob contents"))
        return rec
