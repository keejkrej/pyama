"""Helpers for configuring Qt WebEngine before the first WebEngine import."""

import os
import shlex


_GRAPHITE_FLAGS = {
    "--enable-skia-graphite",
    "--disable-skia-graphite",
}
_GRAPHITE_PREFIXES = (
    "--skia-graphite-backend=",
    "--skia-graphite-dawn-backend=",
)


def _is_empty_graphite_backend_flag(flag: str) -> bool:
    return any(flag == prefix for prefix in _GRAPHITE_PREFIXES)


def _has_graphite_override(flag: str) -> bool:
    return flag in _GRAPHITE_FLAGS or any(
        flag.startswith(prefix) and not _is_empty_graphite_backend_flag(flag)
        for prefix in _GRAPHITE_PREFIXES
    )


def sanitize_qtwebengine_chromium_flags(flags: str) -> str:
    """Remove invalid Graphite flags and default to Ganesh-backed rendering."""

    tokens = [
        token
        for token in shlex.split(flags)
        if not _is_empty_graphite_backend_flag(token)
    ]
    if not any(_has_graphite_override(token) for token in tokens):
        tokens.append("--disable-skia-graphite")
    return shlex.join(tokens)


def configure_qtwebengine_environment() -> None:
    """Apply Chromium flag defaults before Qt WebEngine initializes."""

    current_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = sanitize_qtwebengine_chromium_flags(
        current_flags
    )
