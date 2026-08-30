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

### ...and until 1.5.2 it was a sentence, not a rule

The boundary was stated in five documents and enforced nowhere. `save()`'s own
docstring said *"The original PDF is never overwritten"* directly above the line
that did it: `export_annotated_pdf` forwarded a save dialog's path straight into
`save(marked_path=...)`, and every write in the app took its destination on
trust. Measured, not argued:

| aimed at | result |
|---|---|
| `export_annotated_pdf(the open drawing)` | replaced, **no `.marked.pdf` written at all** |
| ...and every save after that | wrote **two** copies of every mark, for ever |
| `export_annotated_pdf(a neighbouring drawing)` | 3 pages → 1, replaced by the acting document |
| `export_flattened_pdf(a neighbouring drawing)` | same, and **unrecoverable** — baked into page content |
| `extract_pages(src, src, merge=True)` | 4 pages → 1 |
| `split_ranges(src, src, merge=True)` | 5 pages → 2 |
| `combine_pdfs([src, other], src)` | 4 pages → 6 |
| `rotate_pdf(a, an unrelated drawing)` | 4 pages → a 3-page rotated copy of `a` |

**PyMuPDF refuses some of this itself** — `save to original must be
incremental` — and the two things that get past it are worth knowing, because
they are what made a stated boundary a false one:

* **The library's check only sees a save from the document that opened the
  file.** Every page tool builds a *new* `fitz.Document` from the pages it read,
  so the check never fires and the write lands.
* **`save()`'s own atomicity machinery defeats it.** The `out_is_open`
  temp-and-`os.replace` branch exists so an open `.marked.pdf` can be re-saved
  on Windows; aimed at the original it turns a refusal the library would have
  issued into a successful destruction. The safety net was there and the app
  routed around it.

**The doubling is the part a user could not undo.** Once the original carries a
mark, `original_pdf_path` still resolves to it and `is_marked_pdf` says False,
so the `strip_annotations` branch that exists to stop re-saving doubling the
marks is unreachable — and the `.marked.pdf` carries every mark twice from then
on, whatever you do.

**What is enforced now, and where.** One guard, in `app/model/storage.py` beside
the path helpers, called from every write:

1. `refuse_protected(out, doc_path)` — never write **this document's original**.
   Refused even when that file is absent, because writing it would *create* the
   pristine base every later open reads from.
2. the same rule for **another drawing that holds marks here** — a reviewer works
   on a folder, and a save dialog opened in it puts every drawing one click away.
3. `refuse_overwriting_input(out, *inputs)` — a page tool may not eat its own
   input.

`app/tools/pdf_ops.py` routes all eleven of its writers through one `_guard_out`,
and `tests/test_never_overwrite_original.py` walks the module's AST and fails on
a writer that has none — a gate over the artifact rather than over a list of the
functions that existed when it was written.

**Two things the rules deliberately do NOT do**, because measuring said so:

* **Rule 2 asks whether the sidecar holds ANNOTATIONS, not whether it exists.**
  Opening a PDF creates its `.markup.db` unconditionally, so "a sidecar is
  present" means "seen here" and nothing more. The existence test refused an
  ordinary second export and broke two of this repo's own regression tests,
  which fork onto a name whose sidecar was pre-seeded with wires and waivers.
* **A PDF this app has never opened is not protected.** It is indistinguishable
  from a stale export, and the save dialog has already asked about replacing it.
  Redline protects what it can identify; saying which is the point.

### Two dead gates were written before the live ones

Both passed on the exact defect they were written for, and both were found by
injecting it rather than by reading them:

* the AST sweep counted only `.save(`, so `pdf_to_docx` — which writes through
  pdf2docx's `convert()` — was **not counted as a writer at all**, and removing
  its guard changed nothing. It now takes a set of write calls and asserts the
  scan is still *finding* at least ten writers, so a rename cannot make it match
  nothing and go green.
* the `same_path` test used a **symlink**, which `os.path.realpath` resolves —
  so the fallback answered it alone and deleting the `os.path.samefile` branch
  kept the test green. A **hard link** has two real names `realpath` does not
  collapse, and the fixture asserts that before it asserts anything else.

And the falsification loop itself was dead first: `2>/dev/null` on a
`python -m unittest` run discards the results, so eight injections in a row
reported *nothing fired*. **If a falsification says the gate did not fire,
suspect the reading before the gate.**

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

## An open PyMuPDF handle is a Windows file lock, and Linux cannot see it

A `fitz.Document` left open holds the file. On Windows that makes `os.remove`
raise `WinError 32` and makes a save onto that path raise *"cannot remove file
… Permission denied"* from inside PyMuPDF; on Linux both succeed. So a test
that leaks a handle is **green locally and red only on `windows-latest`** —
which is what `tests/test_never_overwrite_original.py` did on its first run:
two errors, both in the fixture, none in the code under test, on a leg the
local suite cannot reach.

The app itself is careful about this and always has been — `open_pdf` closes
the previous document before it swaps (`main_window.py:1364-1368`) and so does
`closeEvent`. It is **test** code that forgets.

**The fix is to assert the CAUSE, which is checkable on Linux.** Waiting for
the effect means waiting for CI. `assertNoOpenHandle(path)` walks the fixture's
own documents and fails when one is still open on that path, so deleting a
`close()` fails immediately on any platform. Five leaks were reintroduced in
turn and every one goes red here.

