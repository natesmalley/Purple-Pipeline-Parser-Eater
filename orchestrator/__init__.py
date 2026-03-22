"""
Orchestrator module for Purple Pipeline Parser Eater.

Coordinates the complete conversion workflow from scanning to deployment.
Refactored from orchestrator.py for better maintainability and testability.
"""

from .core import ConversionSystemOrchestrator

__all__ = ['ConversionSystemOrchestrator']
