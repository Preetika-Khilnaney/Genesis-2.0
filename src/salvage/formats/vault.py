"""VAULT. OWNER: Khushi (recovery), field evidence with Bhupesh.

Three pieces stacked: an index table pointing at blobs, run-length-compressed blobs, and
XOR-obfuscated names. VAULT has NO checksum, so every VERIFIED needs other proof:
  - offsets/sizes: the entries tile the data area exactly (core.index.read_index);
  - blob content: the RLE variant pinned on all samples re-encodes the blob to the exact
    stored bytes AND decodes to exactly the size the index says AND the entries tile the
    file exactly. The last condition matters: bytes deleted inside one blob shift every
    later blob, and with (count, byte) pairs the shifted blobs still decode and round-trip.
    From the bytes alone that looks just like a file cut short at the end, so once the file
    length disagrees with its index, no blob can be proven to sit where the index says;
  - an empty blob (size 0) is never VERIFIED: a zeroed entry decodes to b"" "perfectly";
  - names: one XOR key wins on every sample (recovery.xor.choose_key) and the name comes
    out as clean NUL-padded text.
What it cannot see: a bit flip inside a literal byte of a blob or a name that still leaves
printable text. Nothing in the file can tell; the tests measure how often it happens.

STAND-IN LAYOUT: worked out from samples/vault/ (our demo data, invented layout) with
tools/vault_probe.py. Redo it from real-samples/vault/ when the real samples arrive
(`python3 tools/vault_probe.py real-samples/vault/ --by Khushi --log`). The RLE variant and
the XOR key are already chosen from the samples at run time, not hard-coded. Every fact is
a FIELD-LOG row (format "vault"):

    0   56 41 4C 54     magic "VALT"
    4   u16             entry count
    6   count x 24-byte entries:  12-byte XORed name | u32 offset | u32 stored size | u32 decoded size
        blobs, back to back to EOF: RLE (count, byte) pairs
"""
from __future__ import annotations

from ..core.index import IndexEntry, index_structure_score, read_index
from ..core.model import DamageCause, DamageEntry, Field, FieldStatus, FileResult, Record
from ..core.reader import ByteReader, OutOfBounds
from ..core.registry import DecodeContext, Decoder, register
from ..core.spec import FieldSpec, FormatSpec, decode_fields
from ..recovery import rle, xor
from ..recovery.index_damage import anchor_empty_ranges

MAGIC = b"VALT"
HEADER_SIZE = 6
NAME_LEN = 12

ENTRY = [
    FieldSpec("name", "bytes", NAME_LEN),
    FieldSpec("offset", "u32"),
    FieldSpec("size", "u32"),
    FieldSpec("raw_size", "u32"),
]

VAULT_SPEC = FormatSpec(
    name="vault",
    magic=MAGIC,
    endian="little",
    description=("A 6-byte header with the entry count, an index table of 24-byte entries, then the "
                 "blobs back to back. Names are XORed with a single-byte key; blobs are run-length "
                 "encoded (count, byte) pairs. No checksum. "
                 "STAND-IN layout from our own samples; redo from the real samples."),
    header=[
        FieldSpec("magic", "bytes", 4, desc="file signature 'VALT'", evidence="FIELD-LOG: same in all 6 samples"),
        FieldSpec("count", "u16", desc="number of index entries",
                  evidence="FIELD-LOG: first blob starts at 6 + count * 24 in every sample"),
    ],
    record=[
        FieldSpec("name", "str", NAME_LEN, desc="entry name, XORed with a single-byte key, NUL-padded",
                  evidence="FIELD-LOG: key 0x5C wins on every sample; not per file or per entry"),
        FieldSpec("offset", "u32", desc="absolute offset of the blob",
                  evidence="FIELD-LOG: blobs tile the data area exactly in every sample"),
        FieldSpec("size", "u32", desc="stored (compressed) blob size",
                  evidence="FIELD-LOG: blobs chain end to start to EOF; 56 in every sample entry"),
        FieldSpec("raw_size", "u32", desc="decoded blob size",
                  evidence="FIELD-LOG: equals the RLE-decoded size of every blob"),
        FieldSpec("data", "bytes", desc="decoded blob content (text when printable, else hex)",
                  evidence="FIELD-LOG: RLE 'pairs' round-trips every blob; 'packbits' none"),
    ],
    notes=["The RLE variant and the XOR key are chosen from the samples at run time (all-samples rule).",
           "No checksum: a bit flip in a literal byte that keeps the text printable cannot be detected."],
)


