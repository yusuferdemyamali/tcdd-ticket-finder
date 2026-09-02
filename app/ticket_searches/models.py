from __future__ import annotations

import enum
from dataclasses import dataclass


class TicketSearchStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FOUND = "FOUND"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass
class TicketSearch:
    id: int | None
    origin_station_id: int
    origin_station_name: str
    destination_station_id: int
    destination_station_name: str
    travel_date: str  # YYYY-MM-DD
    departure_time_from: str  # HH:MM
    departure_time_to: str  # HH:MM
    status: TicketSearchStatus
    last_checked_at: str | None = None
    last_successful_check_at: str | None = None
    next_check_at: str | None = None
    tcdd_outage_notified: bool = False
    last_tcdd_error_at: str | None = None
    found_at: str | None = None
    completed_at: str | None = None
    cancelled_at: str | None = None
    expired_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def is_departure_in_window(self, departure_time: str) -> bool:
        """Inclusive window check: departure_time_from <= departure_time <= departure_time_to."""
        # HH:MM lexicographic works when zero-padded; also normalize
        return self.departure_time_from <= departure_time <= self.departure_time_to
