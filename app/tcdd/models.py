from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Station:
    """Canonical TCDD station record.

    Only stable identifiers and display names are exposed.
    Raw TCDD JSON fields are not retained.
    """

    id: int
    name: str

    # Optional display helpers – keep minimal but useful
    city_name: str | None = None


@dataclass(frozen=True, slots=True)
class TrainAvailability:
    """Normalized train availability for downstream application code.

    Only stable fields needed by the MVP domain are retained.
    Raw TCDD response shape and non-MVP category details are not exposed.
    """

    train_id: int | str
    train_name: str
    train_number: str
    departure_at: datetime.datetime
    arrival_at: datetime.datetime
    economy_available: int

    @property
    def departure_date(self) -> str:
        return self.departure_at.strftime("%Y-%m-%d")

    @property
    def departure_time(self) -> str:
        return self.departure_at.strftime("%H:%M")

    @property
    def arrival_time(self) -> str:
        return self.arrival_at.strftime("%H:%M")
