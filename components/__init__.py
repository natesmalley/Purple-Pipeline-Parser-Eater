"""Components package for Purple Pipeline Parser Eater.

Lazy re-exports via PEP 562 ``__getattr__`` so that importing a stdlib-only
submodule (e.g. ``components.s1_models``) does not drag in the full heavy
dependency wave (anthropic, aiohttp, flask, numpy, ...).

See plan Phase -1.A: ``~/.claude/plans/abundant-munching-hanrahan.md``.
"""
from typing import TYPE_CHECKING

_LAZY = {
    "GitHubParserScanner": ".github_scanner",
    "ClaudeParserAnalyzer": ".claude_analyzer",
    "ParserAnalysis": ".claude_analyzer",
    "ClaudeLuaGenerator": ".lua_generator",
    "LuaGenerationResult": ".lua_generator",
    "RAGKnowledgeBase": ".rag_knowledge",
    "ClaudeRAGAssistant": ".rag_assistant",
    "ClaudeGitHubAutomation": ".github_automation",
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
    from .claude_analyzer import (  # noqa: F401
        ClaudeParserAnalyzer,
        ParserAnalysis,
    )
    from .github_automation import ClaudeGitHubAutomation  # noqa: F401
    from .github_scanner import GitHubParserScanner  # noqa: F401
    from .lua_generator import (  # noqa: F401
        ClaudeLuaGenerator,
        LuaGenerationResult,
    )
    from .rag_assistant import ClaudeRAGAssistant  # noqa: F401
    from .rag_knowledge import RAGKnowledgeBase  # noqa: F401
