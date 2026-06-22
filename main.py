"""QApplication entry point for DSI Redline (PDF Markup + Wire-Number Extractor)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app import __app_name__, app_icon
from app.main_window import MainWindow


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
    app.setApplicationName(__app_name__)
    app.setOrganizationName("DSI Innovations")
    app.setWindowIcon(app_icon())          # taskbar + window title-bar icon

    win = MainWindow()
    win.show()

    # optional: open a PDF passed on the command line
    pdf_args = [a for a in argv[1:] if a.lower().endswith(".pdf")]
    if pdf_args:
        win.load_document(pdf_args[0])

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
