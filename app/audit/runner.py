"""Running the design rule check.

Written to run on a worker thread, which shapes the whole interface: it opens
its own PyMuPDF handle, takes the document's sheet metadata as plain
dictionaries, and never touches the sidecar.  The sidecar's sqlite connection
belongs to the thread that created it, and the open ``Document`` belongs to the
UI.  Results come back as plain data for the main thread to persist.

Qt-free, so it is testable without a QApplication.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from .adapter import AdapterOptions, build_model
from .findings import (AuditRun, Coverage, Finding, apply_waivers, sort_findings)

DEFAULT_PACK = "drc-base"


class AuditUnavailable(RuntimeError):
    """The rule library is not installed."""


@dataclass
class AuditResult:
    findings: list = field(default_factory=list)
    run: AuditRun = field(default_factory=AuditRun)
    cancelled: bool = False

    @property
    def open_findings(self) -> list:
        return [f for f in self.findings if not f.waived]


def user_pack_dirs() -> list:
    """Directories to search for rule packs besides the built-in ones.

    A packaged installation lives under Program Files, which is not writable,
    so user-authored packs cannot sit beside the built-ins. ``PYDRC_PACK_PATH``
    is how the library is pointed at somewhere they can.
    """
    raw = os.environ.get("PYDRC_PACK_PATH", "")
    return [p for p in raw.split(os.pathsep) if p and os.path.isdir(p)]


def available_rules(pack_ids=(), extra_dirs=None) -> list:
    """``(rule_id, title, severity, pack)`` for every rule that could run.

    Used by Settings to list rules without running anything.
    """
    from pydrc.packs import loader
    out = []
    for pack_id in (pack_ids or (DEFAULT_PACK,)):
        try:
            pack = loader.load_by_id(pack_id, extra=extra_dirs or user_pack_dirs())
        except Exception:
            continue
        for rule in pack.rules:
            out.append((rule.id, rule.title, rule.severity, pack.ref))
    return out


def run_audit(pdf_path: str, sheet_labels: dict, sheet_sources: dict,
              sheet_roles: dict, *,
              options: Optional[AdapterOptions] = None,
              pack_ids=(), extra_pack_dirs=None,
              disabled_rules=(), severity_overrides=None,
              waivers: Optional[dict] = None,
              project: Optional[dict] = None,
              progress: Optional[Callable] = None,
              cancel: Optional[Callable] = None) -> AuditResult:
    """Audit a drawing and return findings plus what could not be checked.

    Opens its own document handle: safe to call from a worker thread, and it
    never mutates anything the caller owns.
    """
    try:
        import fitz
        import pydrc.checks                     # noqa: F401  (registers checks)
        from pydrc.engine.evaluator import run as run_rules
        from pydrc.packs import loader
    except ImportError as e:
        raise AuditUnavailable(
            "The design rule library (PyDRC) is not installed.") from e

    dirs = list(extra_pack_dirs or user_pack_dirs())
    packs = []
    for pack_id in (pack_ids or (DEFAULT_PACK,)):
        packs.append(loader.load_by_id(pack_id, extra=dirs))

    doc = fitz.open(pdf_path)
    try:
        built = build_model(doc, sheet_labels, sheet_sources, sheet_roles,
                            options or AdapterOptions(), project,
                            progress=progress, cancel=cancel)
        if built is None:
            return AuditResult(cancelled=True)

        result = run_rules(built.model, packs,
                           disabled=set(disabled_rules or ()),
                           severity_overrides=dict(severity_overrides or {}))
    finally:
        doc.close()

    if cancel is not None and cancel():
        return AuditResult(cancelled=True)

    payload = result.to_dict()
    findings = [Finding.from_pydrc(raw, built.extents)
                for raw in payload.get("findings", [])]
    findings = sort_findings(apply_waivers(findings, waivers or {}))

    cov_rows = (payload.get("coverage") or {}).get("rules") or []
    summary = (payload.get("coverage") or {}).get("summary") or {}
    run = AuditRun(
        packs=[p.ref for p in packs],
        eligible=int(summary.get("eligible", 0)),
        checked=int(summary.get("checked", 0)),
        skipped=int(summary.get("skipped", 0)),
        coverage=[Coverage.from_dict(c) for c in cov_rows],
        errors=list((payload.get("run") or {}).get("errors") or []),
    )
    return AuditResult(findings=findings, run=run)
