from __future__ import annotations

import inspect
from typing import Protocol

from app.ticket_searches.models import TicketSearch
from app.tcdd.models import TrainAvailability
from app.telegram.formatting import (
    build_found_keyboard,
    format_expired_message,
    format_found_tickets_message,
    format_tcdd_auth_outage_message,
    format_tcdd_outage_message,
    format_tcdd_recovery_message,
)


class NotifierProtocol(Protocol):
    """Protocol for monitoring notifier.

    Implementations may be sync or async. Tests can use fake that records calls.
    """

    async def notify_found(self, search: TicketSearch, trains: list[TrainAvailability]) -> None: ...

    async def notify_expired(self, search: TicketSearch) -> None: ...

    async def notify_outage(self, search: TicketSearch) -> None: ...

    async def notify_auth_outage(self, search: TicketSearch) -> None: ...

    async def notify_recovery(self, search: TicketSearch) -> None: ...

    async def notify_found_retry(self, search: TicketSearch, trains: list[TrainAvailability]) -> None: ...


class TelegramNotifier:
    """Production Telegram notifier using python-telegram-bot Bot."""

    def __init__(self, bot, chat_id: int) -> None:
        self._bot = bot
        self._chat_id = chat_id

    async def notify_found(self, search: TicketSearch, trains: list[TrainAvailability]) -> None:
        text = format_found_tickets_message(search, trains)
        keyboard = build_found_keyboard(search.id)  # type: ignore[arg-type]
        await self._bot.send_message(chat_id=self._chat_id, text=text, reply_markup=keyboard)

    async def notify_expired(self, search: TicketSearch) -> None:
        text = format_expired_message(search)
        await self._bot.send_message(chat_id=self._chat_id, text=text)

    async def notify_outage(self, search: TicketSearch) -> None:
        text = format_tcdd_outage_message(search)
        await self._bot.send_message(chat_id=self._chat_id, text=text)

    async def notify_auth_outage(self, search: TicketSearch) -> None:
        text = format_tcdd_auth_outage_message(search)
        await self._bot.send_message(chat_id=self._chat_id, text=text)

    async def notify_recovery(self, search: TicketSearch) -> None:
        text = format_tcdd_recovery_message(search)
        await self._bot.send_message(chat_id=self._chat_id, text=text)

    async def notify_found_retry(self, search: TicketSearch, trains: list[TrainAvailability]) -> None:
        # Retry uses same formatting as found but emphasizes persisted retry
        text = format_found_tickets_message(search, trains)
        keyboard = build_found_keyboard(search.id)  # type: ignore[arg-type]
        await self._bot.send_message(chat_id=self._chat_id, text=text, reply_markup=keyboard)

    # synchronous aliases for convenience if monitoring loop is sync
    def notify_found_sync(self, search: TicketSearch, trains: list[TrainAvailability]):  # pragma: no cover
        import asyncio

        return asyncio.run(self.notify_found(search, trains))

    def notify_expired_sync(self, search: TicketSearch):  # pragma: no cover
        import asyncio

        return asyncio.run(self.notify_expired(search))


async def _call_maybe_async(func, *args, **kwargs):
    """Helper to call notifier method that may be sync or async."""
    res = func(*args, **kwargs)
    if inspect.isawaitable(res):
        return await res
    return res