def _header_count(data: bytes) -> int | None:
    return int.from_bytes(data[4:6], "little") if len(data) >= HEADER_SIZE else None


def _scan(data: bytes):
    count = _header_count(data)
    return None if count is None else read_index(data, HEADER_SIZE, count, ENTRY)


def _clean(e: IndexEntry) -> bool:
    return e.ok and "overlaps" not in e.note


def _text(raw: bytes) -> str:
    if raw and all(32 <= c < 127 or c in (9, 10, 13) for c in raw):
        return raw.decode("ascii")
    return raw.hex()


def _evidence(data: bytes, ctx: DecodeContext | None):
    """Per run, from every sample of this format: the RLE variant and the XOR key."""
    samples = ctx.samples(data) if ctx else [data]
    names, blobs = [], []
    for s in samples:
        try:
            scan = _scan(s)
        except Exception:
            scan = None
        names.append([bytes.fromhex(e.fields["name"].value) for e in scan.entries] if scan else [])
        blobs += [e.blob for e in scan.entries if scan and _clean(e)] if scan else []
    variant, share = rle.best_variant(blobs)
    from ..evidence.checker import MIN_SAMPLES
    key, agreed, key_note = xor.choose_key(names, min_samples=MIN_SAMPLES)
    return variant, share, key, agreed, key_note, len(samples)


