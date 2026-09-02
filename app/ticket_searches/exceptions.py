from __future__ import annotations


class TicketSearchError(Exception):
    """Base for ticket-search domain errors."""


class TicketSearchValidationError(TicketSearchError):
    pass


class TicketSearchConflictError(TicketSearchError):
    pass


class TicketSearchNotFoundError(TicketSearchError):
    pass


class TicketSearchTransitionError(TicketSearchError):
    pass
