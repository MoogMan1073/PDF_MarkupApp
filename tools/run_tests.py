"""Run the test suite with each module in its own process.

Running the whole suite in a single process accumulates Qt GUI resources
(GDI/USER handles, pixmaps) from the many window-creating tests and hard-crashes
a late module on the headless Windows runner -- even though every module passes
on its own.  Per-module isolation keeps resource use bounded, and it names the
module that failed instead of leaving a bare crash in the log.

It also reports whether the optional rule library was present, and how many
tests were skipped because it was not.  A green run that quietly skipped the
design rule checks is not the same as a green run that checked them, and CI
should not let those two look alike.

    python tools/run_tests.py [-v] [module ...]
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAN_RE = re.compile(r"^Ran (\d+) test", re.M)
SKIP_RE = re.compile(r"skipped=(\d+)")


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
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    ok, message = drc_status()
    print(f"Design rule library: {message}")
    print()

    failed, ran, skipped = [], 0, 0
    for mod in modules(argv):
        cmd = [sys.executable, "-m", "unittest", mod] + (["-v"] if verbose else [])
        proc = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
        out = (proc.stdout or "") + (proc.stderr or "")

        counted = RAN_RE.search(out)
        ran += int(counted.group(1)) if counted else 0
        skips = SKIP_RE.search(out)
        skipped += int(skips.group(1)) if skips else 0

        status = "ok  " if proc.returncode == 0 else "FAIL"
        note = f" ({skips.group(0)})" if skips else ""
        print(f"{status} {mod}{note}", flush=True)
        if proc.returncode != 0 or verbose:
            print(out)
        if proc.returncode != 0:
            failed.append(mod)

    print()
    print(f"{ran} tests across {len(modules(argv))} modules; {skipped} skipped.")
    if skipped and not ok:
        # Loud on purpose. "No failures" must never be read as "everything was
        # checked" -- the same rule the audit itself follows about coverage.
        print()
        print("!" * 72)
        print("!! Tests were SKIPPED because the design rule library is absent.")
        print("!! The design rule check code in this repository was NOT exercised.")
        print("!! See CI.md to give the workflow access to it.")
        print("!" * 72)
    if failed:
        print(f"\nFAILED MODULES: {', '.join(failed)}")
        return 1
    print("All test modules passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
