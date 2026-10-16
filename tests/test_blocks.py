"""Generic block reader: CRC gate, single-bit correction, resync, truncation."""
from salvage.core.blocks import BlockLayout, block_structure_score, read_blocks
from salvage.core.model import DamageCause, FieldStatus
from salvage.core.reader import ByteWriter
from salvage.core.spec import FieldSpec
from salvage.recovery.crc import crc32

LAYOUT = BlockLayout(marker=b"BLK", extra=[FieldSpec("seq", "u16")], length_type="u16",
                     checksum_algo="crc32", checksum_type="u32", checksum_covers="payload")


def block(seq: int, payload: bytes) -> bytes:
    w = ByteWriter()
    w.write("bytes", b"BLK")
    w.write("u16", seq)
    w.write("u16", len(payload))
    w.write("bytes", payload)
    w.write("u32", crc32(payload))
    return w.getvalue()


PAYLOADS = [b"temp=21.5C", b"temp=22.0C", b"temp=22.4C"]
CLEAN = b"".join(block(i, p) for i, p in enumerate(PAYLOADS))


def test_clean_blocks_all_verified():
    scan = read_blocks(CLEAN, LAYOUT)
    assert [b.payload for b in scan.blocks] == PAYLOADS
    assert all(b.status == FieldStatus.VERIFIED for b in scan.blocks)
    assert scan.blocks[1].header["seq"].value == 1
    assert not scan.damage and scan.coverage(len(CLEAN)) == 1.0


def test_single_bit_flip_in_payload_is_corrected():
    data = bytearray(CLEAN)
    first_payload = 3 + 2 + 2
    data[first_payload + 2] ^= 0x10
    scan = read_blocks(bytes(data), LAYOUT)
    b0 = scan.blocks[0]
    assert b0.status == FieldStatus.CORRECTED and b0.payload == PAYLOADS[0]
    assert "single-bit fix at payload byte 2, bit 4" in b0.note
    assert not scan.damage


def test_bad_block_lost_and_resynced():
    data = bytearray(CLEAN)
    b1 = len(block(0, PAYLOADS[0]))
    data[b1 + 7] ^= 0xFF                 # 8 bits wrong in block 1's payload: not fixable
    data[b1 + 8] ^= 0xFF
    scan = read_blocks(bytes(data), LAYOUT)
    statuses = [b.status for b in scan.blocks]
    assert statuses == [FieldStatus.VERIFIED, FieldStatus.LOST, FieldStatus.VERIFIED]
    assert scan.blocks[1].payload == b""                     # nothing invented
    d = scan.damage[0]
    assert d.cause == DamageCause.CRC_FAIL and d.start == b1 and d.end == 2 * b1
    assert scan.blocks[2].payload == PAYLOADS[2]


def test_corrupted_length_resyncs_on_marker():
    data = bytearray(CLEAN)
    b1 = len(block(0, PAYLOADS[0]))
    data[b1 + 5] = 0xFF                  # block 1 length -> 0xFFxx, runs past the file
    data[b1 + 6] = 0xFF
    scan = read_blocks(bytes(data), LAYOUT)
    assert scan.blocks[-1].payload == PAYLOADS[2] and scan.blocks[-1].status == FieldStatus.VERIFIED
    assert scan.damage[0].start == b1 and scan.damage[0].cause.value == "bad_length"


def test_truncated_last_block():
    scan = read_blocks(CLEAN[:-6], LAYOUT)
    assert len(scan.blocks) == 2
    assert scan.damage[-1].cause == DamageCause.TRUNCATED


def test_garbage_between_blocks_is_reported():
    data = block(0, PAYLOADS[0]) + b"\x00\x13\x37junk" + block(1, PAYLOADS[1])
    scan = read_blocks(data, LAYOUT)
    assert [b.payload for b in scan.blocks] == PAYLOADS[:2]
    assert scan.damage[0].cause == DamageCause.BAD_OFFSET


def test_checksum_covering_whole_block():
    layout = BlockLayout(marker=b"BK", length_type="u8", checksum_algo="crc16_ccitt",
                         checksum_type="u16", checksum_covers="all")
    from salvage.recovery.crc import crc16_ccitt
    body = b"BK" + bytes([3]) + b"abc"
    data = body + crc16_ccitt(body).to_bytes(2, "little")
    scan = read_blocks(data, layout)
    assert scan.blocks[0].status == FieldStatus.VERIFIED and scan.blocks[0].payload == b"abc"


def test_structure_score_for_fingerprint_fallback():
    assert block_structure_score(CLEAN, LAYOUT) == 1.0
    assert block_structure_score(bytes(range(256)), LAYOUT) == 0.0
