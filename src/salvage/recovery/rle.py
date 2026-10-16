"""Run-length decoding for VAULT blobs. OWNER: Khushi (recovery).

RLE has many variants. Implement each candidate as a (decode, encode) pair, then
keep the one where encode(decode(blob)) == blob on every sample (round-trip proof).
Log every variant tried in FIELD-LOG.md.

TODO(Khushi): confirm VAULT's variant from the samples. `pairs` below is ONE
common candidate, not a confirmed spec.
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


VARIANTS = {
    "pairs": (decode_pairs, encode_pairs),
    # TODO(Khushi): add PackBits / escape-byte variants if the samples need them
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