@register
class VaultDecoder(Decoder):
    name = "vault"
    spec = VAULT_SPEC
    ready = True

    def structure_score(self, data: bytes) -> float:
        # magic damaged: still VAULT if the entries tile the rest of the file exactly
        count = _header_count(data)
        return 0.0 if not count else index_structure_score(data, HEADER_SIZE, count, ENTRY)

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        res = FileResult(source_file=path, format=self.name)
        try:
            res.header = decode_fields(ByteReader(data, "little"), VAULT_SPEC.header)
        except OutOfBounds:
            res.damage.append(DamageEntry(0, len(data), DamageCause.TRUNCATED,
                                          "file ends inside the 6-byte header", ["header"]))
            return res
        scan = _scan(data)
        variant, share, key, agreed, key_note, n = _evidence(data, ctx)

        magic = res.header["magic"]
        if data[:4] == MAGIC:
            magic.status, magic.note = FieldStatus.VERIFIED, "matches 'VALT' (same in every sample)"
        cnt = res.header["count"]
        if scan.tiles_exactly:
            cnt.status, cnt.note = FieldStatus.VERIFIED, "the index entries tile the file exactly"
        else:
            cnt.note = "the entries do not tile the file exactly (damage or gaps)"

        res.damage += anchor_empty_ranges(scan.damage, HEADER_SIZE, 24)
        res.warnings += scan.warnings
        res.warnings += [f"gap {a}..{b} not covered by any entry" for a, b in scan.gaps]
        if variant is None:
            res.warnings.append(f"no single RLE variant round-trips >= 80% of the blobs (best {share:.0%}); "
                                "blob contents stay unverified")
        res.extra.update({"rle_variant": variant, "xor_key": None if key is None else f"0x{key:02X}",
                          "xor_key_agreed": agreed, "samples_for_evidence": n})

        if not scan.tiles_exactly and scan.entries:
            res.warnings.append("the entries do not tile the file exactly: blob contents are at most unverified "
                                "(no checksum can show where bytes went missing or were added)")
        for e in scan.entries:
            res.records.append(self._record(e, variant, key, agreed, key_note, res, scan.tiles_exactly))
        return res

    def _record(self, e: IndexEntry, variant, key, agreed, key_note, res: FileResult, tiles: bool) -> Record:
        rec = Record(index=e.index, offset=HEADER_SIZE + e.index * 24)
        f = e.fields
        name_f = f["name"]

        # name: XOR key (all-samples rule) + clean NUL-padded text
        raw_name = bytes.fromhex(name_f.value)
        if key is None:
            rec.add(Field("name", None, FieldStatus.LOST, name_f.offset, NAME_LEN, key_note))
            res.damage.append(DamageEntry(name_f.offset, name_f.offset + NAME_LEN, DamageCause.BAD_KEY,
                                          f"entry {e.index}: {key_note}", [f"entry {e.index} name"]))
        else:
            plain = xor.xor(raw_name, bytes([key]))
            text = plain.rstrip(b"\0").decode("latin-1")
            if agreed and _clean(e) and xor.is_clean_fixed_string(plain):
                rec.add(Field("name", text, FieldStatus.VERIFIED, name_f.offset, NAME_LEN,
                              f"XOR 0x{key:02X}: {key_note}"))
            else:
                why = key_note if not agreed else ("entry is damaged" if not _clean(e)
                                                   else "not clean NUL-padded text under the key")
                rec.add(Field("name", text, FieldStatus.UNVERIFIED, name_f.offset, NAME_LEN, why))

        if not e.ok:
            # the entry points outside the file / into the table: none of its numbers can be used
            for k in ("offset", "size", "raw_size", "data"):
                rec.add(Field(k, None, FieldStatus.LOST, f[k].offset if k in f else None,
                              f[k].length if k in f else None, e.note))
            return rec

        for k in ("offset", "size"):
            note = f[k].note or (e.note or "the entries do not tile the file exactly")
            rec.add(Field(k, f[k].value, f[k].status, f[k].offset, f[k].length, note))

        raw_size = f["raw_size"]
        if variant is None:
            rec.add(Field("raw_size", raw_size.value, FieldStatus.UNVERIFIED, raw_size.offset, 4,
                          "no RLE variant pinned"))
            rec.add(Field("data", None, FieldStatus.LOST, e.offset, e.size, "no RLE variant pinned on the samples"))
            res.damage.append(DamageEntry(e.offset, e.end, DamageCause.UNKNOWN,
                                          f"entry {e.index}: blob cannot be decoded (no RLE variant pinned)",
                                          [f"entry {e.index} data"]))
            return rec
        dec, enc = rle.VARIANTS[variant]
        try:
            out = dec(e.blob)
        except rle.RLEError as ex:
            rec.add(Field("raw_size", raw_size.value, FieldStatus.UNVERIFIED, raw_size.offset, 4, str(ex)))
            rec.add(Field("data", None, FieldStatus.LOST, e.offset, e.size, f"RLE '{variant}' decode failed: {ex}"))
            res.damage.append(DamageEntry(e.offset, e.end, DamageCause.UNKNOWN,
                                          f"entry {e.index}: RLE '{variant}' decode failed: {ex}",
                                          [f"entry {e.index} data"]))
            return rec
        round_trip = enc(out) == e.blob
        size_ok = len(out) == raw_size.value
        if round_trip and size_ok and _clean(e) and tiles and e.size > 0:
            status, note = FieldStatus.VERIFIED, f"RLE '{variant}' re-encodes exactly; decoded size matches the index"
        else:
            status = FieldStatus.UNVERIFIED
            note = "; ".join(x for x in (
                None if round_trip else f"RLE '{variant}' does not re-encode to the stored bytes",
                None if size_ok else f"decodes to {len(out)} bytes, index says {raw_size.value}",
                None if _clean(e) else e.note,
                None if e.size > 0 else "empty blob: its round trip proves nothing (zeroed entry?)",
                None if tiles or not (round_trip and size_ok) else
                "decodes cleanly, but the file does not match its index, so it may be shifted") if x)
        if not size_ok:
            res.damage.append(DamageEntry(e.offset, e.end, DamageCause.BAD_LENGTH,
                                          f"entry {e.index}: blob decodes to {len(out)} bytes, index says "
                                          f"{raw_size.value}", [f"entry {e.index} data"]))
        rec.add(Field("raw_size", raw_size.value, status if size_ok else FieldStatus.UNVERIFIED,
                      raw_size.offset, 4, "equals the decoded size" if size_ok else note))
        rec.add(Field("data", _text(out), status, e.offset, e.size, note))
        return rec
