#!/usr/bin/env python3
"""Generate FORMAT-SPEC.md from templates/format_spec.md.j2 using Jinja2.
OWNER: Manas (delivery).

Usage:
    python tools/gen_format_spec.py [--out FORMAT-SPEC.md]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from salvage import formats  # noqa: F401  (registers decoders)
from salvage.core.reader import type_size
from salvage.core.registry import all_decoders


def render_format_spec() -> str:
    templates_dir = ROOT / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("format_spec.md.j2")
    return template.render(
        decoders=all_decoders(),
        type_size=type_size,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render FORMAT-SPEC.md from Jinja2 template")
    parser.add_argument("--out", type=Path, default=ROOT / "FORMAT-SPEC.md", help="Output path for rendered spec")
    args = parser.parse_args(argv)

    content = render_format_spec()
    args.out.write_text(content.strip() + "\n")
    print(f"Rendered {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
