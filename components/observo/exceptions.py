"""Custom exceptions for Observo API client."""


class ObservoAPIError(Exception):
    """Base exception for Observo API errors."""
    pass


class ObservoConnectionError(ObservoAPIError):
    """Connection error to Observo API."""
    pass


class ObservoAuthenticationError(ObservoAPIError):
    """Authentication error with Observo API."""
    pass


class ObservoValidationError(ObservoAPIError):
    """Validation error for API requests."""
    pass
