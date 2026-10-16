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


def is_clean_fixed_string(data: bytes) -> bool:
    """Printable text followed by at least one NUL of padding: what a fixed-width string
    field looks like under the right key. The padding is the real fingerprint: almost any
    key makes short names printable, but only the right key turns the padding into zeros."""
    core = data.rstrip(b"\x00")
    return bool(core) and len(core) < len(data) and all(32 <= c < 127 for c in core)


def best_fixed_string_key(fields: list[bytes], min_share: float = 0.5, min_margin: float = 0.3) -> tuple[int | None, float]:
    """Single-byte key that turns the most fields into clean NUL-padded strings.
    Returns (key, share) only when the winner covers >= min_share of the fields and beats
    the runner-up by >= min_margin; otherwise (None, best_share): leave strings unverified.
    Tolerates a few damaged fields, so one corrupt sample cannot flip the decision.
    min_share is 0.5 because names that fill the whole field have no padding."""
    if not fields:
        return None, 0.0
    shares = sorted(((sum(is_clean_fixed_string(xor(f, bytes([k]))) for f in fields) / len(fields), k)
                     for k in range(256)), reverse=True)
    (top, key), (second, _) = shares[0], shares[1]
    if top >= min_share and top - second >= min_margin:
        return key, top
    return None, top


def choose_key(per_sample: list[list[bytes]], min_samples: int = 2) -> tuple[int | None, bool, str]:
    """The all-samples rule for a single-byte XOR key over fixed-width string fields.

    per_sample: the obfuscated fields of each sample (this file first).
    Returns (key, agreed, note):
      - agreed=True:  the same key wins (best_fixed_string_key) on every sample that names a
                      winner, and on at least `min_samples` of them -> strings may be VERIFIED;
      - agreed=False, key set:  samples disagree or too few; key is this file's own winner, so
                      its strings stay UNVERIFIED;
      - key None:     no key turns this file's fields into readable text -> LOST, cause bad_key.
    A sample with no winner (e.g. badly damaged) does not veto; a sample with a DIFFERENT
    winner does."""
    keys = [best_fixed_string_key(f)[0] if f else None for f in per_sample]
    own = keys[0] if keys else None
    named = [k for k in keys if k is not None]
    if own is None:
        return None, False, "no single-byte key gives readable NUL-padded names in this file"
    if len(set(named)) == 1 and len(named) >= min_samples:
        return own, True, f"key 0x{own:02X} wins on all {len(named)} samples that name a key"
    if len(set(named)) > 1:
        return own, False, f"samples disagree on the key ({', '.join(f'0x{k:02X}' for k in sorted(set(named)))})"
    return own, False, f"key 0x{own:02X} seen on {len(named)} sample(s) only; need {min_samples}"
