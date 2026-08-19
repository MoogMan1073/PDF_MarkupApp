"""Exporting an audit report.

Three formats for three audiences: HTML to file with a project record, Markdown
to paste into a review, CSV to sort in a spreadsheet.  All three carry the same
two things that make a finding checkable — the clause it rests on and the
arithmetic or facts behind it — plus the coverage statement, which is not
optional in any of them.

GUI-free, like its siblings in this package.
"""

from __future__ import annotations

import csv
import html as _html
import os

from ..audit.findings import DEFINITE, POTENTIAL, INFO, SEVERITY_LABELS

# Deliberate wording: this is a review, not a determination of compliance.
ADVISORY = ("Advisory review. Findings identify things to confirm against the "
            "governing standard and the authority having jurisdiction. This "
            "report is not a determination of compliance.")

NOT_CHECKED = ("A skipped item is not a passing item. The rules below could not "
               "run on part of the drawing; supply the missing data to check them.")

_ORDER = (DEFINITE, POTENTIAL, INFO)


def _rows(document) -> list:
    from ..audit.findings import sort_findings
    return sort_findings(list(getattr(document, "findings", []) or []))


def _run(document):
    return getattr(document, "audit_run", None)


def export_markdown(document, path: str) -> str:
    findings = _rows(document)
    run = _run(document)
    out = ["# Design rule check", "", f"> {ADVISORY}", ""]
    if run is not None:
        out += [f"**Coverage.** {run.summary_line()}", ""]
        if run.packs:
            out += [f"Rule packs: {', '.join(run.packs)}", ""]

    for severity in _ORDER:
        group = [f for f in findings if f.severity == severity]
        if not group:
            continue
        out += [f"## {SEVERITY_LABELS[severity]} ({len(group)})", ""]
        for f in group:
            where = f"sheet {f.sheet}" if f.sheet else "set-wide"
            mark = " *(waived)*" if f.waived else ""
            out.append(f"- **{f.message}**{mark}")
            out.append(f"  - `{f.rule_id}` · {where} · {f.subject_id}")
            if f.clause:
                out.append(f"  - Cited: {f.clause}")
            if f.evidence:
                out.append("  - Evidence: "
                           + ", ".join(f"{k}={v}" for k, v in f.evidence.items()))
            waiver = document.waiver_for(f.key) if hasattr(document, "waiver_for") else None
            if waiver is not None:
                who = f" — {waiver.author}" if waiver.author else ""
                out.append(f"  - Waived: {waiver.reason}{who}")
        out.append("")

    if not findings:
        out += ["No findings.", "",
                "Read the coverage statement above before treating that as a "
                "clean result.", ""]

    if run is not None and not run.complete:
        out += ["## Not checked", "", NOT_CHECKED, ""]
        for cov in run.coverage:
            if cov.complete:
                continue
            why = ", ".join(f"{n} {r}" for r, n in (cov.reasons or {}).items())
            out.append(f"- `{cov.rule_id}`: {cov.checked} of {cov.eligible} "
                       f"checked, {cov.skipped} skipped ({why})")
        out.append("")

    text = "\n".join(out)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def export_csv(document, path: str) -> str:
    findings = _rows(document)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Severity", "Rule", "Sheet", "Page", "Subject", "Finding",
                    "Cited", "Status", "Evidence"])
        for f in findings:
            w.writerow([
                f.severity_label, f.rule_id, f.sheet,
                f.page + 1 if f.has_location else "",
                f.subject_id, f.message, f.clause,
                "Waived" if f.waived else "Open",
                "; ".join(f"{k}={v}" for k, v in (f.evidence or {}).items()),
            ])
        run = _run(document)
        if run is not None:
            w.writerow([])
            w.writerow(["Coverage", run.summary_line()])
            for cov in run.coverage:
                if cov.complete:
                    continue
                w.writerow(["", f"{cov.rule_id}: {cov.checked} of {cov.eligible} "
                                f"checked, {cov.skipped} skipped"])
    return path


