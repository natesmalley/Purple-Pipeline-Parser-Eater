"""Utilities package for Purple Pipeline Parser Eater.

Lazy re-exports via PEP 562 ``__getattr__`` so that importing a stdlib-only
submodule (e.g. ``utils.secret_manager``) does not drag in the full heavy
dependency wave.

See plan Phase -1.A: ``~/.claude/plans/abundant-munching-hanrahan.md``.
"""
from typing import TYPE_CHECKING

_LAZY = {
    "ConversionLogger": ".logger",
    "ConversionError": ".error_handler",
    "ParserScanError": ".error_handler",
    "ClaudeAPIError": ".error_handler",
    "ObservoAPIError": ".error_handler",
    "LuaGenerationError": ".error_handler",
    "DeploymentError": ".error_handler",
    "ValidationError": ".error_handler",
    "RateLimiter": ".error_handler",
    "ErrorRecovery": ".error_handler",
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
    return sorted(set(list(globals().keys()) + list(_LAZY.keys())))


__all__ = list(_LAZY.keys())

if TYPE_CHECKING:
    from .error_handler import (  # noqa: F401
        ClaudeAPIError,
        ConversionError,
        DeploymentError,
        ErrorRecovery,
        LuaGenerationError,
        ObservoAPIError,
        ParserScanError,
        RateLimiter,
        ValidationError,
    )
    from .logger import ConversionLogger  # noqa: F401