Two ways the falsification of that was wrong before it was right, both worth
more than the fix:

* **An injection that also deletes the assertion proves nothing.** Three of the
  first four removed the `close()` *and* the check beside it, reported "0
  failing", and read exactly like four dead gates.
* **An assertion pointed at the wrong file reads like a live one.** One checked
  the `.marked.pdf` where the released handle was on the original, so it was
  vacuously true and the leak beside it fired nothing.

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

The version is declared in **three** places — `app/__init__.py`,
`packaging/installer.iss` and a `CHANGELOG.md` section — and
`tests/test_requirements.py::TestVersionIsStatedOnce` fails when they disagree.
That gate is right and this line used to say "declared once", which is the
claim it exists to disprove: it caught the 1.5.2 bump within a minute of it
being made in one file.

## A test that hides itself runs a smaller number, and nothing reports that

Two ways a module here ran fewer tests than it holds. Neither is a failure —
both are a *smaller number*, and no runner calls that anything.

- **A misplaced `if __name__ == "__main__"` block hides everything below it
  from a direct run.** `python3 tests/test_requirements.py` ran **3** tests
  where `python3 -m unittest tests.test_requirements` ran **5**: the guard sat
  at line 44 and `TestVersionIsStatedOnce` began at 48, so the two that vanished
  were **the version-drift gates** — the ones that exist because the installer
  once sat at 1.4.0 while the app moved on.

  Four modules carried the guard mid-file. In three it was harmless *only*
  because they import `app` at module scope and cannot be run as scripts at all
  — luck rather than design, and the kind that expires the first time somebody
  moves an import.

- **A Qt-dependent class without the `skipUnless` its siblings carry errors
  instead of skipping.** `TestRolledUpFindingOnScreen` had none, so a machine
  without Qt got `FAILED (errors=1, skipped=31)` where it should get a clean
  skip. Loud, which is the safe direction — and loud about the wrong thing,
  which makes a legitimately-skipping run look broken.

`tests/test_suite_is_discoverable.py` sweeps **the artifact** for both, never a
list of the modules that had the problem when it was written — a gate scoped to
today's offenders covers what was there when the list was made.

### ...and its first draft cried wolf, which is the half worth keeping

The Qt sweep flagged `test_v12_order.py::TestDrawNewOnce`, a working class in a
module that skips cleanly (10 of 10). `unittest.skipUnless` sets
`__unittest_skip__` on the class it decorates and **a subclass inherits it** —
measured rather than assumed: a child of a skipped base reports
`OK (skipped=2)` and `Child.__unittest_skip__` is `True`. So `_Base` covers
both classes under it. Ancestry counts now, resolved within the module, which
is where these bases live.

**An audit that flags a working file is one nobody reads twice.** Calibrate
before believing it — and the stated limit is direct use only: a class calling
a module-level helper that touches a guarded name is not caught, and widening
that means resolving calls, which is a different tool.

### The version rule and the version gate had been contradicting each other

`CONTRIBUTING.md` listed *"a version number anywhere but `app/__init__.py`"*
among the things that fail review, three feet from
`TestVersionIsStatedOnce`, which exists **because there are three** and fails
when they disagree. **A rule and a gate that contradict each other teach people
to trust neither**, and here it was the rule that was wrong. `CLAUDE.md` was
corrected at the 1.5.2 bump and `CONTRIBUTING.md` was not — the same
fix-where-it-was-noticed pattern, one file over.

## "Python 3.11+" was a claim to contributors, and only 3.11 ran

`CONTRIBUTING.md` and `README.md` both say it. The CI matrix varied only the
operating system and pinned `python-version: "3.11"` on both runners, so **3.12
and 3.13 — increasingly the default on a fresh machine — were advertised and
never checked.**

The frozen Windows build pins its own interpreter, so a shipped installer is
unaffected. What this is about is **running from source**, which the README
documents as a first-class way to use the app, against a suite that heavily
exercises PySide6 and PyMuPDF. `build-windows.yml` therefore stays pinned, and
**the reason is written into the file** — an asymmetry with no stated reason
reads as the oversight the test matrix just corrected, and somebody eventually
"fixes" it.

**And both workflows pinned Node-20 action majors.** Every run ended with
*"Node.js 20 is deprecated. The following actions … are being forced to run on
Node.js 24."* The forcing is GitHub's temporary accommodation; when it ends, a
workflow pinned to those majors stops working — and here that is the Windows
build, **the only path that produces the installer**. Bumped to `checkout@v5`,
`setup-python@v6`, `upload-artifact@v5`.

`tests/test_requirements.py::TestTheInterpreterClaimIsExercised` reads the
minimum out of the documents and asserts the matrix covers it *and* names more
than one version, asserts the frozen build stays pinned *with* its reason, and
sweeps both workflows for a stale action major. Comments are stripped first —
the comment explaining this defect necessarily names the versions the check is
hunting, which is the dead gate this repo already paid for once with
`--require-drc`.

**What is NOT verified here**: no interpreter in this container has PySide6, so
3.12 and 3.13 could not be exercised locally. CI is the verification, and
`fail-fast: false` was already set, so a failure on the new legs cannot mask the
3.11 result. Say which of the two you did.
