"""QApplication entry point for DSI Redline (PDF Markup + Wire-Number Extractor)."""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication


def _set_windows_app_id():
    """Make Windows group the taskbar entry under our own icon, not python's."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "DSIInnovations.DSIRedline")
    except Exception:
        pass


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    _set_windows_app_id()
    app = QApplication(argv)

    # lightweight imports so the splash can appear before the heavy modules load
    from app import __app_name__, __version__, app_icon
    from app.splash import SplashScreen

    app.setApplicationName(__app_name__)
    app.setOrganizationName("DSI Innovations")
    icon = app_icon()
    app.setWindowIcon(icon)

    splash = SplashScreen(__app_name__, __version__, icon)
    splash.show()
    splash.message("Starting up…", 8)

    # the heavy import chain (PySide widgets, PyMuPDF, panels) lives here
    splash.message("Loading the PDF engine…", 30)
    from app.main_window import MainWindow

    splash.message("Building the workspace…", 55)
    win = MainWindow(on_progress=splash.message)

    splash.message("Finishing up…", 95)
    win.show()

    # optional: open a PDF passed on the command line (keep the splash up for it)
    pdf_args = [a for a in argv[1:] if a.lower().endswith(".pdf")]
    if pdf_args and os.path.exists(pdf_args[0]):
        splash.message(f"Opening {os.path.basename(pdf_args[0])}…", 98)
        win.load_document(pdf_args[0])

    splash.finish(win)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
