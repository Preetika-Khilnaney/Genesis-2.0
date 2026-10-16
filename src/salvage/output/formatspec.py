"""Generate FORMAT-SPEC.md from the spec library. OWNER: Manas (delivery).

Run:  python -m salvage.output.formatspec > FORMAT-SPEC.md
Hand-written prose goes in each FormatSpec's `description` and `notes`,
so the document can never drift from the code.
"""
from __future__ import annotations

from .. import formats  # noqa: F401  (registers decoders)
from ..core.registry import all_decoders
from ..core.spec import spec_to_markdown

HEADER = """# FORMAT-SPEC

Generated from the spec library (`src/salvage/formats/`). Do not edit by hand:
change the FormatSpec and regenerate with `make spec`.

Field statuses used in outputs: `verified`, `corrected`, `unverified`, `lost`.
"""


def render() -> str:
    parts = [HEADER]
    for dec in all_decoders():
        if dec.spec is None:
            parts.append(f"## {dec.name}\n\n_Spec not written yet._\n")
        else:
            status = "" if dec.ready else "\n_Status: in progress (decoder not ready)._\n"
            parts.append(spec_to_markdown(dec.spec) + status)
    return "\n".join(parts)


if __name__ == "__main__":
    print(render(), end="")
