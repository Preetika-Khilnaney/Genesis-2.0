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
