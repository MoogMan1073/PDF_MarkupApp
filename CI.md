# Continuous integration

Two workflows, both under `.github/workflows/`.

| Workflow | Runs on | Does |
|---|---|---|
| **Tests** (`tests.yml`) | every push, every pull request | the suite, on Ubuntu and Windows |
| **Build Windows** (`build-windows.yml`) | manual dispatch, `v*` tags | the suite, then the portable app, the installer, and the release |

## Running the suite

```
python tools/run_tests.py          # everything
python tools/run_tests.py -v       # everything, verbose
python tools/run_tests.py tests.test_audit
```

On Linux the runner needs Qt's system libraries, which a bare Ubuntu box does
not have — without them `import PySide6.QtGui` fails with
`libEGL.so.1: cannot open shared object file` and about a third of the suite
turns into skips. The Tests workflow installs them; locally, the short list is
`libegl1 libgl1 libglib2.0-0 libdbus-1-3 libxkbcommon-x11-0 libxcb-cursor0`
plus the other `libxcb-*` packages named in the workflow.

Each test module runs in **its own process**. This is not fussiness: running
the whole suite in one process accumulates Qt GUI resources from the many
window-creating tests and hard-crashes a late module on the headless Windows
runner, even though every module passes on its own. Per-module isolation keeps
resource use bounded and names the module that failed instead of leaving a bare
crash in the log.

Qt also needs a display. The runner sets `QT_QPA_PLATFORM=offscreen` itself, so
there is nothing to remember locally.

## The design rule library is optional, and CI says so

Design rule checking lives in [PyDRC](https://github.com/MoogMan1073/PyDRC), a
separate library. It is **not** in `requirements.txt`, because that repository
is private and a plain `pip install -r requirements.txt` would fail for anyone
without credentials — including every CI runner. It lives in
`requirements-drc.txt` instead:

```
pip install -r requirements.txt        # the app
pip install -r requirements-drc.txt    # ...and design rule checking
```

Without it the app still runs and the Audit tab reports the library as
unavailable, which is the same graceful path the AI extraction takes when the
Anthropic SDK is absent.

In CI that creates a trap worth naming: the audit tests are written to **skip**
when the library is missing, so a run without it goes green having never
exercised any of the design rule code. The runner therefore prints the library's
status at the top, groups every skip by its stated reason, and ends with a loud
banner naming how many tests were skipped for that reason. A green tick that
checked nothing must not look like a green tick that checked everything — the
same rule the audit itself follows about coverage.

Qt gets the same treatment, with one difference: the workflows install it, so a
Qt skip means a broken runner rather than a choice. `--strict`, which both
workflows pass, turns those skips into a failed run.

### Giving CI access to it

Both workflows install the library when a `PYDRC_TOKEN` secret exists, and skip
it (loudly) when it does not. To set it up:

1. Create a fine-grained personal access token with **Contents: read-only** on
   `MoogMan1073/PyDRC`.
2. In `MoogMan1073/PDF_MarkupApp`, go to **Settings ▸ Secrets and variables ▸
   Actions ▸ New repository secret**.
3. Name it `PYDRC_TOKEN` and paste the token.

Making PyDRC public would work equally well and needs no secret; the split
between the two requirements files is still worth keeping either way, so the
app's own dependencies never depend on a sibling project being reachable.

Note that secrets are not exposed to pull requests from forks, so a fork's PR
will always run in the skip-and-say-so mode.

## Releases

Push a `v*` tag, or run **Build Windows** manually. On a tag it also publishes a
GitHub Release with the installer and the portable zip attached. A release built
without `PYDRC_TOKEN` ships without design rule checking; the workflow logs a
warning saying so rather than producing a quietly reduced build.
