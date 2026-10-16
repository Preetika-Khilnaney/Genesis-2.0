"""Seeded, deterministic damage functions. OWNER: Manas (delivery).

Provides reproducible corruption functions for adversarial testing:
  - bit_flips (1, 8, 64 bits)
  - truncate (at specified percentage or byte offset)
  - zero_block (overwrites a range with zeros)
  - insert_bytes (inserts random bytes, shifting downstream offsets)
  - delete_bytes (deletes a range of bytes, shifting downstream offsets)
  - overwrite_header (corrupts magic/signature bytes)
  - append_garbage (appends random trailing bytes after EOF)
  - empty_file (0-byte file)
  - wrong_extension (renames file with misleading extension)

Every function returns:
  (damaged_bytes: bytes, ground_truth: dict)
"""
from __future__ import annotations

import random
from pathlib import Path


def bit_flips(data: bytes, n_flips: int = 1, seed: int = 0) -> tuple[bytes, dict]:
    """Flip exactly n_flips bits deterministically at pseudo-random positions."""
    if not data:
        return b"", {"damage_type": "bit_flips", "flips": 0, "start": 0, "end": 0, "cause": "crc_fail", "detail": "empty buffer"}
    rng = random.Random(seed)
    buf = bytearray(data)
    total_bits = len(data) * 8
    actual_flips = min(n_flips, total_bits)
    bit_indices = rng.sample(range(total_bits), actual_flips)
    flipped_bytes = set()
    for b in bit_indices:
        byte_idx = b // 8
        bit_idx = b % 8
        buf[byte_idx] ^= 1 << bit_idx
        flipped_bytes.add(byte_idx)

    min_byte = min(flipped_bytes) if flipped_bytes else 0
    max_byte = max(flipped_bytes) + 1 if flipped_bytes else 0
    return bytes(buf), {
        "damage_type": "bit_flips",
        "flips": actual_flips,
        "start": min_byte,
        "end": max_byte,
        "cause": "crc_fail",
        "flipped_bytes": sorted(flipped_bytes),
        "detail": f"{actual_flips} bit flips across bytes [{min_byte}..{max_byte})",
    }


def truncate(data: bytes, pct: float | None = None, offset: int | None = None, seed: int = 0) -> tuple[bytes, dict]:
    """Truncate buffer at a given percentage (0..1) or absolute byte offset."""
    if not data:
        return b"", {"damage_type": "truncate", "start": 0, "end": 0, "cause": "truncated", "detail": "empty buffer"}
    n = len(data)
    if pct is not None:
        cut = max(0, min(n, int(n * pct)))
    elif offset is not None:
        cut = max(0, min(n, offset))
    else:
        rng = random.Random(seed)
        cut = rng.randint(0, n)

    return data[:cut], {
        "damage_type": "truncate",
        "start": cut,
        "end": n,
        "cause": "truncated",
        "kept_bytes": cut,
        "original_size": n,
        "detail": f"truncated from {n} bytes to {cut} bytes",
    }


