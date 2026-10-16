"""Format decoders. Importing this package registers all of them.

One decoder per format in OUTPUT-CONTRACT.md; each Decoder.name is the contract format name.
To add a format: create a module with a @register'd Decoder, then import it below.
"""
from . import archives, cvt, documents, ebcdic, lablog, libra98, vault, wks  # noqa: F401
