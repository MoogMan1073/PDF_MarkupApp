"""Findings and waivers as this application stores and shows them.

Deliberately its own types rather than the rule library's.  A sidecar written by
a colleague who has the rule library installed must still open for someone who
does not: findings are data, and reading data should not require the engine that
produced it.  These types are also what the sidecar round-trips, so they own
their own JSON.

Qt-free, so the storage layer can use them without dragging the UI in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# Mirrors the rule library's vocabulary.
DEFINITE = "definite"
POTENTIAL = "potential"
INFO = "info"
SEVERITIES = (DEFINITE, POTENTIAL, INFO)

SEVERITY_LABELS = {
    DEFINITE: "Definite violation",
    POTENTIAL: "Potential issue",
    INFO: "Informational",
}

STATUS_OPEN = "open"
STATUS_WAIVED = "waived"

_ORDER = {DEFINITE: 0, POTENTIAL: 1, INFO: 2}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Finding:
    """One thing the audit wants a person to confirm.

    ``key`` is the rule library's fingerprint: stable across re-runs and free of
    coordinates, so a waiver survives a re-extract and a redraw that nudges the
    tag it is about. Findings are rewritten wholesale on every run; waivers are
    keyed on this and are not.
    """

    key: str = ""
    rule_id: str = ""
    severity: str = POTENTIAL
    status: str = STATUS_OPEN
    message: str = ""
    clause: str = ""
    subject_kind: str = ""
    subject_id: str = ""
    sheet: str = ""
    page: int = 0
    # Printed box of the text this finding is about, in the page's displayed
    # space. Zero size when the subject has no single place on the drawing.
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    evidence: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    pack: str = ""
    pack_version: str = ""

    @property
    def waived(self) -> bool:
        return self.status == STATUS_WAIVED

    @property
    def has_location(self) -> bool:
        return bool(self.x or self.y)

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS.get(self.severity, self.severity)

    @property
    def sort_key(self):
        return (_ORDER.get(self.severity, 9), self.sheet, self.rule_id,
                self.subject_id)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "rule_id": self.rule_id, "severity": self.severity,
            "status": self.status, "message": self.message, "clause": self.clause,
            "subject_kind": self.subject_kind, "subject_id": self.subject_id,
            "sheet": self.sheet, "page": self.page,
            "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "evidence": self.evidence, "provenance": self.provenance,
            "pack": self.pack, "pack_version": self.pack_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        d = dict(d or {})
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def from_pydrc(cls, raw: dict, extents: Optional[dict] = None) -> "Finding":
        """Convert one finding from the rule library's JSON."""
        raw = raw or {}
        loc = raw.get("location") or {}
        subject = raw.get("subject") or {}
        cites = raw.get("cites") or {}
        pack = raw.get("pack") or {}
        page = loc.get("page_index")
        subject_id = str(subject.get("id", ""))

        x = float(loc.get("x") or 0.0)
        y = float(loc.get("y") or 0.0)
        w = h = 0.0
        if extents and page is not None:
            box = extents.get((int(page), subject_id))
            if box:
                x, y, w, h = box

        clause = " ".join(str(cites.get(k, "")) for k in
                          ("standard", "edition", "clause")).strip()
        return cls(
            key=str(raw.get("fingerprint", "")),
            rule_id=str(raw.get("rule_id", "")),
            severity=str(raw.get("severity", POTENTIAL)),
            status=str(raw.get("status", STATUS_OPEN)),
            message=str(raw.get("message", "")),
            clause=" ".join(clause.split()),
            subject_kind=str(subject.get("kind", "")),
            subject_id=subject_id,
            sheet=str(loc.get("sheet", "")),
            page=int(page) if page is not None else 0,
            x=x, y=y, w=w, h=h,
            evidence=dict(raw.get("evidence") or {}),
            provenance=dict(raw.get("provenance") or {}),
            pack=str(pack.get("id", "")),
            pack_version=str(pack.get("version", "")),
        )


