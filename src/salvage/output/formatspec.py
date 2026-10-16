"""Generate FORMAT-SPEC.md from the spec library. OWNER: Manas (delivery).

Run:  python -m salvage.output.formatspec > FORMAT-SPEC.md   (or: make spec)
Each section is built from the decoder itself: the layout written at the top of its module, and
its FormatSpec (fields with evidence). The document can never drift from the code.
"""
from __future__ import annotations

import inspect
import sys

from .. import formats  # noqa: F401  (registers decoders)
from ..core.registry import all_decoders
from ..core.spec import spec_to_markdown

ORDER = ["LIBRA-98", "LABLOG", "VAULT", "WKS", "WPD", "BRAVO", "CVT", "EBCDIC-DUMP", "WAD", "PAK"]

HEADER = """# FORMAT-SPEC

Generated from the decoders in `src/salvage/formats/` with `make spec`. Do not edit by hand.
Every claim is tested against the organisers' real samples (`real-samples/samples/`); the
hypotheses, including the rejected ones, are in `FIELD-LOG.md` (regenerate with
`python3 tools/field_evidence.py`).

Output follows `real-samples/OUTPUT-CONTRACT.md`: per file `status` is ok / partial / unsupported /
unrecognized / failed; `damage[].kind` uses the contract vocabulary; a record that could not be
verified carries `"verified": false` and its `"issues"`. A damage entry with `"lossy": false` was
found and fully repaired (a provable single-bit fix) or did not lose data.

| Format | Files | Integrity check used for verification |
| --- | --- | --- |
"""


def _layout(dec) -> str:
    doc = inspect.getdoc(sys.modules[type(dec).__module__]) or ""
    lines = doc.splitlines()
    body = "\n".join(lines[1:]).strip()       # first line is the module title
    return "```\n" + body + "\n```\n" if body else ""


def render() -> str:
    decs = {d.name: d for d in all_decoders() if d.ready}
    names = [n for n in ORDER if n in decs] + sorted(n for n in decs if n not in ORDER)
    hints = {"LIBRA-98": "s01-s04, s29", "LABLOG": "s05-s07", "VAULT": "s08-s10", "WKS": "s11-s13",
             "WPD": "s14-s15", "BRAVO": "s16-s17", "CVT": "s18-s19", "EBCDIC-DUMP": "s20-s22",
             "WAD": "s23", "PAK": "s24"}
    parts = [HEADER + "".join(f"| {n} | {hints.get(n, '')} | {decs[n].spec.checksum or 'structure'} |\n"
                              for n in names)]
    for n in names:
        dec = decs[n]
        md = spec_to_markdown(dec.spec)
        head, _, rest = md.partition("\n")
        parts.append(head + "\n\n" + _layout(dec) + rest)
    parts.append("""## UNKNOWN

Files no decoder recognises (s25 random, s26 empty, s27 text, s28 one byte, s30 PNG) get
`format: UNKNOWN`, `status: unrecognized`, no records, and `metadata` describing the bytes
(size, entropy, what it looks like, readable strings). s29 starts with the LIBRA-98 magic but is
7 bytes long, so it is recognised and `failed` (header truncated).
""")
    return "\n".join(parts)


if __name__ == "__main__":
    print(render(), end="")
