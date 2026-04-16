"""
Web UI module for Purple Pipeline Parser Eater.

Provides a web interface for user feedback and conversion management.
This module is refactored from web_feedback_ui.py for better maintainability.
"""
from typing import TYPE_CHECKING

_LAZY = {
    "WebFeedbackServer": ".server",
}


def __getattr__(name):
    if name in _LAZY:
        import importlib
        module = importlib.import_module(_LAZY[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + list(_LAZY.keys()))


__all__ = list(_LAZY.keys())


if TYPE_CHECKING:
    from .server import WebFeedbackServer  # noqa: F401
