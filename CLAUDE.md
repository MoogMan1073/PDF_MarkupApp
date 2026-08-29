# DSI Redline (`PDF_MarkupApp`) — working notes

A desktop reviewer for AutoCAD Electrical drawing sets: continuous-scroll PDF
viewing, markup, a comment/TODO workflow, wire-number extraction and export,
and an optional design-rule audit. PySide6 + PyMuPDF, fully functional offline.

`README.md` is the feature list. `CI.md` is the workflows, the skip rules and
the release ordering, and is authoritative for all three. `docs/` is the user
manual, served in-app by `app/help.py`. This file is the standing rules.

## Run it

```bash
pip install -r requirements.txt        # the app
pip install -r requirements-drc.txt    # ...and design rule checking (private)
python tools/run_tests.py              # 682 tests across 53 modules
python main.py
```

CI's last green run on `main` reports **682 tests across 53 modules; 0
skipped**, on Ubuntu and Windows. A local run without Qt's system libraries
reports far fewer and says so loudly — see below.

## The original file is never overwritten

Storage is deliberately hybrid, and this is the one boundary a change must not
cross:

- marks are written as standard PDF annotations into a **`*.marked.pdf` copy**,
  so another tool can read them and the source drawing set is untouched;
- app-only state — TODO status, tags, the wire cache — lives in a
  **`*.markup.db` SQLite sidecar** beside it.

A file whose name is too long or carries characters that cannot back a sidecar
opens **view-only** rather than half-working: view, search, print and the PDF
tools stay available and markup is turned off until it is renamed. Degrading to
a named, explained state beats saving somewhere the user did not ask for.

## Three optional dependencies, one pattern

`pydrc` (design rules), `ezdxf` (reading AutoCAD Electrical source drawings),
and `anthropic` (AI extraction) are each absent on some real installs. Every
one of them **reports itself unavailable in the place it would have been used**
— the Audit tab, the import dialog, the extraction path — rather than raising.

Only `requirements.txt` is the app. PyDRC lives in `requirements-drc.txt`
because that repository is **private**, and a plain
`pip install -r requirements.txt` would otherwise fail for anyone without
credentials, CI runners included.

## A SKIP IS HOW COVERAGE EVAPORATES UNDER A GREEN TICK

The audit tests skip when PyDRC is missing, so a run without it goes green
having exercised none of the design-rule code. `tools/run_tests.py` therefore
prints the library's status first, **groups every skip by its stated reason**,
and ends with a loud banner per reason naming how many tests it covered.
`--strict` (Qt) and `--require-drc` (the rule library) turn those skips into a
failed run, and both workflows pass them.

Two things that were wrong here and are worth not repeating:

- **`--require-drc` was read through a pipe.** A bash pipeline's exit status is
  the *last* command's, so `run_tests.py … | tail` reported success over a red
  suite. Measure an exit code without a pipe.
- **One banner was built for every gap.** A fix that rewrote the cause on all
  skips made 54 Qt skips read *"the design rule library could not be
  imported"* — a banner that is loud, prominent and about the wrong thing.
  Build each banner from its own gap.

## Each test module runs in its own process

Not fussiness. Running the whole suite in one process accumulates Qt GUI
resources across the many window-creating tests and **hard-crashes a late
module on the headless Windows runner**, while every module passes alone.
Per-module isolation bounds resource use and names the module that failed
instead of leaving a bare crash in the log.

Qt needs a display; the runner sets `QT_QPA_PLATFORM=offscreen` itself.

On Linux it also needs Qt's system libraries, which a bare box does not have.
Without them `import PySide6.QtGui` fails with `libEGL.so.1: cannot open shared
object file` and about a third of the suite turns into skips. `CI.md` carries
the package list.

## A release names the rules it ships

An installer that cannot say which rules it contains is one nobody can
reproduce. `packaging/pydrc-ref.txt` names the PyDRC ref, whatever it names is
**resolved to a commit SHA** before installing, and that SHA lands in the build
log and the release notes — so a branch cannot move underneath a build and two
runs of one tag cannot quietly differ.

Cutting a release is three steps **in this order**:

1. tag PyDRC (`v0.2.0`);
2. set `packaging/pydrc-ref.txt` to that tag here and commit it;
3. tag the app (`v1.5.0`).

Tagging the app before step 2 produces a release whose notes name a moving
branch, which is the one thing the pin exists to prevent.

The version is declared once, in `app/__init__.py`.
