import importlib
import os

import pyama_gui._qtwebengine_bootstrap as qtwebengine_bootstrap
from pyama_gui.qtwebengine import (
    configure_qtwebengine_environment,
    sanitize_qtwebengine_chromium_flags,
)


def test_sanitize_qtwebengine_chromium_flags_removes_empty_backend_flag() -> None:
    flags = "--skia-graphite-backend= --foo=bar"

    sanitized = sanitize_qtwebengine_chromium_flags(flags)

    assert "--skia-graphite-backend=" not in sanitized
    assert "--foo=bar" in sanitized
    assert "--disable-skia-graphite" in sanitized


def test_sanitize_qtwebengine_chromium_flags_preserves_explicit_graphite_choice() -> (
    None
):
    flags = "--enable-skia-graphite --foo=bar"

    sanitized = sanitize_qtwebengine_chromium_flags(flags)

    assert sanitized == "--enable-skia-graphite --foo=bar"


def test_configure_qtwebengine_environment_updates_env(
    monkeypatch,
) -> None:
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--skia-graphite-backend=")

    configure_qtwebengine_environment()

    assert os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] == "--disable-skia-graphite"


def test_qtwebengine_bootstrap_sanitizes_env_on_import(monkeypatch) -> None:
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--skia-graphite-backend=")

    importlib.reload(qtwebengine_bootstrap)

    assert os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] == "--disable-skia-graphite"
