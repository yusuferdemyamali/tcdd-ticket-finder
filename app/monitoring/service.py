from __future__ import annotations

import asyncio
import datetime
import inspect
import random
from zoneinfo import ZoneInfo

from .config import MonitoringConfig, load_monitoring_config
from .filtering import filter_eligible_trains

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


async def _call_maybe_async(func, *args, **kwargs):
    res = func(*args, **kwargs)
    if inspect.isawaitable(res):
        return await res
    return res


class MonitoringService:
    """Orchestrates polling, filtering, state transitions, and notifications.

    Dependencies:
      - ticket_service: TicketSearchService (domain boundary)
      - tcdd_client: TcddClient with search_trains method returning normalized TrainAvailability
      - notifier: object with notify_found(search, eligible_trains) and notify_expired(search)
                  may be sync or async; if async, will be awaited
      - config: MonitoringConfig
      - now_fn: callable returning datetime (for expiry checks)
      - random_fn: callable (a,b) -> int
      - sleep_fn: callable (seconds) -> awaitable or sync
    """

    def __init__(
        self,
        ticket_service,
        tcdd_client,
        notifier,
        config: MonitoringConfig | None = None,
        now_fn=None,
        random_fn=None,
        sleep_fn=None,
    ) -> None:
        self.ticket_service = ticket_service
        self.tcdd_client = tcdd_client
        self.notifier = notifier
        self.config = config or load_monitoring_config()
        self._now_fn = now_fn
        self._random_fn = random_fn
        self._sleep_fn = sleep_fn

    def _now_dt(self) -> datetime.datetime:
        if self._now_fn is not None:
            dt = self._now_fn()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ISTANBUL_TZ)
            return dt
        return datetime.datetime.now(ISTANBUL_TZ)

    def _random_interval(self) -> int:
        fn = self._random_fn or random.randint
        return fn(self.config.poll_min_seconds, self.config.poll_max_seconds)

    async def _sleep(self, seconds: int) -> None:
        fn = self._sleep_fn
        if fn is None:
            await asyncio.sleep(seconds)
            return
        res = fn(seconds)
        if inspect.isawaitable(res):
            await res

    def _is_expired(self, search, now: datetime.datetime) -> bool:
        # window end = travel_date + departure_time_to in Istanbul, inclusive
        try:
            travel_end_str = f"{search.travel_date} {search.departure_time_to}"
            travel_end_dt = datetime.datetime.strptime(travel_end_str, "%Y-%m-%d %H:%M")
            travel_end_dt = travel_end_dt.replace(tzinfo=ISTANBUL_TZ)
        except Exception:
            # If parsing fails, treat as not expired to avoid false expiration
            return False
        return now > travel_end_dt

    async def run_once(self) -> str:
        """Deterministic one-check entry point.

        Returns outcome string: "no_active", "expired", "no_match", "found", "found_notify_failed"
        Does not sleep. May raise on TCDD error or notification failure.
        Tests can call this without sleeping.
        """
        now = self._now_dt()
        search = self.ticket_service.get_active_search()
        if search is None:
            return "no_active"

        # Expiration check before TCDD call
        if self._is_expired(search, now):
            # Transition to EXPIRED
            self.ticket_service.expire_search(search.id)
            # Send one expiration notification
            # Even if notifier fails, keep EXPIRED (do not revert)
            try:
                await _call_maybe_async(self.notifier.notify_expired, search)
            except Exception:
                # Keep expired state, propagate for visibility? But we want to ensure state is EXPIRED even if notify fails.
                # For spec, notification should be sent once; if fails, state remains EXPIRED.
                # We swallow notification failure here to avoid looping expiration? But we also want to ensure caller sees failure?
                # For this MVP, if expiration notification fails we still keep EXPIRED and surface exception? Decide to swallow.
                pass
            return "expired"

        # Query TCDD – let exceptions propagate (do not treat as empty)
        trains = self.tcdd_client.search_trains(
            search.origin_station_id,
            search.destination_station_id,
            search.travel_date,
        )

        eligible = filter_eligible_trains(search, trains)

        if not eligible:
            return "no_match"

        # Found: ACTIVE -> FOUND before notification
        self.ticket_service.mark_found(search.id)

        # Notify – if fails, leave as FOUND and do NOT mark COMPLETED
        try:
            await _call_maybe_async(self.notifier.notify_found, search, eligible)
        except Exception:
            # Leave FOUND, propagate exception to caller for test visibility
            raise

        # Only after successful notification, mark COMPLETED
        self.ticket_service.mark_completed(search.id)
        return "found"

    # Alias for spec wording: "deterministic one-check monitoring entry point"
    async def check_once(self) -> str:
        return await self.run_once()

    # Synchronous convenience for tests that don't want async
    def run_once_sync(self) -> str:
        """Synchronous wrapper for run_once using asyncio.run or current loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            # If already in loop, create task? For tests without running loop, we can use asyncio.run
            # Fallback: run in new loop via asyncio.run is not allowed inside running loop, so we need to handle.
            # For simplicity, raise, but tests should use async.
            raise RuntimeError("run_once_sync cannot be called from running event loop; use await run_once")
        return asyncio.run(self.run_once())

    async def run_loop(self, iterations: int | None = None) -> None:
        """Thin random-interval polling loop around run_once.

        If iterations is set, loop that many times (for tests).
        Otherwise loop forever until cancelled.
        """
        count = 0
        while True:
            try:
                await self.run_once()
            except Exception:
                # TCDD errors and notify failures should not crash loop
                # For TCDD errors, we keep ACTIVE and will retry after interval
                # For notify failure, search is FOUND and will remain FOUND (retry hardening deferred)
                pass
            count += 1
            if iterations is not None and count >= iterations:
                break
            interval = self._random_interval()
            await self._sleep(interval)

    # Expose filtering helper for external use / tests
    def filter_eligible(self, search, trains):
        return filter_eligible_trains(search, trains)
