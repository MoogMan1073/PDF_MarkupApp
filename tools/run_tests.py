"""Run the test suite with each module in its own process.

Running the whole suite in a single process accumulates Qt GUI resources
(GDI/USER handles, pixmaps) from the many window-creating tests and hard-crashes
a late module on the headless Windows runner -- even though every module passes
on its own.  Per-module isolation keeps resource use bounded, and it names the
module that failed instead of leaving a bare crash in the log.

It also reports *why* tests were skipped, grouped by reason.  A green run that
quietly skipped the design rule checks is not the same as a green run that
checked them, and CI should not let those two look alike.

    python tools/run_tests.py [-v] [--strict] [module ...]

``--strict`` (used by CI) fails the run when tests were skipped because Qt was
missing.  The workflows install Qt, so that is a broken runner, not a choice --
and a run that skipped every GUI test must not report success.
"""

from __future__ import annotations

import collections
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAN_RE = re.compile(r"^Ran (\d+) test", re.M)
# Verbose unittest writes: "test_x (tests.y.Z.test_x) ... skipped 'reason'"
SKIP_RE = re.compile(r"\.\.\. skipped ['\"](.*?)['\"]")
# Reasons that mean "the optional rule library was missing", as spelled by the
# skipUnless decorators in tests/.
DRC_REASON = re.compile(r"pydrc", re.I)
# Qt is guaranteed by both workflows; if it is missing the environment is
# broken, and roughly a third of the suite quietly turns into skips.
QT_REASON = re.compile(r"pyside", re.I)


def modules(argv) -> list:
    named = [a for a in argv if not a.startswith("-")]
    if named:
        return named
    found = glob.glob(os.path.join(HERE, "tests", "test_*.py"))
    return sorted("tests." + os.path.basename(p)[:-3] for p in found)


def drc_status() -> tuple:
    """``(available, message)`` for the optional rule library."""
    try:
        sys.path.insert(0, HERE)
        from app import audit
        return audit.status()
    except Exception as e:                       # pragma: no cover - defensive
        return False, f"could not be queried: {e}"


def main(argv) -> int:
    verbose = "-v" in argv
    strict = "--strict" in argv
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    names = modules(argv)

    ok, message = drc_status()
    print(f"Design rule library: {message}")
    print()

    failed, ran = [], 0
    reasons = collections.Counter()
    for mod in names:
        # Always verbose in the subprocess: the skip reasons are only in the
        # verbose stream, and attributing a skip to the wrong cause is worse
        # than not counting it. The output is captured either way.
        proc = subprocess.run([sys.executable, "-m", "unittest", mod, "-v"],
                              cwd=HERE, capture_output=True, text=True)
        out = (proc.stdout or "") + (proc.stderr or "")

        counted = RAN_RE.search(out)
        ran += int(counted.group(1)) if counted else 0
        found = SKIP_RE.findall(out)
        reasons.update(found)

        status = "ok  " if proc.returncode == 0 else "FAIL"
        note = f" ({len(found)} skipped)" if found else ""
        print(f"{status} {mod}{note}", flush=True)
        if proc.returncode != 0 or verbose:
            print(out)
        if proc.returncode != 0:
            failed.append(mod)

    total_skipped = sum(reasons.values())
    print()
    print(f"{ran} tests across {len(names)} modules; {total_skipped} skipped.")
    for reason, n in reasons.most_common():
        print(f"    {n:4d}  {reason}")

    # Loud on purpose. "No failures" must never be read as "everything was
    # checked" -- the same rule the audit itself follows about coverage.
    drc_skipped = sum(n for r, n in reasons.items() if DRC_REASON.search(r))
    qt_skipped = sum(n for r, n in reasons.items() if QT_REASON.search(r))
    gaps = []
    if drc_skipped:
        gaps.append((drc_skipped, "the design rule library is absent",
                     "See CI.md to give the workflow access to it."))
    if qt_skipped:
        gaps.append((qt_skipped, "Qt (PySide6) could not be loaded",
                     "On Linux this usually means the Qt system libraries are "
                     "missing; see the Tests workflow."))
    for count, why, hint in gaps:
        print()
        print("!" * 72)
        print(f"!! {count} tests were SKIPPED because {why}.")
        print("!! That code was NOT exercised by this run.")
        print(f"!! {hint}")
        print("!" * 72)

    if strict and qt_skipped:
        print(f"\n--strict: failing because {qt_skipped} tests were skipped "
              f"for a missing Qt, which CI is supposed to provide.")
        return 1
    if failed:
        print(f"\nFAILED MODULES: {', '.join(failed)}")
        return 1
    print("\nAll test modules passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
