#!/usr/bin/env python3
"""Append a hypothesis to FIELD-LOG.md.

    python3 tools/log.py lablog "u16 at 0x04 is block length" "matched 5/5 samples" accepted --by Khushi
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from salvage.evidence.ledger import main  # noqa: E402

main()
