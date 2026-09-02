from __future__ import annotations


class TcddError(Exception):
    """Base for all TCDD provider errors."""


# Station errors
class TcddStationError(TcddError):
    """Base for station lookup failures."""


class TcddStationNotFoundError(TcddStationError):
    """No canonical station matches the requested name."""


class TcddStationAmbiguityError(TcddStationError):
    """Multiple stations match without an exact canonical winner."""

    def __init__(self, message: str, candidates: list | None = None) -> None:
        super().__init__(message)
        self.candidates = candidates or []


# Transport / protocol errors
class TcddNetworkError(TcddError):
    """Network-level failure distinct from valid empty result."""


class TcddTimeoutError(TcddNetworkError):
    """Timeout failure."""


class TcddAuthenticationError(TcddError):
    """Missing or rejected token / 401/403 auth failure."""


class TcddRateLimitError(TcddError):
    """429 rate limited."""


class TcddServerError(TcddError):
    """HTTP 5xx server error."""


class TcddInvalidResponseError(TcddError):
    """Invalid JSON response."""


class TcddUnexpectedResponseError(TcddError):
    """Valid JSON but incompatible response shape / cannot be normalized safely."""


class TcddTlsError(TcddError):
    """TLS negotiation or WAF blocking failure."""

    # Alias for WAF-distinct handling
    pass


class TcddWafError(TcddTlsError):
    """WAF blocking failure (subclass of TLS error for compatibility)."""