@dataclass
class Waiver:
    """A human decision that a finding is acceptable here.

    Every real panel has justified exceptions, and a checker without a way to
    record them gets switched off after the second review. Waivers outlive
    findings: an audit re-run replaces the findings table wholesale and must
    never touch this one.
    """

    key: str = ""
    rule_id: str = ""
    reason: str = ""
    author: str = ""
    created: str = field(default_factory=now_iso)
    subject_id: str = ""

    def to_dict(self) -> dict:
        return {"key": self.key, "rule_id": self.rule_id, "reason": self.reason,
                "author": self.author, "created": self.created,
                "subject_id": self.subject_id}

    @classmethod
    def from_dict(cls, d: dict) -> "Waiver":
        d = dict(d or {})
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Coverage:
    """What a rule could not look at, and why.

    Reported beside findings, never folded into them: "no findings" and "could
    not check" must not be the same answer.
    """

    rule_id: str = ""
    eligible: int = 0
    checked: int = 0
    skipped: int = 0
    reasons: dict = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return self.skipped == 0

    def to_dict(self) -> dict:
        return {"rule_id": self.rule_id, "eligible": self.eligible,
                "checked": self.checked, "skipped": self.skipped,
                "reasons": self.reasons}

    @classmethod
    def from_dict(cls, d: dict) -> "Coverage":
        d = dict(d or {})
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class AuditRun:
    """Summary of one audit, stored in the sidecar's meta table."""

    ran_at: str = field(default_factory=now_iso)
    packs: list = field(default_factory=list)
    eligible: int = 0
    checked: int = 0
    skipped: int = 0
    coverage: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.skipped == 0

    def summary_line(self) -> str:
        """The one sentence the panel header shows.

        Says what was *not* checked first when anything was missed, because
        that is the part a reader is most likely to assume away.
        """
        if not self.eligible:
            return "Nothing to check."
        if self.complete:
            return f"{self.checked} of {self.eligible} checked."
        top = sorted(self._reason_totals().items(), key=lambda kv: -kv[1])
        why = "; ".join(f"{n} {r}" for r, n in top[:2])
        tail = f" ({why})" if why else ""
        return (f"{self.checked} of {self.eligible} checked — "
                f"{self.skipped} not checked{tail}.")

    def _reason_totals(self) -> dict:
        totals: dict = {}
        for cov in self.coverage:
            for reason, n in (cov.reasons or {}).items():
                totals[reason] = totals.get(reason, 0) + int(n)
        return totals

    def to_json(self) -> str:
        return json.dumps({
            "ran_at": self.ran_at, "packs": list(self.packs),
            "eligible": self.eligible, "checked": self.checked,
            "skipped": self.skipped, "errors": list(self.errors),
            "coverage": [c.to_dict() for c in self.coverage],
        })

    @classmethod
    def from_json(cls, raw: Optional[str]) -> Optional["AuditRun"]:
        if not raw:
            return None
        try:
            d = json.loads(raw)
        except Exception:
            return None
        return cls(
            ran_at=str(d.get("ran_at", "")),
            packs=list(d.get("packs") or []),
            eligible=int(d.get("eligible", 0)),
            checked=int(d.get("checked", 0)),
            skipped=int(d.get("skipped", 0)),
            errors=list(d.get("errors") or []),
            coverage=[Coverage.from_dict(c) for c in (d.get("coverage") or [])],
        )


def sort_findings(findings) -> list:
    return sorted(findings, key=lambda f: f.sort_key)


def apply_waivers(findings, waivers: dict) -> list:
    """Mark findings the user has already decided about.

    Waived findings are marked, never dropped: a reviewer needs to see that a
    decision was made, not just its consequence.
    """
    for f in findings:
        f.status = STATUS_WAIVED if f.key in waivers else STATUS_OPEN
    return findings
