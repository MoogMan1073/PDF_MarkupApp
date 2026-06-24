"""Settings dialog is organised into tabs (so it never outgrows the screen),
and both the Wire Numbers and Component Labels tabs expose a scanned-page
AI/OCR engine picker."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QTabWidget
    _QT_OK = True
except Exception:  # pragma: no cover
    _QT_OK = False


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestSettingsTabs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self):
        from app.config import AppConfig
        from app.main_window import SettingsDialog
        return SettingsDialog(AppConfig())

    def test_settings_split_into_tabs(self):
        d = self._dialog()
        tw = d.findChild(QTabWidget)
        self.assertIsNotNone(tw, "settings should use a QTabWidget")
        titles = [tw.tabText(i) for i in range(tw.count())]
        self.assertIn("General", titles)
        self.assertIn("Wire numbers", titles)
        self.assertIn("Component labels", titles)
        # several tabs keeps any single page short
        self.assertGreaterEqual(tw.count(), 4)

    def test_wire_method_picker_round_trips(self):
        d = self._dialog()
        original = d.config.get("wire/extract_method")
        try:
            self.assertEqual(
                [d.wire_method.itemText(i) for i in range(d.wire_method.count())],
                ["AI assist", "OCR"])
            d.wire_method.setCurrentIndex(1)   # OCR
            d.apply()
            self.assertEqual(d.config.wire_extract_method, "ocr")
        finally:
            d.config.set("wire/extract_method", original)
            d.config.sync()


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestWirePanelMethodPicker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_wire_panel_has_scanned_method_dropdown(self):
        from app.panels.wire_panel import WirePanel
        wp = WirePanel()
        self.assertEqual(
            [wp.method.itemText(i) for i in range(wp.method.count())],
            ["AI assist", "OCR"])


if __name__ == "__main__":
    unittest.main()
