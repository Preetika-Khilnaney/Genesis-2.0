"""Format decoders. Importing this package registers all of them.

To add a format: create a module here with a @register'd Decoder, then import it below.
"""
from . import game_archive, lablog, libra98, realworld, vault  # noqa: F401
