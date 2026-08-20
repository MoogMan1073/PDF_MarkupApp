"""Design rule checking inside DSI Redline.

The rules themselves live in PyDRC, a separate pure-Python library with no Qt
and no PyMuPDF: this package is the adapter between the two.  It turns an open
drawing into the model document PyDRC evaluates, runs the rule packs, and hands
back findings for the UI to show.

PyDRC is an optional dependency, handled the same way the AI extraction path
handles the Anthropic SDK: the feature reports itself unavailable rather than
breaking the app when the library is absent.
"""

from __future__ import annotations


def available() -> bool:
    """Whether the rule library is importable."""
    try:
        import pydrc  # noqa: F401
        import pydrc.checks  # noqa: F401
    except Exception:
        return False
    return True


def status() -> tuple:
    """``(ok, message)`` describing why the audit is or is not usable."""
    try:
        import pydrc
        import pydrc.checks  # noqa: F401
    except ImportError:
        return False, ("The design rule library (PyDRC) is not installed. "
                       "Install it to enable design rule checking.")
    except Exception as e:                       # pragma: no cover - defensive
        return False, f"The design rule library failed to load: {e}"
    return True, f"PyDRC {getattr(pydrc, '__version__', '?')}"
