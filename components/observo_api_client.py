"""
Observo.ai API Client - Backward Compatibility Wrapper

DEPRECATED: This file now imports from components.observo module.
For new code, import directly from components.observo:
    from components.observo import ObservoAPI

This wrapper maintains backward compatibility with existing code.
"""

from .observo import (
    ObservoAPI,
    ObservoAPIError,
    ObservoConnectionError,
    ObservoAuthenticationError,
    ObservoValidationError
)

__all__ = [
    'ObservoAPI',
    'ObservoAPIError',
    'ObservoConnectionError',
    'ObservoAuthenticationError',
    'ObservoValidationError'
]
