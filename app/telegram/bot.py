from __future__ import annotations

from telegram.ext import Application, CommandHandler

from .handlers import TelegramHandlers


def build_application(token: str, allowed_user_id: int, ticket_service, station_provider, now_fn=None) -> Application:
    """Build PTB Application with all handlers, without starting polling."""
    handlers = TelegramHandlers(ticket_service, station_provider, allowed_user_id, now_fn=now_fn)
    app = Application.builder().token(token).build()
    # Standalone commands
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("durum", handlers.durum))
    app.add_handler(CommandHandler("iptal", handlers.iptal))
    # Conversation for /ara wizard
    conv = handlers.build_conversation_handler()
    app.add_handler(conv)
    # Callback fallback for stale etc. – handled inside conversation states,
    # but also add global handlers for station/confirm when outside conversation? Keep minimal.
    return app


def create_handlers(ticket_service, station_provider, allowed_user_id: int, now_fn=None) -> TelegramHandlers:
    """Helper to construct handlers without building Application (for tests)."""
    return TelegramHandlers(ticket_service, station_provider, allowed_user_id, now_fn=now_fn)
