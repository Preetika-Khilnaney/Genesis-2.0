"""Two-pass CLI: each decoder sees the other files of its format as context."""
import json

from salvage.cli import main
from salvage.core.model import FileResult
from salvage.core.registry import DecodeContext, Decoder, register
from salvage.core.spec import FormatSpec

SEEN: dict[str, list[str]] = {}


@register
class _CtxProbe(Decoder):
    """Test-only decoder: records which siblings it was given."""
    name = "ctx_probe"
    spec = FormatSpec(name="ctx_probe", magic=b"CTXPROBE")
    ready = True

    def decode(self, path: str, data: bytes, ctx: DecodeContext | None = None) -> FileResult:
        SEEN[path] = sorted(p for p, _ in ctx.siblings)
        assert ctx.sample_count == len(ctx.samples(data))
        return FileResult(source_file=path, format=self.name)


@register
class _Crasher(Decoder):
    """Test-only decoder that always crashes: the run must survive it."""
    name = "ctx_crasher"
    spec = FormatSpec(name="ctx_crasher", magic=b"CRASHME!")
    ready = True

    def decode(self, path, data, ctx=None):
        raise RuntimeError("boom")


def test_decoder_receives_same_format_siblings_only(tmp_path):
    inp, out = tmp_path / "in", tmp_path / "out"
    (inp / "sub").mkdir(parents=True)
    (inp / "a.bin").write_bytes(b"CTXPROBE" + b"\x01" * 20)
    (inp / "b.bin").write_bytes(b"CTXPROBE" + b"\x02" * 20)
    (inp / "sub" / "c.bin").write_bytes(b"CTXPROBE" + b"\x03" * 20)
    (inp / "other.dat").write_bytes(b"not a probe file")
    assert main([str(inp), str(out)]) == 0
    assert SEEN["a.bin"] == ["b.bin"]          # sub-directories are not read (OUTPUT-CONTRACT.md)
    assert SEEN["b.bin"] == ["a.bin"]
    assert "sub/c.bin" not in SEEN and "other.dat" not in SEEN


def test_crashing_decoder_is_isolated(tmp_path):
    inp, out = tmp_path / "in", tmp_path / "out"
    inp.mkdir()
    (inp / "x.bin").write_bytes(b"CRASHME!" + b"\x00" * 8)
    (inp / "y.bin").write_bytes(b"CTXPROBE" + b"\x00" * 8)
    assert main([str(inp), str(out)]) == 0
    x = json.loads((out / "x.bin.json").read_text())
    y = json.loads((out / "y.bin.json").read_text())
    assert x["status"] == "failed" and "boom" in x["error"]
    assert "error" not in y
    assert {f["file"]: f["status"] for f in json.loads((out / "report.json").read_text())["files"]}["x.bin"] == "failed"
