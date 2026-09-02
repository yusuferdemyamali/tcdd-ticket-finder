"""Production TCDD integration – isolated from Telegram, SQLite, scheduler."""

from .client import TcddClient, TRAIN_AVAIL_URL_PRIMARY
from .exceptions import (
    TcddAuthenticationError,
    TcddError,
    TcddInvalidResponseError,
    TcddNetworkError,
    TcddRateLimitError,
    TcddServerError,
    TcddStationAmbiguityError,
    TcddStationError,
    TcddStationNotFoundError,
    TcddTimeoutError,
    TcddTlsError,
    TcddUnexpectedResponseError,
    TcddWafError,
)
from .models import Station, TrainAvailability
from .parser import parse_train_availability
from .stations import STATION_CDN_URL

__all__ = [
    "TcddClient",
    "Station",
    "TrainAvailability",
    "parse_train_availability",
    "STATION_CDN_URL",
    "TRAIN_AVAIL_URL_PRIMARY",
    "TcddError",
    "TcddStationError",
    "TcddStationNotFoundError",
    "TcddStationAmbiguityError",
    "TcddNetworkError",
    "TcddTimeoutError",
    "TcddAuthenticationError",
    "TcddRateLimitError",
    "TcddServerError",
    "TcddInvalidResponseError",
    "TcddUnexpectedResponseError",
    "TcddTlsError",
    "TcddWafError",
]