_CSS = """
body{margin:0;padding:2rem 1.25rem;background:#fff;color:#1a1a1a;
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:60rem;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 .25rem}
h2{font-size:1.05rem;margin:2rem 0 .75rem;padding-bottom:.35rem;
border-bottom:1px solid #e2e5ea}
.note{background:#f7f8fa;border-left:3px solid #5b6470;padding:.75rem 1rem;
margin:1rem 0;color:#5b6470;font-size:.9rem}
.f{border:1px solid #e2e5ea;border-radius:6px;padding:.9rem 1rem;margin:.6rem 0}
.f.waived{opacity:.55}.f.waived .msg{text-decoration:line-through}
.tag{display:inline-block;font-size:.72rem;font-weight:600;letter-spacing:.03em;
text-transform:uppercase;padding:.12rem .45rem;border-radius:3px;color:#fff}
.definite{background:#b3261e}.potential{background:#9a6700}.info{background:#0b5cad}
.waivedtag{background:#8a9099}
.rid{font-family:ui-monospace,Menlo,monospace;font-size:.8rem;color:#5b6470;
margin-left:.5rem}
.msg{margin:.5rem 0 .35rem}.sub{color:#5b6470;font-size:.85rem}
.ev{font-family:ui-monospace,Menlo,monospace;font-size:.78rem;color:#5b6470;
margin-top:.4rem;word-break:break-word}
table{border-collapse:collapse;width:100%;font-size:.875rem}
th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #e2e5ea}
th{color:#5b6470}.gap{color:#b3261e;font-weight:600}
.scroll{overflow-x:auto}
"""


def export_html(document, path: str, title: str = "") -> str:
    findings = _rows(document)
    run = _run(document)
    esc = lambda v: _html.escape(str(v), quote=True)          # noqa: E731
    name = title or os.path.basename(getattr(document, "path", "") or "Drawing")

    out = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>Design rule check — {esc(name)}</title>",
           f"<style>{_CSS}</style></head><body><div class='wrap'>",
           f"<h1>Design rule check</h1><p class='sub'>{esc(name)}</p>",
           f"<div class='note'><strong>Advisory review.</strong> {esc(ADVISORY[18:])}</div>"]

    if run is not None:
        out.append(f"<p><strong>Coverage.</strong> {esc(run.summary_line())}</p>")

    shown = False
    for severity in _ORDER:
        group = [f for f in findings if f.severity == severity]
        if not group:
            continue
        shown = True
        out.append(f"<h2>{esc(SEVERITY_LABELS[severity])} ({len(group)})</h2>")
        for f in group:
            cls = " waived" if f.waived else ""
            out.append(f"<div class='f{cls}'>")
            out.append(f"<span class='tag {severity}'>"
                       f"{esc(SEVERITY_LABELS[severity])}</span>")
            if f.waived:
                out.append("<span class='tag waivedtag'>waived</span>")
            out.append(f"<span class='rid'>{esc(f.rule_id)}</span>")
            out.append(f"<div class='msg'>{esc(f.message)}</div>")
            where = f"sheet {f.sheet}" if f.sheet else "set-wide"
            sub = f"{esc(where)} &nbsp;·&nbsp; {esc(f.subject_id)}"
            if f.clause:
                sub += f" &nbsp;·&nbsp; cited: {esc(f.clause)}"
            out.append(f"<div class='sub'>{sub}</div>")
            if f.evidence:
                out.append("<div class='ev'>" + "  ·  ".join(
                    f"{esc(k)}={esc(v)}" for k, v in f.evidence.items()) + "</div>")
            out.append("</div>")

    if not shown:
        out.append("<h2>No findings</h2><p>Read the coverage statement above "
                   "before treating that as a clean result.</p>")

    if run is not None:
        out.append("<h2>Coverage</h2>")
        if not run.complete:
            out.append(f"<div class='note'>{esc(NOT_CHECKED)}</div>")
        out.append("<div class='scroll'><table><thead><tr><th>Rule</th>"
                   "<th>Eligible</th><th>Checked</th><th>Skipped</th><th>Why</th>"
                   "</tr></thead><tbody>")
        for cov in run.coverage:
            why = ", ".join(f"{n} {r}" for r, n in (cov.reasons or {}).items())
            cls = " class='gap'" if cov.skipped else ""
            out.append(f"<tr><td>{esc(cov.rule_id)}</td><td>{cov.eligible}</td>"
                       f"<td>{cov.checked}</td><td{cls}>{cov.skipped}</td>"
                       f"<td>{esc(why)}</td></tr>")
        out.append("</tbody></table></div>")

    out.append("</div></body></html>")
    text = "\n".join(out)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def export_report(document, path: str) -> str:
    """Export in the format implied by ``path``'s extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".markdown"):
        return export_markdown(document, path)
    if ext == ".csv":
        return export_csv(document, path)
    return export_html(document, path)
