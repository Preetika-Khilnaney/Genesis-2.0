"""Recovery helpers and evidence checker."""
import struct

from salvage.evidence import candidates
from salvage.evidence.checker import best_of, evaluate
from salvage.recovery import crc, rle, xor


def test_guess_algorithm_and_check():
    blocks = [(p, crc.crc32(p)) for p in (b"alpha", b"beta", b"gamma")]
    assert crc.guess_algorithm(blocks) == ["crc32"]
    assert crc.check("crc32", b"alpha", crc.crc32(b"alpha"))


def test_single_bit_fix_is_provable_or_refused():
    payload = b"lab reading 42.5C"
    stored = crc.crc32(payload)
    damaged = bytearray(payload)
    damaged[3] ^= 0x04
    fixed = crc.single_bit_fix("crc32", bytes(damaged), stored)
    assert fixed is not None and fixed[0] == payload and fixed[1] == 3 * 8 + 2
    assert crc.single_bit_fix("sum8", bytes(damaged), stored) is None  # sums can't prove a fix


def test_rle_variant_found_by_round_trip():
    blobs = [rle.encode_pairs(b"aaaabbbcc"), rle.encode_pairs(b"zzzzzzzz")]
    assert rle.find_variant(blobs) == ["pairs"]


def test_xor_key_ranking():
    key = 0x5A
    samples = [xor.xor(t, bytes([key])) for t in (b"Student Name", b"Roll Number 12")]
    assert xor.rank_single_byte_keys(samples)[0][0] == key


def test_length_field_vs_lookalike():
    # Field at offset 0 is a real "length of rest" in every sample.
    samples = [struct.pack("<H", len(body)) + body for body in (b"abc", b"hello world", b"x" * 40)]
    v = evaluate("toy", "u16@0 is length of rest", samples,
                 lambda s: candidates.is_length_of_rest(s, 0, 2), log=False)
    assert v.accepted
    # A field that happens to match in one sample only is rejected.
    lookalike = [b"\x03\x00abc", b"\x01\x00hello"]
    v2 = evaluate("toy", "u16@0 is length of rest", lookalike,
                  lambda s: candidates.is_length_of_rest(s, 0, 2), log=False)
    assert v2.outcome == "rejected" and v2.counterexamples == [1]


def test_best_of_requires_a_single_survivor():
    samples = [b"\x05\x00abcde", b"\x02\x00xy", b"\x03\x00xyz"]
    winner = best_of("toy", "u16@0", samples, {
        "length of rest": lambda s: candidates.is_length_of_rest(s, 0, 2),
        "file size": lambda s: candidates.is_file_size(s, 0, 2),
    })
    assert winner == "length of rest"
