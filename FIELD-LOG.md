# FIELD-LOG

Dated log of every hypothesis we tried, including the ones that failed. Append rows as you go
(`python3 tools/log.py ...` does it for you). Outcomes: `accepted`, `rejected`, `open`.

## Rehearsal on our stand-in samples (invented layout, superseded by the real samples below)

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
| 2026-10-16 16:15 | lablog | block layout for read_blocks: marker A5 5A, extra u16 seq, u16 payload length, crc32 stored u32le, covers payload; blocks start at offset 6 | all 6 clean samples decode with 0 damage, every field verified, and re-encode byte for byte | accepted | Khushi |
| 2026-10-16 16:15 | lablog | single-bit correction: CORRECTED only when exactly one bit flip, in the payload OR in the stored CRC, makes crc32 pass | lablog_1.damaged-flip0_bit797 corrected to the true payload; a flipped stored-CRC bit corrected in tests; 2000 random 2-bit errors in one block: 0 corrected (CRC-32 Hamming distance >= 6 at ~30-byte blocks) | accepted | Khushi |
| 2026-10-16 16:15 | lablog | single-bit correction over the payload only (bits of the stored CRC not tried) | a flip in the stored CRC then leaves an intact payload LOST; replaced by the rule above | rejected | Khushi |
| 2026-10-16 16:15 | lablog | length is verified when crc32 passes over exactly that many payload bytes | 0 wrong over 3000 tools/corrupt.py copies (50 seeds); a wrong length moves the CRC range and fails it | accepted | Khushi |
| 2026-10-16 16:15 | lablog | seq (outside the CRC) is verified only when it continues the count from an adjacent good block, or is 0 on the block at offset 6 | a flipped seq comes out unverified in tests; 0 wrong verified seq over 3000 corrupt.py copies | accepted | Khushi |
| 2026-10-16 16:15 | lablog | seq can be verified from the CRC alone | the CRC covers only the payload: a seq bit flip passes the CRC unnoticed | rejected | Khushi |
| 2026-10-16 16:15 | lablog | resync: never jump by a failed block's length; a marker counts only if a full block there passes its CRC | planted A5 5A + fake length inside a payload is skipped; inserted/deleted bytes resync to the next real block with exact lost ranges | accepted | Khushi |
| 2026-10-16 16:15 | lablog | false-recovery rate of the LABLOG decoder on damaged copies | 3000 corrupt.py copies (truncate, bit flip, zeroed, inserted, deleted; seeds 0-49): 30122 seq+payload values verified or corrected, 0 wrong; 2298 lost, 372 unverified | accepted | Khushi |
| 2026-10-16 18:31 | vault | bytes 0-3 are the magic 56 41 4C 54 ('VALT') | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 18:31 | vault | byte 5 is always 0 (high byte of a u16 count, or padding after a u8 count) | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 18:31 | vault | u16le at 4 is the entry count; index table of 24-byte entries starts at 6 | held on 6/6 samples; the first entry's offset points at the first byte after count entries; a u8 count fits too (byte 5 is always 0) | accepted | Khushi |
| 2026-10-16 18:31 | vault | u32 at entry+12 is the blob offset and u32 at entry+16 the stored blob size | held on 6/6 samples; blobs chain end to start and the last ends at EOF; NOTE: the size is 56 in every entry, so it is checked only by the chain, never by varying | accepted | Khushi |
| 2026-10-16 18:31 | vault | blobs tile the data area exactly: sorted by offset they start at the table end, touch end to start, and the last ends at EOF (no gaps, no overlaps) | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 18:31 | vault | blobs are RLE 'pairs': encode(decode(blob)) == blob for every blob | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 18:31 | vault | blobs are RLE 'packbits': encode(decode(blob)) == blob for every blob | held on 0/6 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 18:31 | vault | u32 at entry+20 is the decoded ('pairs') size of the blob | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 18:31 | vault | entry bytes 0-11 are a name XORed with the single-byte key 0x5C, NUL-padded | held on 6/6 samples; e.g. 'SND00.DAT', 'LVL01.DAT', 'MAP02.DAT' | accepted | Khushi |
| 2026-10-16 18:31 | vault | the XOR key is the same in every file (not one key per file) | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 18:31 | vault | the XOR key is per entry (each name needs a different key) | held on 0/6 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 18:31 | vault | blob contents are XORed too (decoded blobs are not printable text as stored) | held on 0/6 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 18:31 | vault | file size == 6 + count * 80 (true, but see the next row) | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 18:31 | vault | 80-byte fixed records are the real structure (what tools/survey.py proposes) | the size fits only because every blob packs to [56] bytes; the u32 at entry+12 points exactly at the end of a 24-byte-entry table in every sample, so the first count*24 bytes are an index and the rest are blobs | rejected | Khushi |
| 2026-10-16 18:31 | vault | blob content is verified when RLE re-encodes it exactly and it decodes to the index's size (no tiling condition) | rejected: 457 values verified wrong on 3000 tools/corrupt.py copies (408 after deletions, 33 after insertions, 16 zeroed): bytes deleted inside one blob shift later blobs, which still decode as pairs of the right size | rejected | Khushi |
| 2026-10-16 18:31 | vault | blob content is verified only when it round-trips, matches the decoded size, is non-empty AND the entries tile the file exactly | 3000 corrupt.py copies (seeds 0-49): 0 values verified wrong from structural damage; a file cut short is unverified too, because from the bytes alone it looks just like deleted bytes | accepted | Khushi |
| 2026-10-16 18:31 | vault | an empty blob (size 0, raw size 0) proves nothing | a zeroed index entry decodes to b'' and round-trips: 16 false 'verified' before this rule, 0 after | accepted | Khushi |
| 2026-10-16 18:31 | vault | names are verified only when one XOR key wins on every sample (recovery.xor.choose_key) and the name is clean NUL-padded text | key 0x5C agreed on all 6 clean samples; a sibling with a different key leaves names unverified (tested) | accepted | Khushi |
| 2026-10-16 18:31 | vault | false-recovery rate of the VAULT decoder on damaged copies | 3000 corrupt.py copies: 22445 values verified, 398 wrong (1.8%), ALL in-place bit flips or zeroing inside one name or literal blob byte, which no checksum-free file can reveal; 0 wrong from any other damage | accepted | Khushi |
| 2026-10-16 19:20 | pak | game archive format = Quake PAK (formats/pak.py) | chosen at H12: the only game-archive samples in hand (samples/pak, 6 clean + 10 damaged), a real public format, and shaped like VAULT (index table + blobs) so core.index.read_index is reused | accepted | Khushi |
| 2026-10-16 19:20 | pak | bytes 0-3 are the magic 50 41 43 4B ('PACK') | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 19:20 | pak | u32 at 4 is the directory offset and u32 at 8 its length in bytes: offset + length == file size (directory at the END) | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 19:20 | pak | the header is 12 bytes and the first blob starts right after it | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 19:20 | pak | the directory length is the same in every file (a constant is not a length) | held on 3/6 samples; fails on pak_2.pak, pak_4.pak, pak_5.pak | rejected | Khushi |
| 2026-10-16 19:20 | pak | directory = 64-byte entries; u32 at entry+56 is the blob offset, u32 at entry+60 its size | held on 6/6 samples; sorted by offset the blobs start right after the header, touch end to start, and end exactly where the directory begins | accepted | Khushi |
| 2026-10-16 19:20 | pak | blob sizes vary between entries (so the size field is evidence, not a constant) | held on 6/6 samples | accepted | Khushi |
| 2026-10-16 19:20 | pak | entry bytes 0-55 are a plain NUL-padded name (printable text, then zeros) | held on 6/6 samples; e.g. 'maps/start.bsp', 'sound/ambience.wav', 'progs/player.mdl' | accepted | Khushi |
| 2026-10-16 19:20 | pak | names are XOR-obfuscated (a non-zero key reads them best) | held on 0/6 samples; fails on every sample; best key per sample: 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 | rejected | Khushi |
| 2026-10-16 19:20 | pak | an entry has a flags / packed-size / checksum field | rejected: name 56 + offset 4 + size 4 = 64 of 64 bytes; 0 bytes left | rejected | Khushi |
| 2026-10-16 19:20 | pak | blob contents can be verified | rejected: no checksum, no compression to round-trip, no packed size to cross-check; blob bytes stay unverified (the guide's rule for archives without a checksum) | rejected | Khushi |
| 2026-10-16 19:20 | pak | when the header's directory offset disagrees with the file size, the directory is the last dir_length bytes | inserted/deleted bytes before the directory: names recovered on the committed samples (inserted_221_44, inserted_531_1, inserted_53_53); accepted only if its names are clean AND its entries tile the blob area | accepted | Khushi |
| 2026-10-16 19:20 | pak | a directory re-found at the end is confirmed by clean names alone | rejected: 7 names verified wrong on 3000 corrupt.py copies, where a byte moved inside the first entry's NUL padding and the shifted directory still read as text | rejected | Khushi |
| 2026-10-16 19:20 | pak | after the directory moved, only the first entry's name can hold the shift (it is unverified, the rest verified) | a shift inside any later name misaligns the entries before it and fails the tiling check; 0 wrong names from inserted/deleted bytes after this rule | accepted | Khushi |
| 2026-10-16 19:20 | pak | false-recovery rate of the PAK decoder on damaged copies | 3000 corrupt.py copies (seeds 0-49): 14639 name/offset/size values verified, 78 wrong (0.5%), ALL in-place bit flips or zeroing inside one name; 0 wrong from any other damage; blob contents never verified | accepted | Khushi |


## Real samples (real-samples/samples): one row per hypothesis, generated by tools/field_evidence.py

`open` = held on every file that shows it, but only one sample exists (the rule needs two).

| Time | Format | Hypothesis | Evidence | Outcome | By |
| --- | --- | --- | --- | --- | --- |
| 2026-10-16 13:24 | LIBRA-98 | bytes 0-3 are the magic 'LB98' [s01.dat, s02.dat, s03.dat, s04.dat, s29_almost_libra.dat] | held on 5/5 samples | accepted | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | u16 at 6 is the record count (= records in the file) [s01.dat, s02.dat, s03.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | u32 at 8 is a unix timestamp (1990-2000) [s01.dat, s02.dat, s03.dat, s04.dat] | held on 0/4 samples; counterexamples: samples [0, 1, 2, 3] | rejected | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | u16 at 8 + u16 at 10 are a DOS date + DOS time = expected 'created' [s01.dat, s04.dat] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | u16 at 12 is the data offset (first 0xA5 record marker there) [s01.dat, s02.dat, s03.dat, s04.dat] | held on 4/4 samples | accepted | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | record length byte = whole record size [s01.dat, s02.dat, s03.dat] | held on 0/3 samples; counterexamples: samples [0, 1, 2] | rejected | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | record length byte = bytes after the length byte (records tile to the END! trailer) [s01.dat, s02.dat, s03.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | record checksum = XOR of the record bytes [s01.dat, s02.dat, s03.dat] | held on 0/3 samples; counterexamples: samples [0, 1, 2] | rejected | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | record checksum = sum of marker..last field (mod 256) [s01.dat, s02.dat, s03.dat] | held on 0/3 samples; counterexamples: samples [0, 1, 2] | rejected | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | record checksum = sum of bytes after the length byte (mod 256) [s01.dat, s02.dat, s03.dat, s04.dat] | held on 4/4 samples | accepted | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | year is stored as-is (u16) [s01.dat, s02.dat, s03.dat] | held on 0/3 samples; counterexamples: samples [0, 1, 2] | rejected | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | year is stored as year - 1500 (Dracula 397 -> 1897) [s01.dat, s02.dat, s03.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | flags bit0 = checked_out: set exactly when a due date is present [s01.dat, s02.dat, s03.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | encoding flag 0 text is latin-1 [s02.dat] | held on 0/1 samples; counterexamples: samples [0] | rejected | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | encoding flag 0 text is cp437 (0x82 = e-acute in 'Miserables') [s02.dat] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | trailer 'END!' + u16 = sum of records only [s01.dat, s02.dat, s03.dat] | held on 0/3 samples; counterexamples: samples [0, 1, 2] | rejected | Preetika |
| 2026-10-16 13:24 | LIBRA-98 | trailer 'END!' + u16 = sum of every byte before the trailer (mod 65536) [s01.dat, s02.dat, s03.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | LABLOG | bytes 0-3 are the magic 'LLOG' [s05.dat, s06.dat, s07.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | LABLOG | u16 at 6 is the sample interval in ms [s05.dat] | held on 0/1 samples; counterexamples: samples [0] | rejected | Preetika |
| 2026-10-16 13:24 | LABLOG | u16 at 6 is the sample interval in 10 ms units (50 -> 500 ms) [s05.dat] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | LABLOG | u32 at 24 = seconds since 1970-01-01 [s05.dat] | held on 0/1 samples; counterexamples: samples [0] | rejected | Preetika |
| 2026-10-16 13:24 | LABLOG | u32 at 24 = seconds since 1990-01-01 [s05.dat] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | LABLOG | u16 at 30 = CRC-16/CCITT-FALSE of header bytes 0..29 [s05.dat, s06.dat, s07.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | LABLOG | block CRC covers the payload only [s05.dat, s06.dat] | held on 0/2 samples; counterexamples: samples [0, 1] | rejected | Preetika |
| 2026-10-16 13:24 | LABLOG | block CRC covers marker + type + length + payload [s05.dat, s06.dat] | held on 0/2 samples; counterexamples: samples [0, 1] | rejected | Preetika |
| 2026-10-16 13:24 | LABLOG | block CRC = CRC-16/CCITT-FALSE of type + length + payload (s07 block 4 is damaged: see next row) [s05.dat, s06.dat] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | LABLOG | s07 block 4 fails its CRC and exactly one flipped bit explains it (provable repair) [s07.dat] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | LABLOG | header u16 at 28 = number of blocks [s05.dat, s06.dat, s07.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | LABLOG | value = raw i16 * channel scale + channel offset (all 44 values of expected s05) [s05.dat] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | VAULT | bytes 0-3 are the magic 'VLT1' [s08.dat, s09.dat, s10.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | VAULT | index (u32 at 8) of 16-byte entries ends exactly at end of file [s08.dat, s09.dat, s10.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | VAULT | names XOR with a constant key [s08.dat, s09.dat, s10.dat] | held on 1/3 samples; counterexamples: samples [1, 2] | rejected | Preetika |
| 2026-10-16 13:24 | VAULT | names XOR with (key + i), length byte XOR'd too when header flag bit0 is set [s08.dat, s09.dat, s10.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | VAULT | entry flags bit0 = RLE-compressed (matches expected 'compressed') [s08.dat] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | VAULT | blob CRC-32 is over the stored (encoded) bytes [s08.dat, s09.dat] | held on 0/2 samples; counterexamples: samples [0, 1] | rejected | Preetika |
| 2026-10-16 13:24 | VAULT | blob CRC-32 is over the decoded data [s08.dat, s09.dat] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | VAULT | RLE90: 0x90 n = repeat the previous byte n times [s09.dat] | held on 0/1 samples; counterexamples: samples [0] | rejected | Preetika |
| 2026-10-16 13:24 | VAULT | RLE90: 0x90 n = repeat the previous byte n-1 more times; 0x90 0x00 = literal 0x90 [s08.dat, s09.dat, s10.dat] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | VAULT | bitmap payload = u8 width, u8 height, width*height pixels [s09.dat, s10.dat] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | VAULT | s10 sensor.bin fails its CRC-32 and exactly one flipped bit explains it [s10.dat] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | WKS | file starts with BOF (opcode 0, length 2, version 0x0404) [s11.wks, s12.wks, s13.wks] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | WKS | records (u16 opcode, u16 length, body) tile the file up to EOF [s11.wks, s12.wks] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | WKS | formula body = f64 cached value, u16 length, formula bytes (matches expected s11) [s11.wks] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | WKS | unknown opcode 0x00FA in s12 is a valid record we can skip (lengths still tile) [s12.wks] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | CVT | signature 'PRG formatted GEOS file' at offset 30 [s18.cvt, s19.cvt] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | CVT | name is PETSCII with case swapped (expected 'Notes v2') [s18.cvt] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | CVT | year byte = year - 1900 (91 -> 1991, 101 -> 2001) [s18.cvt, s19.cvt] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | CVT | declared blocks = 254-byte blocks after the first [s18.cvt, s19.cvt] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | CVT | vlir bytes-used = stored value - 1 (as on a real 1541 disk) [s19.cvt] | held on 0/1 samples; counterexamples: samples [0] | rejected | Preetika |
| 2026-10-16 13:24 | CVT | vlir bytes-used = stored value as-is ('First record, short.' keeps its '.') [s19.cvt] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | EBCDIC-DUMP | text is EBCDIC code page 037 [s20.000, s21.000, s22.000] | held on 3/3 samples | accepted | Preetika |
| 2026-10-16 13:24 | EBCDIC-DUMP | RDW = u16 big-endian length incl. the 4-byte RDW, then 00 00 [s20.000, s22.000] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | EBCDIC-DUMP | s21 is blocked: BDW (u16be length, 00 00) wraps RDW records [s21.000] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | EBCDIC-DUMP | credits are packed decimal [s20.000] | held on 0/1 samples; counterexamples: samples [0] | rejected | Preetika |
| 2026-10-16 13:24 | EBCDIC-DUMP | credits are a u16 big-endian binary number (00 28 -> 40) [s20.000] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | EBCDIC-DUMP | trailer count and credits total equal the detail records [s20.000, s21.000] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | WPD | u32 at 4 is the text start (48) [s14.wpd, s15.wpd] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | WPD | summary packet index at 0x1E: u16 type 1, u16 length, u32 offset (s14: text ends there) [s14.wpd] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | WPD | s15 is truncated: its index points at byte 223 but the file is 136 bytes [s15.wpd] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | WPD | u16 at 12 is an encryption key (0 = not protected) [s14.wpd, s15.wpd] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | BRAVO | text, ^Z, then format runs [s16.bravo, s17.bravo] | held on 2/2 samples | accepted | Preetika |
| 2026-10-16 13:24 | BRAVO | run table length counts bytes [s16.bravo] | held on 0/1 samples; counterexamples: samples [0] | rejected | Preetika |
| 2026-10-16 13:24 | BRAVO | run table length counts 16-bit words (s16: 6 words = 12 bytes, exactly) [s16.bravo] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | BRAVO | run = u16be start, u16be length, u8 looks, u8 font ('Alto users' at 4, length 10) [s16.bravo] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | WAD | PWAD header: i32 count, i32 directory offset; 16-byte entries end at EOF [s23.wad] | held on 1/1 samples | open | Preetika |
| 2026-10-16 13:24 | PAK | PACK header: i32 directory offset, i32 length; 64-byte entries end at EOF [s24.pak] | held on 1/1 samples | open | Preetika |
| 2026-10-16 19:46 | LABLOG | bytes 0-4 are the magic 4C 4C 4F 47 01 | held on 2/2 samples | accepted | Khushi |
| 2026-10-16 19:46 | LABLOG | B1 is the block marker; first block at offset 32 | held on 2/2 samples; 15 blocks chain marker to marker to EOF; marker bytes inside payloads 4 times (resync must still check the CRC) | accepted | Khushi |
| 2026-10-16 19:46 | LABLOG | header u16le at 5 is the block count | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u16le at 5 is the file size | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u16le at 5 is the same in every file | held on 1/2 samples; fails on s06.dat | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u16be at 5 is the block count | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u16be at 5 is the file size | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u16be at 5 is the same in every file | held on 1/2 samples; fails on s06.dat | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u32le at 5 is the block count | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u32le at 5 is the file size | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u32le at 5 is the same in every file | held on 1/2 samples; fails on s06.dat | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u32be at 5 is the block count | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u32be at 5 is the file size | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header u32be at 5 is the same in every file | held on 1/2 samples; fails on s06.dat | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | header bytes 5-31: meaning unknown | values 02 32 00 54 48 45 52 4d 4f 20 4c 4f 47 47 45 52 00 00 00 1f 19 39 05 07 00 52 ef, 03 64 00 46 4c 4f 57 43 45 4c 4c 2d 32 00 00 00 00 00 00 5a 63 e6 06 08 00 68 02; not block count, file size or constant; keep unverified | open | Khushi |
| 2026-10-16 19:46 | LABLOG | u8 at marker+1 is the block length (block = length + 6) | walks all 15 blocks and the checksum matches too: the samples cannot tell it from u16le@+1 | open | Khushi |
| 2026-10-16 19:46 | LABLOG | u16le at marker+1 is the payload length (block = length + 6) | 15 blocks walk to EOF exactly and the checksum matches, but so does u8@+1 (every length < 256 and the checksum covers both bytes); widest reading kept | open | Khushi |
| 2026-10-16 19:46 | LABLOG | checksum stored as u16le in the last 2 bytes of the block | no algorithm in recovery.crc (crc32, crc16_ccitt, sum8, sum16, xor8) matches every block over payload / length+payload / marker+...+payload (every algorithm 0/15) | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | checksum stored as u16be in the last 2 bytes of the block | no algorithm in recovery.crc (crc32, crc16_ccitt, sum8, sum16, xor8) matches every block over payload / length+payload / fields+length+payload / marker+...+payload (every algorithm 0/15) | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | checksum stored as u32le in the last 4 bytes of the block | no algorithm in recovery.crc (crc32, crc16_ccitt, sum8, sum16, xor8) matches every block over payload / length+payload / fields+length+payload / marker+...+payload (every algorithm 0/15) | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | checksum stored as u32be in the last 4 bytes of the block | no algorithm in recovery.crc (crc32, crc16_ccitt, sum8, sum16, xor8) matches every block over payload / length+payload / fields+length+payload / marker+...+payload (every algorithm 0/15) | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | payload is printable ASCII text in every block | held on 0/2 samples; fails on every sample | rejected | Khushi |
| 2026-10-16 19:46 | LABLOG | checksum = crc16_ccitt, stored u16le in the last 2 bytes of each block, over the fields+length+payload | held on 2/2 samples; all 15 blocks match (guess_algorithm); other algorithms: crc32 0/15, sum16 0/15, sum8 0/15, xor8 0/15 | accepted | Khushi |
| 2026-10-16 19:46 | LABLOG | s07 is left out of the probe: it holds a real damaged block | one block of s07 fails CRC-16 and is repaired by exactly one bit flip (formats/lablog.py); a damaged sample would veto 'matches every block' | open | Khushi |
| 2026-10-16 19:46 | VAULT | the file-name extension agrees with the type byte: .txt = text, .bin = binary, .bmp8 = bitmap | holds on all 9 entries of s08-s10; used as a value check (extensions not seen in the samples are not judged) | accepted | Khushi |
| 2026-10-16 19:46 | VAULT | an entry flagged compressed always contains an RLE90 escape (0x90) | rejected: s08 and s10 report.txt are flagged compressed (flags 3) but stored at full size with no escape | rejected | Khushi |
| 2026-10-16 19:46 | VAULT | false recoveries on 1-3 random bit flips (tools/false_recovery.py, 400 per file) | 94 of 3515 records verified wrong (2.67%); all but one are flips inside a name: the name table has no checksum and a flip that keeps a plausible name cannot be seen | accepted | Khushi |
| 2026-10-16 19:46 | PAK | entries with data tile [12, directory) exactly; an entry next to a break in the tiling is not verified | s24 tiles exactly (12-132-142-219); false recoveries 337 -> 315 (21.3% -> 19.9%) at a cost of 49 right ones; the rest are flips inside file data or names (no checksum) | accepted | Khushi |
| 2026-10-16 19:46 | WAD | lumps with data tile [12, directory) exactly (zero-size markers skipped); an entry next to a break is not verified | s23 tiles exactly (12-76-116-206-214); false recoveries 421 -> 387 (15.2% -> 13.9%) at a cost of 124 right ones | accepted | Khushi |
| 2026-10-16 19:46 | PAK | blob contents (sha256) of a checksum-less archive can be reported as verified | open: about 60% of PAK and 80% of WAD false recoveries are flips inside file data, which no check in the format can see; the guide says at most unverified, the current decoder says verified (team decision) | open | Khushi |
