from __future__ import annotations

import datetime
import secrets
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.ticket_searches.exceptions import TicketSearchConflictError, TicketSearchValidationError
from app.ticket_searches.models import TicketSearch

from .formatting import (
    format_active_exists_message,
    format_cancel_success,
    format_confirmation_message,
    format_durum_message,
    format_no_active_for_cancel,
    format_operation_cancelled,
    format_search_started,
    format_replacement_started,
    format_stale_callback,
    format_start_message,
    format_unauthorized,
    format_wizard_cancelled_preserved,
)
from .validators import ISTANBUL_TZ, validate_date_strict, validate_time_strict, validate_time_window

# State constants for ConversationHandler
STATE_ORIGIN = 0
STATE_DESTINATION = 1
STATE_DATE = 2
STATE_FROM_TIME = 3
STATE_TO_TIME = 4
STATE_CONFIRM = 5
STATE_AWAITING_REPLACE = 6


def _generate_token() -> str:
    return secrets.token_hex(4)


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


def _get_station_provider(search_context: Any):
    # helper to allow injection; search_context is not used directly
    # station_provider is captured via closure in factory
    return None


class TelegramHandlers:
    """Encapsulates all Telegram handlers with injected dependencies.

    ticket_service: TicketSearchService
    station_provider: object with search_stations(query: str) -> list[Station]
    allowed_user_id: int
    now_fn: callable returning datetime for date validation (optional)
    """

    def __init__(self, ticket_service, station_provider, allowed_user_id: int, now_fn=None) -> None:
        self.ticket_service = ticket_service
        self.station_provider = station_provider
        self.allowed_user_id = allowed_user_id
        self.now_fn = now_fn

    # ---------- helpers ----------
    def _check_auth(self, update: Update) -> bool:
        return _is_authorized(update, self.allowed_user_id)

    def _current_token(self, context: ContextTypes.DEFAULT_TYPE) -> str | None:
        return context.user_data.get("wizard_token")

    def _validate_token(self, token: str | None, context: ContextTypes.DEFAULT_TYPE) -> bool:
        cur = self._current_token(context)
        if cur is None or token != cur:
            return False
        return True

    # ---------- commands outside conversation ----------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return
        await update.message.reply_text(format_start_message())

    async def durum(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return
        active = self.ticket_service.get_active_search()
        msg = format_durum_message(active)
        await update.message.reply_text(msg)

    async def iptal(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return
        active = self.ticket_service.get_active_search()
        if active is None:
            await update.message.reply_text(format_no_active_for_cancel())
            return
        self.ticket_service.cancel_search(active.id)
        await update.message.reply_text(format_cancel_success())

    # ---------- /ara entry ----------
    async def ara_entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return -1  # END
        active = self.ticket_service.get_active_search()
        if active is None:
            # Start create wizard
            token = _generate_token()
            context.user_data["wizard_token"] = token
            context.user_data["wizard_mode"] = "create"
            context.user_data["wizard"] = {}
            context.user_data.pop("station_candidates", None)
            context.user_data.pop("station_step", None)
            await update.message.reply_text("🚉 Nereden hareket edeceksin?\n\nİstasyon adını yaz:")
            return STATE_ORIGIN
        else:
            # Show active exists + choice
            token = _generate_token()
            context.user_data["wizard_token"] = token
            # pending replace choice, not yet in wizard
            context.user_data["wizard_mode"] = "pending_replace"
            # Do not clear wizard yet; preserve
            msg = format_active_exists_message(active)
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Aramayı Değiştir", callback_data=f"rp:yes:{token}"),
                        InlineKeyboardButton("Vazgeç", callback_data=f"rp:no:{token}"),
                    ]
                ]
            )
            await update.message.reply_text(msg, reply_markup=keyboard)
            return STATE_AWAITING_REPLACE

    # ---------- replace choice callbacks ----------
    async def handle_replace_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return STATE_AWAITING_REPLACE
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        # format rp:yes:token or rp:no:token
        parts = data.split(":")
        if len(parts) != 3:
            await query.message.reply_text(format_stale_callback())
            return STATE_AWAITING_REPLACE
        _, action, token = parts
        if not self._validate_token(token, context):
            await query.message.reply_text(format_stale_callback())
            return STATE_AWAITING_REPLACE
        # valid token
        if action == "yes":
            # Start replacement wizard, new token for inner wizard? Keep same token for simplicity or generate new
            # Generate new token for wizard to make old replace token stale after starting?
            # We keep same token to avoid extra complexity but ensure stale for future /ara
            # Instead generate new wizard token to invalidate old callbacks (good for stale test)
            new_token = _generate_token()
            context.user_data["wizard_token"] = new_token
            context.user_data["wizard_mode"] = "replace"
            context.user_data["wizard"] = {}
            context.user_data.pop("station_candidates", None)
            context.user_data.pop("station_step", None)
            # Need to edit or reply with origin prompt
            try:
                await query.message.reply_text("🚉 Nereden hareket edeceksin?\n\nİstasyon adını yaz:")
            except Exception:
                await query.edit_message_text("🚉 Nereden hareket edeceksin?\n\nİstasyon adını yaz:")
            return STATE_ORIGIN
        elif action == "no":
            # Cancel replacement choice, preserve old active
            context.user_data.pop("wizard_token", None)
            context.user_data.pop("wizard_mode", None)
            context.user_data.pop("wizard", None)
            await query.message.reply_text(format_operation_cancelled())
            return -1
        else:
            await query.message.reply_text(format_stale_callback())
            return STATE_AWAITING_REPLACE

    # ---------- station text handlers ----------
    async def handle_origin_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return STATE_ORIGIN
        text = (update.message.text or "").strip()
        if not text:
            await update.message.reply_text("Lütfen istasyon adını yaz.")
            return STATE_ORIGIN
        # Resolve station
        try:
            # station_provider.search_stations returns list[Station]
            candidates = self.station_provider.search_stations(text)
        except Exception:
            # Treat any exception as no match (but dont expose raw)
            candidates = []
        if not candidates:
            await update.message.reply_text("İstasyon bulunamadı. Lütfen tekrar yaz:")
            return STATE_ORIGIN
        if len(candidates) == 1:
            station = candidates[0]
            context.user_data["wizard"]["origin"] = station
            # clear any previous candidate cache
            context.user_data.pop("station_candidates", None)
            context.user_data.pop("station_step", None)
            await update.message.reply_text("🚉 Nereye gideceksin?\n\nVarış istasyonunu yaz:")
            return STATE_DESTINATION
        else:
            # ambiguous -> show inline keyboard with compact ids
            token = self._current_token(context)
            # store candidates dict for lookup
            cand_dict = {str(s.id): s for s in candidates}
            context.user_data["station_candidates"] = cand_dict
            context.user_data["station_step"] = "origin"
            # Build keyboard, each button callback_data st:<id>:<token>
            keyboard_rows = []
            for s in candidates:
                # Display name + city if available
                label = s.name
                if s.city_name:
                    label = f"{s.name} ({s.city_name})"
                # Keep label short for Telegram
                if len(label) > 35:
                    label = label[:32] + "..."
                keyboard_rows.append([InlineKeyboardButton(label, callback_data=f"st:{s.id}:{token}")])
            markup = InlineKeyboardMarkup(keyboard_rows)
            await update.message.reply_text("Birden fazla istasyon bulundu. Lütfen seç:", reply_markup=markup)
            return STATE_ORIGIN

    async def handle_destination_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return STATE_DESTINATION
        text = (update.message.text or "").strip()
        if not text:
            await update.message.reply_text("Lütfen istasyon adını yaz.")
            return STATE_DESTINATION
        try:
            candidates = self.station_provider.search_stations(text)
        except Exception:
            candidates = []
        if not candidates:
            await update.message.reply_text("İstasyon bulunamadı. Lütfen tekrar yaz:")
            return STATE_DESTINATION
        if len(candidates) == 1:
            station = candidates[0]
            # Prevent same origin/destination? Not required by MVP but could be nice; allow?
            context.user_data["wizard"]["destination"] = station
            context.user_data.pop("station_candidates", None)
            context.user_data.pop("station_step", None)
            await update.message.reply_text("📅 Seyahat tarihini yaz.\n\nÖrnek: 15.09.2026")
            return STATE_DATE
        else:
            token = self._current_token(context)
            cand_dict = {str(s.id): s for s in candidates}
            context.user_data["station_candidates"] = cand_dict
            context.user_data["station_step"] = "destination"
            keyboard_rows = []
            for s in candidates:
                label = s.name
                if s.city_name:
                    label = f"{s.name} ({s.city_name})"
                if len(label) > 35:
                    label = label[:32] + "..."
                keyboard_rows.append([InlineKeyboardButton(label, callback_data=f"st:{s.id}:{token}")])
            markup = InlineKeyboardMarkup(keyboard_rows)
            await update.message.reply_text("Birden fazla istasyon bulundu. Lütfen seç:", reply_markup=markup)
            return STATE_DESTINATION

    async def handle_station_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return -1
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "st":
            await query.message.reply_text(format_stale_callback())
            return context.user_data.get("_current_state", STATE_ORIGIN)
        _, sid, token = parts
        if not self._validate_token(token, context):
            await query.message.reply_text(format_stale_callback())
            # Stay in same state? Return current state without mutation
            step = context.user_data.get("station_step")
            if step == "destination":
                return STATE_DESTINATION
            return STATE_ORIGIN
        cand_dict = context.user_data.get("station_candidates")
        step = context.user_data.get("station_step")
        if not cand_dict or sid not in cand_dict:
            await query.message.reply_text(format_stale_callback())
            if step == "destination":
                return STATE_DESTINATION
            return STATE_ORIGIN
        station = cand_dict[sid]
        # clear candidates
        context.user_data.pop("station_candidates", None)
        context.user_data.pop("station_step", None)
        if step == "destination":
            context.user_data["wizard"]["destination"] = station
            # Edit message to confirm selection
            try:
                await query.edit_message_text(f"Seçilen varış: {station.name}")
            except Exception:
                pass
            await query.message.reply_text("📅 Seyahat tarihini yaz.\n\nÖrnek: 15.09.2026")
            return STATE_DATE
        else:
            # default origin
            context.user_data["wizard"]["origin"] = station
            try:
                await query.edit_message_text(f"Seçilen kalkış: {station.name}")
            except Exception:
                pass
            await query.message.reply_text("🚉 Nereye gideceksin?\n\nVarış istasyonunu yaz:")
            return STATE_DESTINATION

    # ---------- date ----------
    async def handle_date_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return STATE_DATE
        text = (update.message.text or "").strip()
        try:
            domain_date = validate_date_strict(text, now_fn=self.now_fn)
        except ValueError as e:
            await update.message.reply_text(str(e) + "\n\nÖrnek: 15.09.2026\nTarihi tekrar yaz:")
            return STATE_DATE
        context.user_data["wizard"]["travel_date"] = domain_date
        context.user_data["wizard"]["travel_date_input"] = text
        await update.message.reply_text("🕐 En erken kalkış saati?\n\nÖrnek: 17:00")
        return STATE_FROM_TIME

    # ---------- from time ----------
    async def handle_from_time_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return STATE_FROM_TIME
        text = (update.message.text or "").strip()
        try:
            validated = validate_time_strict(text)
        except ValueError as e:
            await update.message.reply_text(str(e) + "\n\nÖrnek: 17:00\nSaati tekrar yaz:")
            return STATE_FROM_TIME
        context.user_data["wizard"]["from_time"] = validated
        await update.message.reply_text("🕐 En geç kalkış saati?\n\nÖrnek: 22:00")
        return STATE_TO_TIME

    # ---------- to time ----------
    async def handle_to_time_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return STATE_TO_TIME
        text = (update.message.text or "").strip()
        try:
            validated = validate_time_strict(text)
        except ValueError as e:
            await update.message.reply_text(str(e) + "\n\nÖrnek: 22:00\nSaati tekrar yaz:")
            return STATE_TO_TIME
        from_time = context.user_data["wizard"].get("from_time")
        if from_time is None:
            # should not happen, but fallback
            context.user_data["wizard"]["from_time"] = validated
            from_time = validated
        try:
            validate_time_window(from_time, validated)
        except ValueError as e:
            await update.message.reply_text(str(e) + "\n\nBitiş saati başlangıçtan önce olamaz. Örnek: 22:00\nBitiş saati tekrar yaz:")
            return STATE_TO_TIME
        context.user_data["wizard"]["to_time"] = validated
        # Build confirmation message
        wizard = context.user_data["wizard"]
        origin = wizard["origin"]
        dest = wizard["destination"]
        travel_date = wizard["travel_date"]
        from_t = wizard["from_time"]
        to_t = validated
        msg = format_confirmation_message(origin.name, dest.name, travel_date, from_t, to_t)
        token = self._current_token(context)
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Aramayı Başlat", callback_data=f"cf:yes:{token}"),
                    InlineKeyboardButton("❌ Vazgeç", callback_data=f"cf:no:{token}"),
                ]
            ]
        )
        await update.message.reply_text(msg, reply_markup=keyboard)
        return STATE_CONFIRM

    # ---------- confirmation ----------
    async def handle_confirm_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return STATE_CONFIRM
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "cf":
            await query.message.reply_text(format_stale_callback())
            return STATE_CONFIRM
        _, action, token = parts
        if not self._validate_token(token, context):
            await query.message.reply_text(format_stale_callback())
            return STATE_CONFIRM
        wizard = context.user_data.get("wizard")
        mode = context.user_data.get("wizard_mode")
        if wizard is None or mode not in ("create", "replace"):
            await query.message.reply_text(format_stale_callback())
            return -1

        if action == "no":
            # Cancel confirmation
            is_replace = mode == "replace"
            context.user_data.pop("wizard_token", None)
            context.user_data.pop("wizard_mode", None)
            context.user_data.pop("wizard", None)
            context.user_data.pop("station_candidates", None)
            context.user_data.pop("station_step", None)
            if is_replace:
                await query.message.reply_text(format_wizard_cancelled_preserved())
            else:
                await query.message.reply_text(format_operation_cancelled())
            try:
                await query.edit_message_text("❌ İşlem iptal edildi.")
            except Exception:
                pass
            return -1

        if action == "yes":
            # Confirm start - create or replace
            origin = wizard.get("origin")
            dest = wizard.get("destination")
            travel_date = wizard.get("travel_date")
            from_time = wizard.get("from_time")
            to_time = wizard.get("to_time")
            if not all([origin, dest, travel_date, from_time, to_time]):
                await query.message.reply_text(format_stale_callback())
                return STATE_CONFIRM
            try:
                if mode == "replace":
                    # atomic replacement
                    result = self.ticket_service.replace_active_search(
                        int(origin.id),
                        str(origin.name),
                        int(dest.id),
                        str(dest.name),
                        travel_date,
                        from_time,
                        to_time,
                    )
                    msg = format_replacement_started()
                else:
                    result = self.ticket_service.create_search(
                        int(origin.id),
                        str(origin.name),
                        int(dest.id),
                        str(dest.name),
                        travel_date,
                        from_time,
                        to_time,
                    )
                    msg = format_search_started()
            except TicketSearchConflictError as e:
                await query.message.reply_text(f"❌ Arama oluşturulamadı: {e}")
                return STATE_CONFIRM
            except TicketSearchValidationError as e:
                await query.message.reply_text(f"❌ Geçersiz arama: {e}")
                return STATE_CONFIRM
            except Exception as e:
                await query.message.reply_text(f"❌ Beklenmeyen hata: {e}")
                return STATE_CONFIRM

            # Clear wizard after success
            context.user_data.pop("wizard_token", None)
            context.user_data.pop("wizard_mode", None)
            context.user_data.pop("wizard", None)
            context.user_data.pop("station_candidates", None)
            context.user_data.pop("station_step", None)
            await query.message.reply_text(msg)
            try:
                await query.edit_message_text("✅ İşlem tamamlandı.")
            except Exception:
                pass
            return -1
        await query.message.reply_text(format_stale_callback())
        return STATE_CONFIRM

    # ---------- generic cancel via command inside conversation (optional) ----------
    async def cancel_wizard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not self._check_auth(update):
            await _unauthorized_reply(update, context)
            return -1
        mode = context.user_data.get("wizard_mode")
        is_replace = mode == "replace"
        context.user_data.pop("wizard_token", None)
        context.user_data.pop("wizard_mode", None)
        context.user_data.pop("wizard", None)
        context.user_data.pop("station_candidates", None)
        context.user_data.pop("station_step", None)
        if is_replace:
            await update.message.reply_text(format_wizard_cancelled_preserved())
        else:
            await update.message.reply_text(format_operation_cancelled())
        return -1

    # For PTB ConversationHandler we need to expose states mapping builder
    def build_conversation_handler(self):
        from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

        conv = ConversationHandler(
            entry_points=[CommandHandler("ara", self.ara_entry)],
            states={
                STATE_ORIGIN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_origin_text),
                    CallbackQueryHandler(self.handle_station_callback, pattern=r"^st:"),
                ],
                STATE_DESTINATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_destination_text),
                    CallbackQueryHandler(self.handle_station_callback, pattern=r"^st:"),
                ],
                STATE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_date_text)],
                STATE_FROM_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_from_time_text)],
                STATE_TO_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_to_time_text)],
                STATE_CONFIRM: [CallbackQueryHandler(self.handle_confirm_callback, pattern=r"^cf:")],
                STATE_AWAITING_REPLACE: [CallbackQueryHandler(self.handle_replace_choice, pattern=r"^rp:")],
            },
            fallbacks=[
                CommandHandler("iptal", self.cancel_wizard),
                CommandHandler("cancel", self.cancel_wizard),
            ],
            allow_reentry=True,
            per_user=True,
            per_chat=True,
        )
        return conv


def create_handlers(ticket_service, station_provider, allowed_user_id: int, now_fn=None) -> TelegramHandlers:
    return TelegramHandlers(ticket_service, station_provider, allowed_user_id, now_fn=now_fn)
