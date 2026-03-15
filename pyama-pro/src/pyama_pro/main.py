#!/usr/bin/env python3
"""Application entry-point wiring together the PyAMA-Pro consolidated widgets."""

# =============================================================================
# IMPORTS
# =============================================================================

import argparse
from importlib import import_module
import logging
import multiprocessing as mp
import sys

from PySide6.QtWidgets import QApplication


# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================


def main() -> None:
    """Spin up the Qt event loop and show the primary application window."""
    # ------------------------------------------------------------------------
    # COMMAND LINE ARGUMENTS
    # ------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="PyAMA-Pro microscopy modeling and statistics application"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # ------------------------------------------------------------------------
    # LOGGING CONFIGURATION (do this first!)
    # ------------------------------------------------------------------------
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Suppress noisy matplotlib debug messages
    matplotlib_logger = logging.getLogger("matplotlib.font_manager")
    matplotlib_logger.setLevel(logging.INFO)

    # Also suppress matplotlib verbose output
    verbose_logger = logging.getLogger("matplotlib")
    verbose_logger.setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        "Starting PyAMA-Pro (level=%s, debug=%s)",
        logging.getLevelName(log_level),
        args.debug,
    )
    if args.debug:
        logger.debug("Debug logging enabled via --debug flag")

    # ------------------------------------------------------------------------
    # MULTIPROCESSING CONFIGURATION
    # ------------------------------------------------------------------------
    mp.freeze_support()
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        # Method may already be set in some environments
        pass

    # ------------------------------------------------------------------------
    # QT APPLICATION SETUP
    # ------------------------------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Pro")
    app.setQuitOnLastWindowClosed(True)

    # ------------------------------------------------------------------------
    # MAIN WINDOW CREATION AND DISPLAY
    # ------------------------------------------------------------------------
    MainWindow = getattr(import_module("pyama_pro.main_window"), "MainWindow")
    window = MainWindow()
    window.show()

    # ------------------------------------------------------------------------
    # EVENT LOOP EXECUTION
    # ------------------------------------------------------------------------
    exit_code = app.exec()

    # Clean up
    app.processEvents()
    app.quit()

    sys.exit(exit_code)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

