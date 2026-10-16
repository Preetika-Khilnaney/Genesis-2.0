"""Optional local-model layout proposer (--discover). OWNER: Bhupesh. ROADMAP, not needed today.

Design: Liquid LFM2 (GGUF) via llama.cpp, fully offline, output grammar-constrained to
FieldSpec syntax. It only PROPOSES candidate layouts; checker.evaluate decides.
Never called in the default run path.
"""
from __future__ import annotations


def propose_layouts(samples: list[bytes]) -> list[dict]:
    raise NotImplementedError("LFM2 proposer is roadmap; see README 'Roadmap'")
