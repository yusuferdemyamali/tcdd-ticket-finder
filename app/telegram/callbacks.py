from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from app.telegram.formatting import format_restart_success, format_stale_callback, format_unauthorized

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


def _is_authorized(update: Update, allowed_user_id: int) -> bool:
    try:
        uid = update.effective_user.id if update.effective_user else None
        return uid == allowed_user_id
    except Exception:
        return False


async def _unauthorized_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = format_unauthorized()
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        try:
            await update.callback_query.message.reply_text(msg)
        except Exception:
            if update.effective_message:
                await update.effective_message.reply_text(msg)
    elif update.message:
        await update.message.reply_text(msg)
    elif update.effective_message:
        await update.effective_message.reply_text(msg)


class RestartCallbackHandler:
    """Global restart callback handler stale-safe.

    - Authorization check
    - Parse search id from callback_data "restart:{id}"
    - Read persisted search by id (not user_data)
    - Require COMPLETED status
    - Require travel window not passed (now <= travel_date + departure_time_to)
    - Calls restart_search on valid
    """

    def __init__(self, ticket_service, allowed_user_id: int, now_fn=None) -> None:
        self.ticket_service = ticket_service
        self.allowed_user_id = allowed_user_id
        self._now_fn = now_fn

    def _now_dt(self) -> datetime.datetime:
        if self._now_fn is not None:
            dt = self._now_fn()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ISTANBUL_TZ)
            return dt
        return datetime.datetime.now(ISTANBUL_TZ)

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _is_authorized(update, self.allowed_user_id):
            await _unauthorized_reply(update, context)
            return

        query = update.callback_query
        if query is None:
            return
        await query.answer()
        data = query.data or ""
        # Expected "restart:{search_id}"
        if not data.startswith("restart:"):
            await query.message.reply_text(format_stale_callback())
            return
        try:
            sid_str = data.split(":", 1)[1]
            search_id = int(sid_str.strip())
        except Exception:
            await query.message.reply_text(format_stale_callback())
            return

        # Read persisted search by id
        try:
            search = self.ticket_service.get_search(search_id)
        except Exception:
            await query.message.reply_text(format_stale_callback())
            return

        # Guard: must be COMPLETED
        from app.ticket_searches.models import TicketSearchStatus

        if search.status != TicketSearchStatus.COMPLETED:
            await query.message.reply_text(format_stale_callback())
            return

        # Guard: travel window not passed (inclusive)
        try:
            travel_end_str = f"{search.travel_date} {search.departure_time_to}"
            travel_end_dt = datetime.datetime.strptime(travel_end_str, "%Y-%m-%d %H:%M")
            travel_end_dt = travel_end_dt.replace(tzinfo=ISTANBUL_TZ)
        except Exception:
            await query.message.reply_text(format_stale_callback())
            return
        now_dt = self._now_dt()
        if now_dt > travel_end_dt:
            await query.message.reply_text(format_stale_callback())
            return

        # All guards passed – attempt restart
        try:
            self.ticket_service.restart_search(search_id)
        except Exception:
            # Includes conflict (ACTIVE exists), validation, etc.
            await query.message.reply_text(format_stale_callback())
            return

        # Success
        await query.message.reply_text(format_restart_success())
        try:
            await query.edit_message_text("✅ İşlem tamamlandı.")
        except Exception:
            pass
