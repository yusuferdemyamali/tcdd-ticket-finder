from __future__ import annotations

from app.tcdd.models import TrainAvailability
from app.ticket_searches.models import TicketSearch


def filter_eligible_trains(search: TicketSearch, trains: list[TrainAvailability]) -> list[TrainAvailability]:
    """Filter normalized TrainAvailability by MVP invariants and sort ascending.

    MVP eligible only when:
      - departure_date == search.travel_date
      - departure_time inclusive between departure_time_from and departure_time_to
      - economy_available >= 1

    Returns sorted list by departure_time ascending (via departure_at).
    """
    eligible: list[TrainAvailability] = []
    for t in trains:
        if t.departure_date != search.travel_date:
            continue
        # inclusive time window check
        if not (search.departure_time_from <= t.departure_time <= search.departure_time_to):
            continue
        if t.economy_available < 1:
            continue
        eligible.append(t)
    # sort ascending by departure_time; use departure_at for stable sorting including seconds
    eligible.sort(key=lambda x: x.departure_at)
    return eligible
