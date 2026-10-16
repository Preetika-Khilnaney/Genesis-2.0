"""XOR de-obfuscation for VAULT strings. OWNER: Khushi (recovery), with Bhupesh for key evidence.

Candidate keys are scored by how much the output looks like text. The best key
must clearly beat the runner-up across ALL samples before it is accepted;
otherwise strings stay UNVERIFIED. Log every key tried in FIELD-LOG.md.
"""
from __future__ import annotations


def xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


_COMMON = set(b"etaoinshrdlu ETAOINSHRDLU0123456789")


def text_score(data: bytes) -> float:
    """How much `data` looks like text: printable share, boosted by common letters,
    digits and spaces. Printable share alone ties keys that only flip letter case.

    Trailing NUL bytes are padding in fixed-width string fields: they are dropped
    before scoring, so the right key is not punished for them (and a wrong key that
    turns the padding into letters does not win)."""
    data = data.rstrip(b"\x00")
    if not data:
        return 0.0
    printable = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13)) / len(data)
    common = sum(1 for b in data if b in _COMMON) / len(data)
    return printable + common


def rank_single_byte_keys(samples: list[bytes]) -> list[tuple[int, float]]:
    """All 256 single-byte keys ranked by mean text score over the samples."""
    scores = []
    for k in range(256):
        key = bytes([k])
        s = sum(text_score(xor(d, key)) for d in samples) / max(len(samples), 1)
        scores.append((k, s))
    return sorted(scores, key=lambda t: t[1], reverse=True)


# TODO(Khushi): multi-byte repeating keys (split by key position, rank each byte)
