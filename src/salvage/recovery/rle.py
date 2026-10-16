"""Run-length decoding for VAULT blobs. OWNER: Khushi (recovery).

RLE has many variants. Implement each candidate as a (decode, encode) pair, then
keep the one where encode(decode(blob)) == blob on every sample (round-trip proof).
Log every variant tried in FIELD-LOG.md.

VAULT (stand-in samples): `pairs` round-trips every blob of every sample and `packbits`
none (FIELD-LOG, format "vault"). The decoder still pins the variant from the samples at
run time, so a real VAULT using PackBits would be picked up without a code change.
"""
from __future__ import annotations


class RLEError(Exception):
    pass


def decode_pairs(blob: bytes) -> bytes:
    """Candidate: (count, byte) pairs."""
    if len(blob) % 2:
        raise RLEError("odd length for (count, byte) pairs")
    out = bytearray()
    for i in range(0, len(blob), 2):
        out += bytes([blob[i + 1]]) * blob[i]
    return bytes(out)


def encode_pairs(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i] and j - i < 255:
            j += 1
        out += bytes([j - i, data[i]])
        i = j
    return bytes(out)


def decode_packbits(blob: bytes) -> bytes:
    """Candidate: PackBits (Apple / TIFF). Header h as a signed byte:
    0..127 -> copy the next h+1 bytes; -1..-127 -> repeat the next byte 1-h times; -128 -> no-op."""
    out = bytearray()
    i = 0
    while i < len(blob):
        h = blob[i] - 256 if blob[i] > 127 else blob[i]
        i += 1
        if h >= 0:
            if i + h + 1 > len(blob):
                raise RLEError(f"literal run of {h + 1} bytes runs past the blob at {i - 1}")
            out += blob[i:i + h + 1]
            i += h + 1
        elif h != -128:
            if i >= len(blob):
                raise RLEError(f"repeat run at {i - 1} has no byte to repeat")
            out += bytes([blob[i]]) * (1 - h)
            i += 1
    return bytes(out)


def encode_packbits(data: bytes) -> bytes:
    """Classic PackBits encoder: runs of 2..128 equal bytes become repeats, the rest literals
    of up to 128 bytes. Other encoders exist (e.g. some never emit 2-byte repeats); the round
    trip on every sample tells them apart."""
    out = bytearray()
    lit = bytearray()

    def flush() -> None:
        while lit:
            chunk = lit[:128]
            out.append(len(chunk) - 1)
            out.extend(chunk)
            del lit[:128]

    i = 0
    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i] and j - i < 128:
            j += 1
        if j - i >= 2:
            flush()
            out += bytes([(1 - (j - i)) & 0xFF, data[i]])
        else:
            lit.append(data[i])
        i = j
    flush()
    return bytes(out)


VARIANTS = {
    "pairs": (decode_pairs, encode_pairs),
    "packbits": (decode_packbits, encode_packbits),
}


def find_variant(blobs: list[bytes]) -> list[str]:
    """Variants whose round trip reproduces every blob exactly."""
    ok = []
    for name, (dec, enc) in VARIANTS.items():
        try:
            if all(enc(dec(b)) == b for b in blobs):
                ok.append(name)
        except RLEError:
            continue
    return ok


def best_variant(blobs: list[bytes], min_share: float = 0.8) -> tuple[str | None, float]:
    """Variant that round-trips the largest share of blobs. Unlike find_variant, a few
    damaged blobs do not veto it. Returns (None, share) unless exactly one variant reaches
    min_share; the caller still verifies each blob by its own exact round trip."""
    if not blobs:
        return None, 0.0
    scored = []
    for name, (dec, enc) in VARIANTS.items():
        ok = 0
        for b in blobs:
            try:
                ok += enc(dec(b)) == b
            except RLEError:
                pass
        scored.append((ok / len(blobs), name))
    winners = [n for s, n in scored if s >= min_share]
    best = max(s for s, _ in scored)
    return (winners[0], best) if len(winners) == 1 else (None, best)
