"""Format decoders. Importing this package registers all of them.

To add a format: create a module here with a @register'd Decoder, then import it below.
"""
from . import lablog, libra98, pak, realworld, vault  # noqa: F401
