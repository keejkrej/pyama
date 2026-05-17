"""Source reader adapters."""

from .base import ImageInfo, ReaderAdapter, ReaderSession
from .registry import open_reader, resolve_reader_adapter

__all__ = ["ImageInfo", "ReaderAdapter", "ReaderSession", "open_reader", "resolve_reader_adapter"]
