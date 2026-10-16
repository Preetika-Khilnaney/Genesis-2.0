"""Bounds-checked byte reader and writer. OWNER: Preetika (core). SHARED INTERFACE.

Every read goes through ByteReader so nothing can read past the end of a file.
A failed read raises OutOfBounds, which decoders turn into a TRUNCATED damage entry.
"""
from __future__ import annotations

import struct
from datetime import datetime, timezone


class OutOfBounds(Exception):
    def __init__(self, offset: int, need: int, size: int):
        super().__init__(f"read of {need} bytes at offset {offset} exceeds size {size}")
        self.offset, self.need, self.size = offset, need, size


# type name -> (struct code, size). Endianness is added by the reader.
_FIXED = {
    "u8": ("B", 1), "i8": ("b", 1),
    "u16": ("H", 2), "i16": ("h", 2),
    "u32": ("I", 4), "i32": ("i", 4),
    "u64": ("Q", 8), "i64": ("q", 8),
    "f32": ("f", 4), "f64": ("d", 8),
}


def type_size(type_name: str) -> int | None:
    """Fixed size of a type, or None for variable-length types."""
    base = type_name.removesuffix("le").removesuffix("be")
    if base in _FIXED:
        return _FIXED[base][1]
    if type_name in ("dos_date", "dos_time"):
        return 2
    if type_name == "unix32":
        return 4
    return None


def _split(type_name: str, default_endian: str) -> tuple[str, str]:
    if type_name.endswith("le"):
        return type_name[:-2], "<"
    if type_name.endswith("be"):
        return type_name[:-2], ">"
    return type_name, "<" if default_endian == "little" else ">"


class ByteReader:
    def __init__(self, data: bytes, endian: str = "little"):
        self.data = data
        self.pos = 0
        self.endian = endian

    @property
    def size(self) -> int:
        return len(self.data)

    def remaining(self) -> int:
        return self.size - self.pos

    def seek(self, offset: int) -> None:
        if offset < 0 or offset > self.size:
            raise OutOfBounds(offset, 0, self.size)
        self.pos = offset

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > self.size:
            raise OutOfBounds(self.pos, n, self.size)
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def peek(self, n: int) -> bytes:
        return self.data[self.pos:self.pos + n]

    def read(self, type_name: str, length: int | None = None, encoding: str = "latin-1"):
        """Read one value. Supported types:
        u8 i8 u16 i16 u32 i32 u64 i64 f32 f64 (suffix le/be to force endianness),
        bytes (needs length), str (fixed length, NUL-trimmed), cstr (NUL-terminated),
        pstr8 / pstr16 (length-prefixed), dos_date, dos_time, unix32.
        """
        base, endian = _split(type_name, self.endian)
        if base in _FIXED:
            code, size = _FIXED[base]
            return struct.unpack(endian + code, self.take(size))[0]
        if type_name == "bytes":
            return self.take(_need(length, type_name))
        if type_name == "str":
            return self.take(_need(length, type_name)).split(b"\x00", 1)[0].decode(encoding, "replace")
        if type_name == "cstr":
            end = self.data.find(b"\x00", self.pos)
            if end < 0:
                raise OutOfBounds(self.pos, self.size - self.pos + 1, self.size)
            raw = self.take(end - self.pos)
            self.take(1)
            return raw.decode(encoding, "replace")
        if type_name in ("pstr8", "pstr16"):
            n = self.read("u8" if type_name == "pstr8" else "u16")
            return self.take(n).decode(encoding, "replace")
        if type_name == "dos_date":
            v = self.read("u16")
            return f"{1980 + (v >> 9):04d}-{(v >> 5) & 0xF:02d}-{v & 0x1F:02d}"
        if type_name == "dos_time":
            v = self.read("u16")
            return f"{v >> 11:02d}:{(v >> 5) & 0x3F:02d}:{(v & 0x1F) * 2:02d}"
        if type_name == "unix32":
            v = self.read("u32")
            return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
        raise ValueError(f"unknown type {type_name!r}")


def _need(length: int | None, type_name: str) -> int:
    if length is None:
        raise ValueError(f"type {type_name!r} needs a length")
    return length


class ByteWriter:
    """Inverse of ByteReader for round-trip tests. Only exact-inverse types are supported."""

    def __init__(self, endian: str = "little"):
        self.buf = bytearray()
        self.endian = endian

    def write(self, type_name: str, value, length: int | None = None, encoding: str = "latin-1") -> None:
        base, endian = _split(type_name, self.endian)
        if base in _FIXED:
            self.buf += struct.pack(endian + _FIXED[base][0], value)
        elif type_name == "bytes":
            self.buf += bytes(value)
        elif type_name == "str":
            raw = value.encode(encoding)
            n = _need(length, type_name)
            self.buf += raw[:n].ljust(n, b"\x00")
        elif type_name == "cstr":
            self.buf += value.encode(encoding) + b"\x00"
        elif type_name in ("pstr8", "pstr16"):
            raw = value.encode(encoding)
            self.write("u8" if type_name == "pstr8" else "u16", len(raw))
            self.buf += raw
        elif type_name == "dos_date":
            y, m, d = (int(x) for x in value.split("-"))
            self.write("u16", ((y - 1980) << 9) | (m << 5) | d)
        elif type_name == "dos_time":
            h, mi, s = (int(x) for x in value.split(":"))
            self.write("u16", (h << 11) | (mi << 5) | (s // 2))
        elif type_name == "unix32":
            self.write("u32", int(datetime.fromisoformat(value).timestamp()))
        else:
            raise ValueError(f"unknown type {type_name!r}")

    def getvalue(self) -> bytes:
        return bytes(self.buf)
