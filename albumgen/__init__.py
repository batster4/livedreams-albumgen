"""albumgen: story and prompt generator for one-reference canvas albums."""

from .config import Config
from .pipeline import AlbumResult, make_album

__all__ = ["Config", "AlbumResult", "make_album"]
__version__ = "1.0.0"
