"""QApplication entry point for the PDF Markup + Wire-Number Extractor."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("PDF Markup App")
    app.setOrganizationName("PDFMarkup")

    win = MainWindow()
    win.show()

    # optional: open a PDF passed on the command line
    pdf_args = [a for a in argv[1:] if a.lower().endswith(".pdf")]
    if pdf_args:
        win.load_document(pdf_args[0])

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
