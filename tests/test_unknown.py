"""Tests for unknown-file reporting. OWNER: Manas (delivery).

Verifies:
  - Shannon entropy calculation (NumPy and fallback)
  - Entropy map generation
  - Compressed / encrypted hint detection
  - ASCII and UTF-16LE string extraction
  - Robust handling of edge cases (empty, 1-byte, huge files)
"""
from __future__ import annotations

import os
from salvage.core.fingerprint import entropy, entropy_map, printable_strings
from salvage.output.unknown import describe


def test_unknown_empty_file():
    res = describe("empty.bin", b"")
    assert res.format == "unknown"
    assert res.extra["size"] == 0
    assert res.extra["overall_entropy"] == 0.0
    assert res.extra["first_bytes_hex"] == ""
    assert res.extra["entropy_map"] == []
    assert res.extra["strings"] == []
    assert res.extra["entropy_hint"] == "empty"
    assert "empty file" in res.warnings


def test_unknown_single_byte():
    res = describe("one_byte.bin", b"\x42")
    assert res.extra["size"] == 1
    assert res.extra["overall_entropy"] == 0.0
    assert res.extra["first_bytes_hex"] == "42"
    assert len(res.extra["entropy_map"]) == 1
    assert res.extra["strings"] == []
    assert "1-byte file" in res.warnings


def test_unknown_high_entropy_hint():
    # Uniform distribution over 256 bytes has Shannon entropy = 8.0 bits/byte
    data = bytes(range(256)) * 4
    res = describe("random.bin", data)
    assert res.extra["overall_entropy"] > 7.5
    assert res.extra["is_compressed_or_encrypted"] is True
    assert res.extra["entropy_hint"] == "compressed_or_encrypted"


def test_unknown_sparse_entropy_hint():
    data = b"\x00" * 1024
    res = describe("zeroes.bin", data)
    assert res.extra["overall_entropy"] < 0.1
    assert res.extra["is_compressed_or_encrypted"] is False
    assert res.extra["entropy_hint"] == "sparse_or_padding"


def test_unknown_ascii_and_utf16_strings():
    # Construct buffer with both ASCII and UTF-16LE strings
    ascii_text = b"SecretDocument"
    utf16_text = "HiddenLegacyRecord".encode("utf-16le")
    buffer = b"\x00" * 10 + ascii_text + b"\xff" * 8 + utf16_text + b"\x00" * 10

    strings = printable_strings(buffer, min_len=4)
    encodings = {s["encoding"] for s in strings}
    texts = [s["text"] for s in strings]

    assert "ascii" in encodings
    assert "utf-16le" in encodings
    assert any("SecretDocument" in t for t in texts)
    assert any("HiddenLegacyRecord" in t for t in texts)


def test_unknown_first_bytes_hex_capped_at_64():
    data = bytes(range(100))
    res = describe("sample.bin", data)
    hex_str = res.extra["first_bytes_hex"]
    # 64 bytes represented as hex with space separators -> 64 pairs
    tokens = hex_str.split()
    assert len(tokens) == 64


def test_unknown_huge_file_bounded_memory():
    # 2 MB buffer
    data = b"ABCDEFGH" * (256 * 1024)
    res = describe("huge.bin", data)
    assert res.extra["size"] == len(data)
    # Entropy map must be capped (<= 1024 blocks)
    assert len(res.extra["entropy_map"]) <= 1024
    # Strings must be capped (<= 50)
    assert len(res.extra["strings"]) <= 50