def zero_block(data: bytes, start: int | None = None, length: int | None = None, seed: int = 0) -> tuple[bytes, dict]:
    """Overwrite a slice with 0x00 bytes."""
    if not data:
        return b"", {"damage_type": "zero_block", "start": 0, "end": 0, "cause": "crc_fail", "detail": "empty buffer"}
    n = len(data)
    rng = random.Random(seed)
    if start is None:
        start = rng.randrange(n)
    if length is None:
        length = max(1, min(n - start, rng.randint(1, max(1, n // 5))))
    end = min(n, start + length)

    damaged = data[:start] + (b"\x00" * (end - start)) + data[end:]
    return damaged, {
        "damage_type": "zero_block",
        "start": start,
        "end": end,
        "cause": "crc_fail",
        "length": end - start,
        "detail": f"zeroed {end - start} bytes from offset {start} to {end}",
    }


def insert_bytes(data: bytes, offset: int | None = None, length: int = 1, seed: int = 0) -> tuple[bytes, dict]:
    """Insert random bytes at an offset, shifting all subsequent bytes."""
    n = len(data)
    rng = random.Random(seed)
    if offset is None:
        offset = rng.randint(0, n)
    offset = max(0, min(n, offset))
    junk = bytes(rng.randrange(256) for _ in range(length))
    damaged = data[:offset] + junk + data[offset:]
    return damaged, {
        "damage_type": "insert_bytes",
        "start": offset,
        "end": offset + length,
        "cause": "bad_offset",
        "length": length,
        "detail": f"inserted {length} bytes at offset {offset}",
    }


def delete_bytes(data: bytes, offset: int | None = None, length: int = 1, seed: int = 0) -> tuple[bytes, dict]:
    """Delete a slice of bytes at an offset, shifting subsequent bytes."""
    n = len(data)
    if not data or n <= length:
        return b"", {
            "damage_type": "delete_bytes",
            "start": 0,
            "end": n,
            "cause": "truncated",
            "length": n,
            "detail": f"deleted all {n} bytes",
        }
    rng = random.Random(seed)
    if offset is None:
        offset = rng.randint(0, n - length)
    offset = max(0, min(n - length, offset))
    end = offset + length
    damaged = data[:offset] + data[end:]
    return damaged, {
        "damage_type": "delete_bytes",
        "start": offset,
        "end": end,
        "cause": "bad_offset",
        "length": length,
        "detail": f"deleted {length} bytes from offset {offset} to {end}",
    }


def overwrite_header(data: bytes, length: int = 8, seed: int = 0) -> tuple[bytes, dict]:
    """Overwrite the file header with arbitrary garbage bytes."""
    if not data:
        return b"", {"damage_type": "overwrite_header", "start": 0, "end": 0, "cause": "crc_fail", "detail": "empty buffer"}
    rng = random.Random(seed)
    actual_len = min(len(data), length)
    garbage = bytes(rng.randrange(256) for _ in range(actual_len))
    damaged = garbage + data[actual_len:]
    return damaged, {
        "damage_type": "overwrite_header",
        "start": 0,
        "end": actual_len,
        "cause": "bad_key",
        "length": actual_len,
        "detail": f"overwrote {actual_len} header bytes with pseudo-random bytes",
    }


def append_garbage(data: bytes, length: int = 64, seed: int = 0) -> tuple[bytes, dict]:
    """Append trailing garbage bytes past EOF."""
    rng = random.Random(seed)
    garbage = bytes(rng.randrange(256) for _ in range(length))
    n = len(data)
    return data + garbage, {
        "damage_type": "append_garbage",
        "start": n,
        "end": n + length,
        "cause": "bad_length",
        "length": length,
        "detail": f"appended {length} bytes of garbage after EOF at {n}",
    }


def empty_file(data: bytes = b"", seed: int = 0) -> tuple[bytes, dict]:
    """0-byte file damage operator."""
    return b"", {
        "damage_type": "empty_file",
        "start": 0,
        "end": 0,
        "cause": "truncated",
        "detail": "empty 0-byte file",
    }


def wrong_extension(filename: str, seed: int = 0) -> tuple[str, dict]:
    """Change the file extension to a mismatched or confusing format."""
    rng = random.Random(seed)
    bad_exts = [".jpg", ".txt", ".csv", ".xyz", ".bak", ".dat", ".tmp"]
    p = Path(filename)
    chosen = rng.choice(bad_exts)
    new_name = p.stem + chosen
    return new_name, {
        "damage_type": "wrong_extension",
        "original_name": filename,
        "new_name": new_name,
        "detail": f"changed extension from {p.suffix} to {chosen}",
    }


def all_damage_variants(data: bytes, seed: int = 42) -> dict[str, tuple[bytes, dict]]:
    """Generate the full standard suite of damaged variants for a given clean buffer."""
    variants: dict[str, tuple[bytes, dict]] = {}
    if not data:
        variants["empty"] = empty_file(data, seed=seed)
        return variants

    # 1. Bit flips
    variants["flip_1bit"] = bit_flips(data, n_flips=1, seed=seed + 1)
    variants["flip_8bit"] = bit_flips(data, n_flips=8, seed=seed + 2)
    variants["flip_64bit"] = bit_flips(data, n_flips=64, seed=seed + 3)

    # 2. Truncations
    variants["trunc_25pct"] = truncate(data, pct=0.25, seed=seed + 10)
    variants["trunc_50pct"] = truncate(data, pct=0.50, seed=seed + 11)
    variants["trunc_75pct"] = truncate(data, pct=0.75, seed=seed + 12)

    # 3. Zero block
    variants["zeroed_block"] = zero_block(data, seed=seed + 20)

    # 4. Insertions & deletions
    variants["inserted_bytes"] = insert_bytes(data, length=max(1, len(data) // 20), seed=seed + 30)
    variants["deleted_bytes"] = delete_bytes(data, length=max(1, len(data) // 20), seed=seed + 40)

    # 5. Overwritten header & appended garbage
    variants["overwritten_header"] = overwrite_header(data, length=min(16, len(data)), seed=seed + 50)
    variants["appended_garbage"] = append_garbage(data, length=64, seed=seed + 60)

    # 6. Empty file
    variants["empty"] = empty_file(data, seed=seed + 70)

    return variants
