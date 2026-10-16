# FIELD-LOG

Dated log of every hypothesis we tried, including the ones that failed. Append rows as you go
(`python3 tools/log.py ...` does it for you). Outcomes: `accepted`, `rejected`, `open`.

| Time | Format | Hypothesis | Evidence | Outcome | By |
| --- | --- | --- | --- | --- | --- |
| 2026-10-16 15:59 | libra98 | Bytes 9-10 (little-endian) are the record count | size = 20 + 30*count holds in 6 of 6 files; big-endian gives nonsense. By hand, awaiting checker verdict | open | Bhupesh |
| 2026-10-16 15:59 | libra98 | Header is 20 bytes, each record is 30 bytes, no trailer | All 46 records in 6 files fit exactly; last bytes of each file are the last record tail. By hand, awaiting checker verdict | open | Bhupesh |
| 2026-10-16 15:59 | libra98 | Record ID (4 bytes LE) equals 1000 + position in file | 46 of 46 records; names differ per file so ID is positional, not a member key. By hand, awaiting checker verdict | open | Bhupesh |
| 2026-10-16 15:59 | libra98 | Byte 15 is an 8-bit checksum or CRC | Tried 6 byte ranges x 13 algorithms (sum, xor, negsum, 10 CRC-8 variants); best was 1 of 6 files, which is chance level | rejected | Bhupesh |
| 2026-10-16 15:59 | libra98 | Bytes 12-14 are a counter or timestamp | Value rises about 5738 per file across 6 files; unit and epoch unknown | open | Bhupesh |
| 2026-10-16 15:59 | libra98 | Byte 11 is a flag or type code | Alternates 80/00 with file number; meaning unknown, may be a generator artifact | open | Bhupesh |
| 2026-10-16 15:59 | libra98 | Bytes 16-19 hold a size or count flag | Byte 16 is 1 only in the three largest files; several readings fit all 6, need a file with 16+ records to separate them | open | Bhupesh |
| 2026-10-16 15:59 | libra98 | Record offset +24 (2 bytes) is a date or an amount | Values about 5200-9100; days since 1970, days since 1980 and a plain amount all fit every sample; organisers' spec needed | open | Bhupesh |
| 2026-10-16 16:10 | libra98 | checker: bytes 9-10 is record count, little-endian | held on 6/6 samples | accepted | Bhupesh |
| 2026-10-16 16:10 | libra98 | checker: bytes 9-10 is record count, big-endian | held on 0/6 samples; counterexamples: samples [0, 1, 2, 3, 4, 5] | rejected | Bhupesh |
| 2026-10-16 16:10 | libra98 | checker: bytes 9-10 is length of rest of file | held on 0/6 samples; counterexamples: samples [0, 1, 2, 3, 4, 5] | rejected | Bhupesh |
| 2026-10-16 16:10 | libra98 | checker: bytes 9-10 is total file size | held on 0/6 samples; counterexamples: samples [0, 1, 2, 3, 4, 5] | rejected | Bhupesh |
| 2026-10-16 16:10 | libra98 | checker: record ID is 1000 + position (little-endian) | held on 6/6 samples | accepted | Bhupesh |
| 2026-10-16 16:10 | libra98 | checker: record offset +24 is plausible DOS date, little-endian | held on 6/6 samples | accepted | Bhupesh |
| 2026-10-16 16:10 | libra98 | checker: record offset +24 is plausible DOS date, big-endian | held on 0/6 samples; counterexamples: samples [0, 1, 2, 3, 4, 5] | rejected | Bhupesh |
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
