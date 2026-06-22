"""Persisted settings (QSettings) + defaults.

Wraps QSettings and produces the plain, Qt-free config objects the extraction
and export layers consume (so those layers never read QSettings directly).
"""

from __future__ import annotations

import getpass
import json
from typing import Any

from PySide6.QtCore import QSettings

from .extraction.wire_parser import WireConfig
from .export.wire_export import WireExportOptions, SORT_NUMERICAL
from .model.storage import DEFAULT_IGNORE_PATTERNS

ORG = "PDFMarkup"
APP = "PDFMarkupApp"


def _default_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "user"


DEFAULTS: dict = {
    "your_name": _default_user(),
    # wire field widths
    "wire/sheet_width": 3,
    "wire/rung_width": 2,
    "wire/wire_width": 1,
    "wire/zero_pad": True,
    "wire/regex_override": "",
    "wire/cross_check_sheet": False,
    # export
    "export/labels_per_wire": 2,
    "export/mode": "single",        # "single" | "per_sheet"
    "export/format": "xlsx",         # "xlsx" | "csv"
    "export/sort": SORT_NUMERICAL,
    # comments / todo
    "comments/treat_all_as_todo": False,
    "filter/ignore_patterns": json.dumps(DEFAULT_IGNORE_PATTERNS),
    "filter/show_ignored": False,
    # ocr / ai
    "ocr/enabled": False,
    "ai/enabled": False,
    "ai/region_size": 400,
    "ai/model": "claude-opus-4-8",
}


class AppConfig:
    """Thin typed wrapper over QSettings."""

    def __init__(self):
        self.s = QSettings(ORG, APP)

    # -- generic get/set -----------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        if default is None:
            default = DEFAULTS.get(key)
        val = self.s.value(key, default)
        # QSettings stringifies bools/ints on some platforms - coerce by default
        if isinstance(default, bool):
            if isinstance(val, str):
                return val.lower() in ("1", "true", "yes", "on")
            return bool(val)
        if isinstance(default, int) and not isinstance(default, bool):
            try:
                return int(val)
            except (ValueError, TypeError):
                return default
        return val

    def set(self, key: str, value: Any) -> None:
        self.s.setValue(key, value)

    def sync(self) -> None:
        self.s.sync()

    # -- typed convenience ---------------------------------------------------

    @property
    def your_name(self) -> str:
        return str(self.get("your_name"))

    @property
    def show_ignored(self) -> bool:
        return bool(self.get("filter/show_ignored"))

    @property
    def treat_all_as_todo(self) -> bool:
        return bool(self.get("comments/treat_all_as_todo"))

    def ignore_patterns(self) -> list:
        raw = self.get("filter/ignore_patterns")
        try:
            val = json.loads(raw) if isinstance(raw, str) else list(raw)
            if isinstance(val, list):
                return [str(p) for p in val]
        except Exception:
            pass
        return list(DEFAULT_IGNORE_PATTERNS)

    def set_ignore_patterns(self, patterns: list) -> None:
        self.set("filter/ignore_patterns", json.dumps(list(patterns)))

    # -- derived config objects ---------------------------------------------

    def wire_config(self) -> WireConfig:
        return WireConfig(
            sheet_width=int(self.get("wire/sheet_width")),
            rung_width=int(self.get("wire/rung_width")),
            wire_width=int(self.get("wire/wire_width")),
            zero_pad=bool(self.get("wire/zero_pad")),
            regex_override=str(self.get("wire/regex_override") or ""),
            cross_check_sheet=bool(self.get("wire/cross_check_sheet")),
        )

    def export_options(self) -> WireExportOptions:
        return WireExportOptions(
            fmt=str(self.get("export/format")),
            labels_per_wire=int(self.get("export/labels_per_wire")),
            sort=str(self.get("export/sort")),
        )

    @property
    def ocr_enabled(self) -> bool:
        return bool(self.get("ocr/enabled"))

    @property
    def ai_enabled(self) -> bool:
        return bool(self.get("ai/enabled"))

    @property
    def ai_model(self) -> str:
        return str(self.get("ai/model"))

    @property
    def ai_region_size(self) -> int:
        return int(self.get("ai/region_size"))
