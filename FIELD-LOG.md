# FIELD-LOG

Dated log of every hypothesis we tried, including the ones that failed. Append rows as you go
(`python3 tools/log.py ...` does it for you). Outcomes: `accepted`, `rejected`, `open`.

| Time | Format | Hypothesis | Evidence | Outcome | By |
| --- | --- | --- | --- | --- | --- |
| 2026-10-16 10:11 | libra98 (stand-in) | bytes 0-7 are the magic 'LIBRA-98' | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | byte 8 is a version number, always 1 | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 9 is the record count: 20 + count*30 == file size | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u32 at 11 is a unix timestamp (1990-2010) | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 15 is the file size | held on 0/10 samples; counterexamples: samples [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 15 is the number of bytes after it | held on 0/10 samples; counterexamples: samples [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 15 is the length of the record area | held on 0/10 samples; counterexamples: samples [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | u16 at 15 == record_count*30 + 7 (meaning unknown) | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | bytes 17-19 are zero padding | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record u32 at +0 is an id counting up by 1 | held on 9/10 samples; counterexamples: samples [4] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record bytes +4..+23 are a NUL-padded name | held on 9/10 samples; counterexamples: samples [4] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record u16 at +24 is a DOS date (1985-2010) | held on 9/10 samples; counterexamples: samples [4] | rejected | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record u8 at +26 is a score 0-100 | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record u8 at +27 is a flag set (values 0-3) | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:11 | libra98 (stand-in) | record bytes +28..+29 are zero padding | held on 10/10 samples | accepted | Preetika |
| 2026-10-16 10:12 | libra98 (stand-in) | record u32 at +0 is an id counting up by 1 (undamaged files only; the 9/10 counterexample is libra98_1.damaged-zeroed_66_89, whose record 2 was wiped) | held on 6/6 samples | accepted | Preetika |
| 2026-10-16 10:12 | libra98 (stand-in) | record bytes +4..+23 are a NUL-padded name (undamaged files only; same counterexample) | held on 6/6 samples | accepted | Preetika |
| 2026-10-16 10:12 | libra98 (stand-in) | record u16 at +24 is a DOS date 1985-2010 (undamaged files only; same counterexample) | held on 6/6 samples | accepted | Preetika |
| 2026-10-16 15:41 | lablog | bytes 0-3 are the magic 4C 42 4C 47 ("LBLG") | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 15:41 | lablog | A5 5A is the block marker; first block at offset 6 | held on 6/6 samples; 37 blocks chain marker to marker to EOF; marker bytes inside payloads 0 times (resync must still check the CRC) | accepted | Khushi |
| 2026-10-16 15:41 | lablog | header u16le at 4 is the block count | held on 0/6 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 15:41 | lablog | header u16le at 4 is the file size | held on 0/6 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 15:41 | lablog | header u16le at 4 is the same in every file | held on 1/6 samples; fails on lablog_1.lbl, lablog_2.lbl, lablog_3.lbl, lablog_4.lbl, lablog_5.lbl | rejected | Khushi |
| 2026-10-16 15:41 | lablog | header u16be at 4 is the block count | held on 0/6 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 15:41 | lablog | header u16be at 4 is the file size | held on 0/6 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 15:41 | lablog | header u16be at 4 is the same in every file | held on 1/6 samples; fails on lablog_1.lbl, lablog_2.lbl, lablog_3.lbl, lablog_4.lbl, lablog_5.lbl | rejected | Khushi |
| 2026-10-16 15:41 | lablog | header bytes 4-5: meaning unknown | values 28 00, 29 00, 2a 00, 2b 00, 2c 00, 2d 00; not block count, file size or constant; keep unverified | open | Khushi |
| 2026-10-16 15:41 | lablog | u16be at marker+1 is the block length (block = length + 10) | walks all 37 blocks too, but no checksum algorithm matches every block under it, so its payload boundaries are wrong | rejected | Khushi |
| 2026-10-16 15:41 | lablog | u8 at marker+2 is the block length (block = length + 10) | walks all 37 blocks too, but no checksum algorithm matches every block under it, so its payload boundaries are wrong | rejected | Khushi |
| 2026-10-16 15:41 | lablog | u16le at marker+2 is the payload length (block = length + 10) | held on 6/6 samples; 37 blocks walk to EOF exactly and the checksum confirms the payload boundaries | accepted | Khushi |
| 2026-10-16 15:41 | lablog | u16le at marker+0 is a block sequence number counting up by 1 | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 15:41 | lablog | block sequence number (u16le at marker+0) starts at 0 | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 15:41 | lablog | checksum stored as u16le in the last 2 bytes of the block | no algorithm in recovery.crc (crc32, crc16_ccitt, sum8, sum16, xor8) matches every block over payload / length+payload / fields+length+payload / marker+...+payload (every algorithm 0/37) | rejected | Khushi |
| 2026-10-16 15:41 | lablog | checksum stored as u16be in the last 2 bytes of the block | no algorithm in recovery.crc (crc32, crc16_ccitt, sum8, sum16, xor8) matches every block over payload / length+payload / fields+length+payload / marker+...+payload (every algorithm 0/37) | rejected | Khushi |
| 2026-10-16 15:41 | lablog | checksum stored as u32le in the last 4 bytes of the block | no algorithm in recovery.crc (crc32, crc16_ccitt, sum8, sum16, xor8) matches every block over length+payload / fields+length+payload / marker+...+payload (every algorithm 0/37) | rejected | Khushi |
| 2026-10-16 15:41 | lablog | checksum stored as u32be in the last 4 bytes of the block | no algorithm in recovery.crc (crc32, crc16_ccitt, sum8, sum16, xor8) matches every block over payload / length+payload / fields+length+payload / marker+...+payload (every algorithm 0/37) | rejected | Khushi |
| 2026-10-16 15:41 | lablog | payload is printable ASCII text in every block | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 15:41 | lablog | payload is ';'-separated key=value pairs with keys t, temp, ph in that order | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 15:41 | lablog | checksum = crc32, stored u32le in the last 4 bytes of each block, over the payload | held on 6/6 samples; all 37 blocks match (guess_algorithm); other algorithms: crc16_ccitt 0/37, sum16 0/37, sum8 0/37, xor8 0/37 | accepted | Khushi |
