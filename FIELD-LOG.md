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
